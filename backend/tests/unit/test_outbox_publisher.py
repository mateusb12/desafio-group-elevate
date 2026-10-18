import unittest
import os
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy.exc import SQLAlchemyError

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://elevate:elevate-local-only@localhost:5433/elevate")

from features.outbox.publisher import process_batch, publish_event


class FakeChannel:
    def __init__(self, confirmed=True):
        self.confirmed = confirmed
        self.calls = []

    def basic_publish(self, **kwargs):
        self.calls.append(kwargs)
        return self.confirmed


def event(event_id="event-1"):
    return SimpleNamespace(id=event_id, payload={"event_id": event_id, "lead_id": "lead-1"})


class OutboxPublisherTests(unittest.TestCase):
    def test_publish_uses_confirmed_persistent_mandatory_json_message(self):
        channel = FakeChannel()

        publish_event(channel, event())

        call = channel.calls[0]
        self.assertEqual(call["exchange"], "")
        self.assertEqual(call["routing_key"], "lead.distributed")
        self.assertTrue(call["mandatory"])
        self.assertEqual(call["properties"].message_id, "event-1")
        self.assertEqual(call["properties"].content_type, "application/json")
        self.assertEqual(call["properties"].delivery_mode, 2)
        self.assertIn(b'"event_id":"event-1"', call["body"])

    def test_confirmed_publication_marks_event(self):
        channel = FakeChannel()

        with patch("features.outbox.publisher.mark_published") as mark:
            self.assertEqual(process_batch(channel, [event()]), 1)

        mark.assert_called_once_with("event-1")

    def test_negative_confirmation_does_not_mark_event(self):
        channel = FakeChannel(confirmed=False)

        with patch("features.outbox.publisher.mark_published") as mark:
            with self.assertRaises(RuntimeError):
                process_batch(channel, [event()])

        mark.assert_not_called()

    def test_database_failure_after_confirmation_keeps_event_eligible(self):
        channel = FakeChannel()

        with patch(
            "features.outbox.publisher.mark_published",
            side_effect=SQLAlchemyError("controlled failure"),
        ) as mark:
            with self.assertRaises(SQLAlchemyError):
                process_batch(channel, [event()])

        mark.assert_called_once_with("event-1")
        self.assertEqual(channel.calls[0]["properties"].message_id, "event-1")


if __name__ == "__main__":
    unittest.main()
