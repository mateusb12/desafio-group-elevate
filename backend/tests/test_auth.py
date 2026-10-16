import os
import time
import unittest
from datetime import timedelta
from uuid import uuid4

from psycopg import connect, sql
from sqlalchemy.engine import make_url


class AuthIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_database_url = os.environ.get("DATABASE_URL", "")
        if not cls.original_database_url.startswith("postgresql+psycopg://"):
            raise RuntimeError("Os testes precisam de DATABASE_URL PostgreSQL.")

        url = make_url(cls.original_database_url)
        cls.test_database = "elevate_auth_test_" + uuid4().hex
        cls.admin_url = url.set(
            drivername="postgresql", database="postgres"
        ).render_as_string(hide_password=False)

        # Cria um banco separado: nunca altera tabelas da aplicação.
        with connect(cls.admin_url, autocommit=True) as conn:
            conn.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(cls.test_database))
            )
        cls.addClassCleanup(cls.cleanup_database)

        os.environ["DATABASE_URL"] = url.set(
            database=cls.test_database
        ).render_as_string(hide_password=False)
        os.environ["JWT_SECRET_KEY"] = "integration-test-only-key-with-32-plus-bytes"
        os.environ["SEED_DEMO"] = "1"

        from app import app
        from database import engine

        cls.app = app
        cls.app.config["TESTING"] = True
        cls.engine = engine

    @classmethod
    def cleanup_database(cls):
        if hasattr(cls, "engine"):
            cls.engine.dispose()
        os.environ["DATABASE_URL"] = cls.original_database_url
        with connect(cls.admin_url, autocommit=True) as conn:
            conn.execute(
                sql.SQL("DROP DATABASE {}").format(sql.Identifier(cls.test_database))
            )

    def setUp(self):
        self.client = self.app.test_client()

    def login(self, email="ana@logicall.example", password="demo123"):
        return self.client.post(
            "/auth/login",
            json={"email": email, "password": password},
        )

    def test_login_me_logout_and_revocation(self):
        # Sem autenticação.
        self.assertEqual(
            self.client.get("/auth/me").status_code, 401
        )

        # Login real com conta demonstrativa.
        response = self.login()
        self.assertEqual(response.status_code, 200)

        user = response.get_json()["user"]
        self.assertEqual(user["role"], "OPERATOR")
        self.assertEqual(user["callCenterName"], "Logicall")

        access = self.client.get_cookie("access_token_cookie")
        csrf = self.client.get_cookie("csrf_access_token")
        self.assertIsNotNone(access)
        self.assertIsNotNone(csrf)

        # O cookie autentica /me.
        response = self.client.get("/auth/me")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["user"]["email"],
            "ana@logicall.example",
        )

        # Sem CSRF, não pode fazer logout.
        response = self.client.post("/auth/logout")
        self.assertEqual(response.status_code, 401)

        # O token continua válido após a tentativa rejeitada.
        self.assertEqual(
            self.client.get("/auth/me").status_code, 200
        )

        # Logout com CSRF válido.
        response = self.client.post(
            "/auth/logout",
            headers={"X-CSRF-TOKEN": csrf.value},
        )
        self.assertEqual(response.status_code, 200)

        # Cookies foram limpos.
        self.assertIsNone(
            self.client.get_cookie("access_token_cookie")
        )

        # Reutilizar o JWT anterior não funciona.
        self.client.set_cookie(
            "access_token_cookie", access.value
        )
        self.assertEqual(
            self.client.get("/auth/me").status_code, 401
        )

    def test_invalid_credentials_and_payload(self):
        self.assertEqual(
            self.login(password="senha-errada").status_code,
            401,
        )

        # JSON válido, mas estrutura inválida.
        response = self.client.post(
            "/auth/login",
            json=["ana@logicall.example", "demo123"],
        )
        self.assertEqual(response.status_code, 400)

    def test_operator_from_another_call_center(self):
        response = self.login(
            email="bruno@salesbound.example"
        )
        self.assertEqual(response.status_code, 200)

        user = response.get_json()["user"]
        self.assertEqual(user["callCenterName"], "Salesbound")
        self.assertEqual(user["role"], "OPERATOR")

    def test_inactive_user_cannot_login(self):
        from sqlalchemy import select
        from auth.models import User
        from database import db_session

        with db_session() as db:
            user = db.scalar(
                select(User).where(
                    User.email == "ana@logicall.example"
                )
            )
            user.is_active = False
            db.commit()

        try:
            self.assertEqual(self.login().status_code, 401)
        finally:
            with db_session() as db:
                user = db.scalar(
                    select(User).where(
                        User.email == "ana@logicall.example"
                    )
                )
                user.is_active = True
                db.commit()

    def test_expired_token_is_rejected(self):
        original = self.app.config["JWT_ACCESS_TOKEN_EXPIRES"]
        try:
            self.app.config["JWT_ACCESS_TOKEN_EXPIRES"] = (
                timedelta(seconds=2)
            )
            response = self.login()
            self.assertEqual(response.status_code, 200)
        finally:
            self.app.config["JWT_ACCESS_TOKEN_EXPIRES"] = original

        # O login deve funcionar antes da expiração real.
        time.sleep(3)

        self.assertEqual(
            self.client.get("/auth/me").status_code, 401
        )
        self.assertEqual(
            self.client.post("/auth/logout").status_code,
            401,
        )


if __name__ == "__main__":
    unittest.main()
