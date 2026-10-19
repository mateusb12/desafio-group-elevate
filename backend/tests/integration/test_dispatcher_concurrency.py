import json
import time
import unittest
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from sqlalchemy import delete, func, select, text

from shared.database import db_session
from features.dispatcher.models import CallCenter
from features.leads.models import Contact, Distribution, Event, Lead
from features.outbox.models import OutboxPendingDelivery


URL = "http://127.0.0.1:5000/api/leads"
LOCK_SQL = "SELECT pg_advisory_xact_lock(41625, 20261017)"


def build_lead_payload(campaign, number):
    return {
        "_idempotency_key": str(uuid4()),
        "name": f"Teste Concorrencia {number}",
        "email": f"race-{campaign}-{number}@example.com",
        "phone": "+5585990000000",
        "product": "nutralean",
        "funnel": "vsl-01",
        "source": "google",
        "campaign": campaign,
        "affiliate_id": "123",
        "utm": {
            "source": "google",
            "medium": "cpc",
            "campaign": campaign,
            "content": "integration-test",
        },
    }


def post_single_lead_request(body):
    request = Request(
        URL,
        data=json.dumps({
            key: value for key, value in body.items()
            if key != "_idempotency_key"
        }).encode(),
        headers={
            "Content-Type": "application/json",
            "Idempotency-Key": body["_idempotency_key"],
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=90) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)
    except (URLError, TimeoutError) as error:
        return 0, {"error": str(error)}


def submit_requests_at_the_same_time(executor, request_bodies):
    """Garante que todas as requisições comecem juntas para testar concorrência real."""
    request_barrier = Barrier(len(request_bodies))

    def send_after_barrier(body):
        request_barrier.wait(timeout=20)
        return post_single_lead_request(body)

    return [
        executor.submit(send_after_barrier, body)
        for body in request_bodies
    ]


def collect_responses_from_futures(futures):
    """Aguarda e retorna as respostas produzidas pelas requisições."""
    return [future.result(timeout=100) for future in futures]


def count_requests_waiting_for_dispatcher_lock():
    with db_session() as monitor:
        return monitor.scalar(text("""
            SELECT COUNT(*)
            FROM pg_stat_activity
            WHERE datname = current_database()
              AND wait_event_type = 'Lock'
              AND wait_event = 'advisory'
        """))


def wait_for_dispatcher_lock_contention():
    """Aguarda requisições aparecerem esperando pelo bloqueio do dispatcher.

    Retorna quantas requests estavam bloqueadas.
    """
    for _ in range(50):
        waiting_requests = count_requests_waiting_for_dispatcher_lock()
        if waiting_requests:
            return waiting_requests
        time.sleep(0.1)
    return 0


def post_requests_concurrently(request_bodies):
    with ThreadPoolExecutor(max_workers=len(request_bodies)) as executor:
        futures = submit_requests_at_the_same_time(
            executor,
            request_bodies,
        )
        return collect_responses_from_futures(futures)


def post_requests_while_dispatcher_is_locked(request_bodies):
    with ThreadPoolExecutor(max_workers=len(request_bodies)) as executor:
        # Mantém o lock ocupado antes de iniciar as requisições.
        # Assim, elas precisam esperar o PostgreSQL liberar o dispatcher.
        with db_session() as locker:
            locker.execute(text(LOCK_SQL))
            futures = submit_requests_at_the_same_time(
                executor,
                request_bodies,
            )

            waiting_requests = wait_for_dispatcher_lock_contention()
            print(
                f"   Requisições aguardando o lock: {waiting_requests}",
                flush=True,
            )
            if not waiting_requests:
                raise AssertionError(
                    "Nenhuma transação aguardou o advisory lock."
                )

            locker.rollback()

        return collect_responses_from_futures(futures)


class TestDispatcherConcurrency(unittest.TestCase):
    def test_parallel_requests(self):
        marker = uuid4().hex[:12]
        bulk_campaign = f"it-{marker}-bulk"
        duplicate_campaign = f"it-{marker}-dup"
        campaigns = [bulk_campaign, duplicate_campaign]

        try:
            self.run_distribution_and_idempotency_scenarios(
                bulk_campaign,
                duplicate_campaign,
            )
        finally:
            # Remove exclusivamente os registros desta execução.
            with db_session() as db, db.begin():
                leads_to_remove = db.scalars(
                    select(Lead).where(Lead.campaign.in_(campaigns))
                ).all()

                lead_ids = [lead.id for lead in leads_to_remove]
                contact_ids = [lead.contact_id for lead in leads_to_remove]
                if lead_ids:
                    db.execute(
                        delete(Lead).where(Lead.id.in_(lead_ids))
                    )
                    db.execute(
                        delete(Contact).where(
                            Contact.id.in_(contact_ids)
                        )
                    )

            print(
                f"\n🧹 Limpeza: {len(lead_ids)} leads de teste removidos.",
                flush=True,
            )

    def run_distribution_and_idempotency_scenarios(
        self,
        bulk_campaign,
        duplicate_campaign,
    ):
        print("\n=== CENÁRIO 1: 100 LEADS DIFERENTES ===", flush=True)

        with db_session() as db:
            available_call_centers = db.scalars(
                select(CallCenter).where(
                    CallCenter.is_active.is_(True),
                    CallCenter.distribution_weight > 0,
                )
            ).all()

        with self.subTest("1.1 - garantir centros ativos para distribuição"):
            self.assertTrue(
                available_call_centers,
                "Nenhum call center ativo",
            )

        replies = []

        # Cinco lotes de 20 requisições simultâneas.
        # O primeiro lote força contenção real no PostgreSQL.
        for start in range(0, 100, 20):
            batch = [
                build_lead_payload(bulk_campaign, number)
                for number in range(start, start + 20)
            ]

            if start == 0:
                batch_replies = post_requests_while_dispatcher_is_locked(batch)
            else:
                batch_replies = post_requests_concurrently(batch)
            replies.extend(batch_replies)

            response_statuses = Counter(
                status for status, _ in batch_replies
            )
            print(
                f"   Lote {start // 20 + 1}: {dict(response_statuses)}",
                flush=True,
            )

        errors = [
            (status, body)
            for status, body in replies
            if status != 201
        ]

        with self.subTest("1.2 - criar 100 leads distintos sob concorrência"):
            self.assertFalse(errors, f"Falhas: {errors[:5]}")
            self.assertEqual(
                len({body["id"] for _, body in replies}),
                100,
                "IDs duplicados",
            )

        with db_session() as db:
            created = db.scalars(
                select(Lead).where(
                    Lead.campaign == bulk_campaign
                )
            ).all()

            lead_counts_by_center = dict(
                db.execute(
                    select(Lead.call_center_id, func.count(Lead.id))
                    .where(Lead.call_center_id.is_not(None))
                    .group_by(Lead.call_center_id)
                ).all()
            )

        with self.subTest("1.3 - persistir e atribuir todos os leads"):
            self.assertEqual(len(created), 100)
            self.assertTrue(all(lead.call_center_id for lead in created))

        distribution = Counter(
            lead.call_center_id for lead in created
        )

        print("\n   Distribuição dos 100 novos leads:")

        for center in sorted(
            available_call_centers,
            key=lambda item: -item.distribution_weight,
        ):
            print(
                f"   {center.name}: "
                f"{distribution[center.id]} leads"
            )

        total_weight = sum(
            center.distribution_weight
            for center in available_call_centers
        )
        total_assigned = sum(lead_counts_by_center.values())

        with self.subTest("1.4 - respeitar pesos de distribuição"):
            for center in available_call_centers:
                expected_lead_count = (
                    total_assigned
                    * center.distribution_weight
                    / total_weight
                )
                self.assertLessEqual(
                    abs(
                        lead_counts_by_center.get(center.id, 0)
                        - expected_lead_count
                    ),
                    1.01,
                    f"Distribuição desequilibrada: {center.name}",
                )

        print("✅ 100 leads criados e distribuição validada.")

        print(
            "\n=== CENÁRIO 2: 50 ENVIOS DO MESMO PAYLOAD ===",
            flush=True,
        )

        duplicate_payload = build_lead_payload(duplicate_campaign, 999)

        # Lotes simultâneos de 20, 20 e 10.
        duplicate_replies = []
        for size in (20, 20, 10):
            duplicate_requests = [
                duplicate_payload.copy() for _ in range(size)
            ]
            duplicate_replies.extend(
                post_requests_concurrently(duplicate_requests)
            )

        duplicate_response_statuses = Counter(
            status for status, _ in duplicate_replies
        )

        print(f"   HTTP: {dict(duplicate_response_statuses)}")

        with self.subTest("2.1 - aceitar uma requisição idempotente"):
            self.assertEqual(duplicate_response_statuses[201], 1)
            self.assertEqual(duplicate_response_statuses[200], 49)
            self.assertEqual(
                len({body["id"] for _, body in duplicate_replies}),
                1,
            )

        with db_session() as db:
            duplicates = db.scalars(
                select(Lead).where(
                    Lead.campaign == duplicate_campaign
                )
            ).all()

            all_test_leads = db.scalars(
                select(Lead).where(
                    Lead.campaign.in_(
                        [bulk_campaign, duplicate_campaign]
                    )
                )
            ).all()

            test_ids = [lead.id for lead in all_test_leads]

            event_count = db.scalar(
                select(func.count(Event.id))
                .where(Event.lead_id.in_(test_ids))
            )
            pending_delivery_count = db.scalar(
                select(func.count(OutboxPendingDelivery.id))
                .join(
                    Distribution,
                    Distribution.id == OutboxPendingDelivery.distribution_id,
                )
                .where(Distribution.lead_id.in_(test_ids))
            )

            contact_ids = {
                lead.contact_id for lead in all_test_leads
            }

        with self.subTest("2.2 - impedir duplicação de lead, contato e evento"):
            self.assertEqual(len(duplicates), 1)
            self.assertEqual(len(all_test_leads), 101)
            self.assertEqual(len(contact_ids), 101)
            self.assertEqual(event_count, 101)
            self.assertEqual(pending_delivery_count, 101)

        print("✅ 50 envios produziram somente 1 lead.")
        print("✅ 101 leads, 101 contatos e 101 eventos iniciais.")
        print("✅ Nenhuma duplicação persistida.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
