import json
import time
import unittest
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

from flask_jwt_extended import create_access_token, get_csrf_token
from sqlalchemy import delete, select, text

from app import app
from features.auth.models import User, UserRole
from shared.database import db_session
from features.leads.models import Contact, Event, Lead


BASE_URL = "http://127.0.0.1:5000"


def post_json_request(path, body, headers=None):
    request = Request(
        BASE_URL + path,
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            **(headers or {}),
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


class TestWebhookConcurrency(unittest.TestCase):

    def setUp(self):
        self.marker = uuid4().hex
        self.lead_id = None
        self.addCleanup(self.cleanup_lead)

        with app.app_context():
            with db_session() as db:
                admin_id = db.scalar(
                    select(User.id).where(
                        User.role == UserRole.ADMIN,
                        User.is_active.is_(True),
                    )
                )

            self.assertIsNotNone(admin_id)

            token = create_access_token(identity=admin_id)

            self.headers = {
                "Cookie": f"access_token_cookie={token}",
                "X-CSRF-TOKEN": get_csrf_token(token),
            }

        payload = {
            "name": "Teste Webhook Concorrente",
            "email": f"webhook-{self.marker}@example.com",
            "phone": "+5585990000000",
            "product": "nutralean",
            "funnel": "vsl-01",
            "source": "google",
            "campaign": f"it-webhook-{self.marker}",
            "affiliate_id": "123",
            "utm": {
                "source": "google",
                "medium": "cpc",
                "campaign": f"it-webhook-{self.marker}",
                "content": "concurrency-test",
            },
        }

        status, response = post_json_request(
            "/api/leads",
            payload,
            {"Idempotency-Key": str(uuid4())},
        )

        self.assertEqual(status, 201, response)
        self.lead_id = response["id"]

    def cleanup_lead(self):
        if self.lead_id is None:
            return

        with db_session() as db, db.begin():
            lead = db.get(Lead, self.lead_id)

            if lead is not None:
                contact_id = lead.contact_id

                # A FK de events possui ON DELETE CASCADE.
                db.execute(
                    delete(Lead).where(Lead.id == self.lead_id)
                )
                db.execute(
                    delete(Contact).where(Contact.id == contact_id)
                )

        print(
            f"🧹 Lead temporário {self.lead_id[:8]} removido.",
            flush=True,
        )

    def build_webhook_payload(self, external_id, status, seconds):
        return {
            "lead_id": self.lead_id,
            "external_id": external_id,
            "status": status,
            "event_at": (
                datetime.now(timezone.utc)
                + timedelta(seconds=seconds)
            ).isoformat(),
        }

    def get_lead_events(self):
        with db_session() as db:
            return db.scalars(
                select(Event)
                .where(Event.lead_id == self.lead_id)
            ).all()

    def get_current_lead_status(self):
        with db_session() as db:
            return db.scalar(
                select(Lead.status).where(
                    Lead.id == self.lead_id
                )
            )

    def submit_webhooks_at_same_time(self, executor, webhook_payloads):
        """Garante que todos os webhooks comecem juntos."""
        request_barrier = Barrier(len(webhook_payloads))

        def send_after_barrier(payload):
            request_barrier.wait(timeout=15)
            return post_json_request(
                "/api/webhooks/callcenter",
                payload,
                self.headers,
            )

        return [
            executor.submit(send_after_barrier, payload)
            for payload in webhook_payloads
        ]

    def collect_responses_from_futures(self, futures):
        """Aguarda e retorna as respostas dos webhooks."""
        return [future.result(timeout=45) for future in futures]

    def count_requests_waiting_for_lead_lock(self):
        """Conta requisições bloqueadas pela linha do lead."""
        with db_session() as monitor:
            return monitor.scalar(text("""
                SELECT COUNT(*)
                FROM pg_stat_activity
                WHERE datname = current_database()
                  AND pid <> pg_backend_pid()
                  AND wait_event_type = 'Lock'
                  AND query ILIKE '%leads%'
                  AND query ILIKE '%FOR UPDATE%'
            """))

    def wait_for_lead_lock_contention(self, expected_requests):
        """Aguarda todas as requisições disputarem o bloqueio do lead."""
        for _ in range(80):
            waiting_requests = self.count_requests_waiting_for_lead_lock()
            if waiting_requests >= expected_requests:
                return waiting_requests
            time.sleep(0.1)
        return waiting_requests

    def post_webhooks_while_lead_is_locked(self, webhook_payloads):
        """Dispara webhooks enquanto mantém o lead bloqueado no banco."""
        with ThreadPoolExecutor(
            max_workers=len(webhook_payloads)
        ) as executor:
            with db_session() as locker:
                locker.execute(
                    select(Lead.id)
                    .where(Lead.id == self.lead_id)
                    .with_for_update()
                ).scalar_one()

                try:
                    futures = self.submit_webhooks_at_same_time(
                        executor,
                        webhook_payloads,
                    )
                    waiting_requests = self.wait_for_lead_lock_contention(
                        len(webhook_payloads)
                    )

                    print(
                        f"   Requisições aguardando lock: {waiting_requests}",
                        flush=True,
                    )
                    self.assertGreaterEqual(
                        waiting_requests,
                        len(webhook_payloads),
                        "Nem todas as requisições disputaram "
                        "o lock no PostgreSQL.",
                    )
                finally:
                    locker.rollback()

            return self.collect_responses_from_futures(futures)

    def test_01_identical_events(self):
        print(
            "\n=== CENÁRIO 1: DOIS WEBHOOKS IDÊNTICOS ===",
            flush=True,
        )

        event_payload = self.build_webhook_payload(
            str(uuid4()), "sale", 120
        )

        responses = self.post_webhooks_while_lead_is_locked([
            event_payload,
            event_payload.copy(),
        ])

        response_statuses = Counter(code for code, _ in responses)
        print(f"   HTTP: {dict(response_statuses)}", flush=True)

        with self.subTest("1.1 - aceitar uma requisição e reconhecer a duplicata"):
            self.assertEqual(response_statuses[201], 1)
            self.assertEqual(response_statuses[200], 1)
            self.assertEqual(len({body["id"] for _, body in responses}), 1)
            self.assertEqual(
                sum(bool(body.get("duplicate")) for _, body in responses),
                1,
            )

        with self.subTest("1.2 - persistir apenas um evento"):
            matching_events = [
                event for event in self.get_lead_events()
                if event.external_id == event_payload["external_id"]
            ]
            self.assertEqual(len(matching_events), 1)

        with self.subTest("1.3 - manter o status final do evento"):
            self.assertEqual(self.get_current_lead_status(), "sale")

        print("✅ Apenas um evento persistido.")
        print("✅ Duplicata reconhecida corretamente.")
        print("✅ Status final: sale.")

    def test_02_out_of_order_events(self):
        print(
            "\n=== CENÁRIO 2: EVENTOS FORA DE ORDEM ===",
            flush=True,
        )

        older = self.build_webhook_payload(
            str(uuid4()), "contacted", 120
        )
        newer = self.build_webhook_payload(
            str(uuid4()), "sale", 240
        )

        responses = self.post_webhooks_while_lead_is_locked([
            newer,
            older,
        ])

        response_statuses = Counter(code for code, _ in responses)
        print(f"   HTTP: {dict(response_statuses)}", flush=True)

        with self.subTest("2.1 - aceitar os dois eventos fora de ordem"):
            self.assertEqual(response_statuses[201], 2)
            received = [
                event for event in self.get_lead_events()
                if event.external_id in {
                    older["external_id"],
                    newer["external_id"],
                }
            ]
            self.assertEqual(len(received), 2)
            self.assertEqual(
                {event.status for event in received},
                {"contacted", "sale"},
            )

        with self.subTest("2.2 - usar o status do evento mais recente"):
            self.assertEqual(self.get_current_lead_status(), "sale")

        print("✅ Os dois eventos foram persistidos.")
        print("✅ Status final corresponde ao evento mais recente.")

    def test_03_conflicting_external_id(self):
        print(
            "\n=== CENÁRIO 3: EXTERNAL_ID CONFLITANTE ===",
            flush=True,
        )

        external_id = str(uuid4())

        first = self.build_webhook_payload(
            external_id, "sale", 120
        )
        second = {
            **first,
            "status": "refund",
        }

        responses = self.post_webhooks_while_lead_is_locked([
            first,
            second,
        ])

        response_statuses = Counter(code for code, _ in responses)
        print(f"   HTTP: {dict(response_statuses)}", flush=True)

        with self.subTest("3.1 - aceitar somente um evento conflitante"):
            self.assertEqual(response_statuses[201], 1)
            self.assertEqual(response_statuses[409], 1)

        with self.subTest("3.2 - impedir duplicidade do external_id"):
            matching_events = [
                event for event in self.get_lead_events()
                if event.external_id == external_id
            ]
            self.assertEqual(len(matching_events), 1)

        winning_status = next(
            body["status"]
            for code, body in responses
            if code == 201
        )
        with self.subTest("3.3 - refletir no lead o status aceito"):
            self.assertEqual(matching_events[0].status, winning_status)
            self.assertEqual(self.get_current_lead_status(), winning_status)

        print("✅ Um evento aceito e outro rejeitado.")
        print("✅ Nenhum external_id conflitante foi duplicado.")
        print(f"✅ Status final: {winning_status}.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
