import unittest
from uuid import uuid4

from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import SQLAlchemyError

from features.leads.models import Contact, Distribution, Event, Lead
from features.leads.service import create_lead
from features.outbox.models import OutboxPendingDelivery
from shared.database import db_session

from tests.integration.test_catalog_and_distributions import post_lead


class PendingDeliveryIntegrationTests(unittest.TestCase):
    def payload(self, marker, suffix="lead"):
        return {
            "name": f"Outbox {suffix}",
            "email": f"{marker}-{suffix}@example.com",
            "phone": "+5585990000999",
            "product": "nutralean",
            "funnel": "vsl-01",
            "source": "outbox-test",
            "campaign": f"outbox-{marker}-{suffix}",
            "affiliate_id": f"outbox-affiliate-{marker}",
            "utm": {
                "source": "outbox-test",
                "medium": "test",
                "campaign": f"outbox-{marker}-{suffix}",
                "content": "integration",
            },
        }

    def test_creation_persists_pending_delivery_with_minimal_payload(self):
        marker = uuid4().hex
        response_status, response_body = post_lead(self.payload(marker))
        self.assertEqual(response_status, 201, response_body)
        lead_id = response_body["id"]

        try:
            with db_session() as db:
                lead = db.scalar(select(Lead).where(Lead.id == lead_id))
                distribution = db.scalar(
                    select(Distribution).where(Distribution.lead_id == lead_id)
                )
                delivery = db.scalar(
                    select(OutboxPendingDelivery).where(
                        OutboxPendingDelivery.distribution_id == distribution.id
                    )
                )

            self.assertIsNotNone(lead)
            self.assertIsNotNone(distribution)
            self.assertIsNotNone(delivery)
            self.assertEqual(delivery.event_type, "lead.distributed")
            self.assertIsNone(delivery.published_at)
            self.assertEqual(delivery.payload, {
                "event_id": delivery.id,
                "lead_id": lead_id,
                "distribution_id": distribution.id,
                "call_center_id": distribution.call_center_id,
            })
            self.assertEqual(delivery.payload["call_center_id"], lead.call_center_id)
        finally:
            self.cleanup_campaign(marker)

    def test_idempotency_and_conflict_do_not_duplicate_delivery(self):
        marker = uuid4().hex
        payload = self.payload(marker)
        key = str(uuid4())

        try:
            first_status, first_body = post_lead(payload, key)
            second_status, second_body = post_lead(payload, key)
            conflict_payload = self.payload(marker, "conflict")
            conflict_payload["campaign"] = payload["campaign"]
            conflict_status, _ = post_lead(conflict_payload, key)

            self.assertEqual(first_status, 201, first_body)
            self.assertEqual(second_status, 200, second_body)
            self.assertEqual(second_body["id"], first_body["id"])
            self.assertEqual(conflict_status, 409)

            with db_session() as db:
                delivery_count = db.scalar(
                    select(func.count(OutboxPendingDelivery.id))
                    .join(
                        Distribution,
                        Distribution.id == OutboxPendingDelivery.distribution_id,
                    )
                    .where(Distribution.lead_id == first_body["id"])
                )

            self.assertEqual(delivery_count, 1)
        finally:
            self.cleanup_campaign(marker)

    def test_database_failure_writing_delivery_rolls_back_everything(self):
        marker = uuid4().hex
        payload = self.payload(marker)
        clean_payload = payload.copy()
        clean_payload["utm"] = payload["utm"].copy()
        key = str(uuid4())
        function_name = f"test_fail_outbox_insert_{marker}"
        trigger_name = f"test_fail_outbox_trigger_{marker}"

        self.install_outbox_failure_trigger(function_name, trigger_name)
        try:
            with self.assertRaises(SQLAlchemyError):
                with db_session() as db:
                    create_lead(db, clean_payload, key)
        finally:
            self.remove_outbox_failure_trigger(function_name, trigger_name)

        with db_session() as db:
            lead_count = db.scalar(
                select(func.count(Lead.id)).where(
                    Lead.campaign == payload["campaign"]
                )
            )
            distribution_count = db.scalar(
                select(func.count(Distribution.id)).join(
                    Lead, Lead.id == Distribution.lead_id
                ).where(Lead.campaign == payload["campaign"])
            )
            event_count = db.scalar(
                select(func.count(Event.id)).join(
                    Lead, Lead.id == Event.lead_id
                ).where(Lead.campaign == payload["campaign"])
            )
            delivery_count = db.scalar(
                select(func.count(OutboxPendingDelivery.id)).join(
                    Distribution,
                    Distribution.id == OutboxPendingDelivery.distribution_id,
                ).join(Lead, Lead.id == Distribution.lead_id).where(
                    Lead.campaign == payload["campaign"]
                )
            )

        self.assertEqual(lead_count, 0)
        self.assertEqual(distribution_count, 0)
        self.assertEqual(event_count, 0)
        self.assertEqual(delivery_count, 0)

    @staticmethod
    def install_outbox_failure_trigger(function_name, trigger_name):
        with db_session() as db, db.begin():
            db.execute(text(f"""
                CREATE FUNCTION {function_name}() RETURNS trigger
                LANGUAGE plpgsql
                AS $$
                BEGIN
                    RAISE EXCEPTION 'controlled outbox database failure';
                END;
                $$;
            """))
            db.execute(text(f"""
                CREATE TRIGGER {trigger_name}
                BEFORE INSERT ON outbox_pending_deliveries
                FOR EACH ROW EXECUTE FUNCTION {function_name}();
            """))

    @staticmethod
    def remove_outbox_failure_trigger(function_name, trigger_name):
        with db_session() as db, db.begin():
            db.execute(text(
                f"DROP TRIGGER IF EXISTS {trigger_name} "
                "ON outbox_pending_deliveries"
            ))
            db.execute(text(f"DROP FUNCTION IF EXISTS {function_name}()"))

    @staticmethod
    def cleanup_campaign(marker):
        with db_session() as db, db.begin():
            leads = db.scalars(
                select(Lead).where(Lead.campaign == f"outbox-{marker}-lead")
            ).all()
            lead_ids = [lead.id for lead in leads]
            contact_ids = [lead.contact_id for lead in leads]
            if lead_ids:
                db.execute(delete(Lead).where(Lead.id.in_(lead_ids)))
            if contact_ids:
                db.execute(delete(Contact).where(Contact.id.in_(contact_ids)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
