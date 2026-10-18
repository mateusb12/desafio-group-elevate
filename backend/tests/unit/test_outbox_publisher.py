import unittest
import os
from types import SimpleNamespace
from unittest.mock import patch

from pika.exceptions import AMQPConnectionError, NackError, UnroutableError
from sqlalchemy.exc import SQLAlchemyError

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://elevate:elevate-local-only@localhost:5433/elevate")

from features.outbox.publisher import check_rabbitmq, process_batch, publish_event


class FakeChannel:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def basic_publish(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return None


class FakeRabbitChannel:
    def queue_declare(self, **kwargs):
        self.queue_declare_kwargs = kwargs
        return SimpleNamespace(method=SimpleNamespace(message_count=7))

    def close(self):
        return None


class FakeRabbitConnection:
    is_closed = False

    def close(self):
        return None


def event(event_id="event-1"):
    return SimpleNamespace(id=event_id, payload={"event_id": event_id, "lead_id": "lead-1"})


class OutboxPublisherTests(unittest.TestCase):
    def test_rabbitmq_health_returns_ready_message_count(self):
        connection = FakeRabbitConnection()
        channel = FakeRabbitChannel()

        with patch("features.outbox.publisher.open_confirmed_channel", return_value=(connection, channel)):
            self.assertEqual(check_rabbitmq(), {"state": "available", "messageCount": 7})

        self.assertEqual(channel.queue_declare_kwargs, {"queue": "lead.distributed", "passive": True})

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

    def test_nack_does_not_mark_event(self):
        channel = FakeChannel(NackError([]))

        with patch("features.outbox.publisher.mark_published") as mark:
            with self.assertRaises(NackError):
                process_batch(channel, [event()])

        mark.assert_not_called()

    def test_unroutable_does_not_mark_event(self):
        channel = FakeChannel(UnroutableError([]))

        with patch("features.outbox.publisher.mark_published") as mark:
            with self.assertRaises(UnroutableError):
                process_batch(channel, [event()])

        mark.assert_not_called()

    def test_connection_failure_does_not_mark_event(self):
        channel = FakeChannel(AMQPConnectionError("connection closed"))

        with patch("features.outbox.publisher.mark_published") as mark:
            with self.assertRaises(AMQPConnectionError):
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
