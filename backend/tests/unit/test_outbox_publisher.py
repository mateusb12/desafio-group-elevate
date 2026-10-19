import unittest
import os
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from pika.exceptions import AMQPConnectionError, NackError, UnroutableError
from sqlalchemy.exc import SQLAlchemyError

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://elevate:elevate-local-only@localhost:5433/elevate")

from features.outbox.publisher import (
    OutboxCounters,
    check_rabbitmq,
    clear_delivery_dead_letter_queue,
    publish_event,
    publish_outbox_batch,
)


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
        message_count = 7 if kwargs["queue"] == "lead.distributed" else 3
        return SimpleNamespace(method=SimpleNamespace(message_count=message_count))

    def close(self):
        return None

    def queue_purge(self, **kwargs):
        self.queue_purge_kwargs = kwargs
        return SimpleNamespace(method=SimpleNamespace(message_count=3))


class FakeRabbitConnection:
    is_closed = False

    def close(self):
        return None


def event(event_id="event-1"):
    return SimpleNamespace(id=event_id, payload={"event_id": event_id, "lead_id": "lead-1"})


class OutboxPublisherTests(unittest.TestCase):
    def test_publication_memory_counts_each_event_once_per_stage(self):
        memory = OutboxCounters(os.path.join(tempfile.mkdtemp(), "outbox.sqlite3"))

        memory.mark_rabbit_published("event-1")
        memory.mark_rabbit_published("event-1")
        memory.mark_sql_published("event-1")

        with self.subTest("1.1 - contar publicação RabbitMQ uma única vez"):
            self.assertEqual(
                memory.health_status(),
                {"status": "ok", "publishedCount": 1, "markedPublishedCount": 1},
            )

    def test_publication_memory_reset_clears_counters(self):
        memory = OutboxCounters(os.path.join(tempfile.mkdtemp(), "outbox.sqlite3"))
        memory.mark_rabbit_published("event-1")
        memory.mark_sql_published("event-1")

        with self.subTest("2.1 - apagar contadores persistidos"):
            self.assertEqual(memory.reset(), {"status": "ok", "deleted": 1})

        with self.subTest("2.2 - zerar contadores após reset"):
            self.assertEqual(memory.health_status()["publishedCount"], 0)

    def test_rabbitmq_health_returns_ready_message_count(self):
        connection = FakeRabbitConnection()
        channel = FakeRabbitChannel()

        with self.subTest("3.1 - retornar saúde disponível e contadores"):
            with patch("features.outbox.publisher.open_confirmed_channel", return_value=(connection, channel)):
                self.assertEqual(
                    check_rabbitmq(),
                    {"state": "available", "messageCount": 7, "deadLetterCount": 3},
                )

        with self.subTest("3.2 - consultar fila de dead letters sem consumir mensagens"):
            self.assertEqual(channel.queue_declare_kwargs, {"queue": "lead.distributed.invalid", "passive": True})

    def test_clear_delivery_dead_letter_queue_purges_invalid_queue(self):
        connection = FakeRabbitConnection()
        channel = FakeRabbitChannel()

        with self.subTest("4.1 - retornar quantidade de mensagens removidas"):
            with patch("features.outbox.publisher.open_confirmed_channel", return_value=(connection, channel)):
                self.assertEqual(clear_delivery_dead_letter_queue(), 3)

        with self.subTest("4.2 - purgar fila de dead letters"):
            self.assertEqual(channel.queue_purge_kwargs, {"queue": "lead.distributed.invalid"})

    def test_publish_uses_confirmed_persistent_mandatory_json_message(self):
        channel = FakeChannel()

        publish_event(channel, event())

        call = channel.calls[0]
        with self.subTest("5.1 - publicar na rota correta com entrega obrigatória"):
            self.assertEqual(call["exchange"], "")
            self.assertEqual(call["routing_key"], "lead.distributed")
            self.assertTrue(call["mandatory"])

        with self.subTest("5.2 - enviar mensagem JSON persistente identificada"):
            self.assertEqual(call["properties"].message_id, "event-1")
            self.assertEqual(call["properties"].content_type, "application/json")
            self.assertEqual(call["properties"].delivery_mode, 2)
            self.assertIn(b'"event_id":"event-1"', call["body"])

    def test_confirmed_publication_marks_event(self):
        channel = FakeChannel()

        with patch("features.outbox.publisher.mark_published") as mark:
            self.assertEqual(publish_outbox_batch(channel, [event()]), 1)

        mark.assert_called_once_with("event-1")

    def test_nack_does_not_mark_event(self):
        channel = FakeChannel(NackError([]))

        with patch("features.outbox.publisher.mark_published") as mark:
            with self.assertRaises(NackError):
                publish_outbox_batch(channel, [event()])

        mark.assert_not_called()

    def test_unroutable_does_not_mark_event(self):
        channel = FakeChannel(UnroutableError([]))

        with patch("features.outbox.publisher.mark_published") as mark:
            with self.assertRaises(UnroutableError):
                publish_outbox_batch(channel, [event()])

        mark.assert_not_called()

    def test_connection_failure_does_not_mark_event(self):
        channel = FakeChannel(AMQPConnectionError("connection closed"))

        with patch("features.outbox.publisher.mark_published") as mark:
            with self.assertRaises(AMQPConnectionError):
                publish_outbox_batch(channel, [event()])

        mark.assert_not_called()

    def test_database_failure_after_confirmation_keeps_event_eligible(self):
        channel = FakeChannel()

        with patch(
            "features.outbox.publisher.mark_published",
            side_effect=SQLAlchemyError("controlled failure"),
        ) as mark:
            with self.assertRaises(SQLAlchemyError):
                publish_outbox_batch(channel, [event()])

        mark.assert_called_once_with("event-1")
        self.assertEqual(channel.calls[0]["properties"].message_id, "event-1")


if __name__ == "__main__":
    unittest.main()
