import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from features.webhooks.schemas import CallCenterWebhookInput
from features.webhooks.service import process_webhook


class WebhookServiceTests(unittest.TestCase):
    def webhook(self, external_id, status, event_at):
        return CallCenterWebhookInput(
            lead_id='lead-1',
            external_id=external_id,
            status=status,
            event_at=event_at.isoformat(),
        )

    def database(self, lead, existing_event=None, latest_event_at=None):
        db = MagicMock()
        db.begin.return_value.__enter__.return_value = db
        db.scalar.side_effect = [lead, existing_event, latest_event_at]
        return db

    def test_newer_event_updates_current_status_and_creates_history(self):
        event_at = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
        lead = SimpleNamespace(
            id='lead-1',
            status='new',
            received_at=datetime(2026, 10, 19, 11, 0, tzinfo=timezone.utc),
        )
        db = self.database(lead, latest_event_at=lead.received_at)

        with self.subTest(
            "1.1 - atualizar o lead com o status do evento mais recente"
        ):
            response, status_code = process_webhook(
                db,
                self.webhook(str(uuid4()), 'contacted', event_at),
            )
            self.assertEqual(status_code, 201)
            self.assertEqual(lead.status, 'contacted')
            self.assertTrue(response['applied'])
            self.assertFalse(response['out_of_order'])

        with self.subTest(
            "1.2 - registrar o evento no histórico do lead"
        ):
            persisted_event = db.add.call_args.args[0]
            self.assertEqual(persisted_event.lead_id, 'lead-1')
            self.assertEqual(persisted_event.status, 'contacted')
            self.assertEqual(persisted_event.event_at, event_at)

    def test_older_event_is_kept_in_history_without_overwriting_status(self):
        older_event_at = datetime(2026, 10, 19, 11, 0, tzinfo=timezone.utc)
        latest_event_at = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
        lead = SimpleNamespace(
            id='lead-1',
            status='sale',
            received_at=datetime(2026, 10, 19, 10, 0, tzinfo=timezone.utc),
        )
        db = self.database(lead, latest_event_at=latest_event_at)

        with self.subTest(
            "2.1 - ignorar evento antigo ao atualizar o status atual"
        ):
            response, status_code = process_webhook(
                db,
                self.webhook(str(uuid4()), 'contacted', older_event_at),
            )
            self.assertEqual(status_code, 201)
            self.assertEqual(lead.status, 'sale')
            self.assertFalse(response['applied'])
            self.assertTrue(response['out_of_order'])

        with self.subTest(
            "2.2 - manter o evento antigo no histórico"
        ):
            persisted_event = db.add.call_args.args[0]
            self.assertEqual(persisted_event.status, 'contacted')
            self.assertEqual(persisted_event.event_at, older_event_at)

    def test_duplicate_event_is_acknowledged_without_creating_history(self):
        event_at = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
        existing_event = SimpleNamespace(
            id='event-1',
            status='sale',
            event_at=event_at,
        )
        lead = SimpleNamespace(id='lead-1', status='sale')
        db = self.database(lead, existing_event=existing_event)

        with self.subTest(
            "3.1 - retornar sucesso para webhook já processado"
        ):
            response, status_code = process_webhook(
                db,
                self.webhook('external-1', 'sale', event_at),
            )
            self.assertEqual(status_code, 200)
            self.assertTrue(response['duplicate'])
            self.assertFalse(response['applied'])

        with self.subTest(
            "3.2 - não criar evento duplicado no histórico"
        ):
            db.add.assert_not_called()

    def test_reused_external_id_with_different_data_is_rejected(self):
        event_at = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
        existing_event = SimpleNamespace(
            id='event-1',
            status='sale',
            event_at=event_at,
        )
        lead = SimpleNamespace(id='lead-1', status='sale')
        db = self.database(lead, existing_event=existing_event)

        with self.subTest(
            "4.1 - rejeitar external_id com dados diferentes"
        ):
            response, status_code = process_webhook(
                db,
                self.webhook('external-1', 'refund', event_at),
            )
            self.assertEqual(status_code, 409)
            self.assertIn('external_id', response['error'])

        with self.subTest(
            "4.2 - preservar o status após rejeitar o conflito"
        ):
            self.assertEqual(lead.status, 'sale')
            db.add.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
