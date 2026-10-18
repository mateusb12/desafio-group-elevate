import os
from datetime import timedelta

from flask import Flask, jsonify
from flask_jwt_extended import JWTManager
from sqlalchemy import select

from features.auth import auth_blueprint
from features.auth.models import TokenBlocklist
from features.auth.service import seed_demo_users
from features.dispatcher import dispatcher_blueprint
from features.dispatcher import models as dispatcher_models  # noqa: F401
from features.dashboard import dashboard_blueprint
from features.leads import leads_blueprint
from features.leads.products import catalog_blueprint
from features.leads import models as leads_models  # noqa: F401
from features.webhooks import webhooks_blueprint
from features.lab import lab_blueprint
from shared.database import db_session
from shared.demo import reset_and_seed_demo


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["JWT_SECRET_KEY"] = os.environ["JWT_SECRET_KEY"]
    app.config["JWT_TOKEN_LOCATION"] = ["cookies"]
    app.config["JWT_COOKIE_SECURE"] = os.getenv("JWT_COOKIE_SECURE", "0") == "1"
    app.config["JWT_COOKIE_SAMESITE"] = "Lax"
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(
        minutes=int(os.getenv("JWT_ACCESS_TOKEN_MINUTES", "15"))
    )

    jwt = JWTManager(app)

    @jwt.token_in_blocklist_loader
    def is_token_revoked(_jwt_header: dict, jwt_payload: dict) -> bool:
        with db_session() as db:
            return db.scalar(
                select(TokenBlocklist.jti).where(
                    TokenBlocklist.jti == jwt_payload["jti"]
                )
            ) is not None

    app.register_blueprint(auth_blueprint)
    app.register_blueprint(dashboard_blueprint)
    app.register_blueprint(dispatcher_blueprint)
    app.register_blueprint(leads_blueprint)
    app.register_blueprint(catalog_blueprint)
    app.register_blueprint(webhooks_blueprint)
    app.register_blueprint(lab_blueprint)

    @app.get("/")
    def hello():
        return "Hello, world!"

    @app.get("/ping")
    def ping():
        return jsonify(status="ok", message="pong")

    return app


if os.getenv("SEED_DEMO") == "1":
    if os.getenv("RESET_DEMO") == "1":
        reset_and_seed_demo()
    else:
        from features.leads.products import seed_demo_catalog

        with db_session() as database:
            seed_demo_users(database)
            seed_demo_catalog(database)

app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
