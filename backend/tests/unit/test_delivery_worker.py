import unittest
import os
import tempfile
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from pika.exceptions import AMQPError, NackError, UnroutableError

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://elevate:elevate-local-only@localhost:5433/elevate")

from features.delivery_worker.worker import (
    CALL_CENTER_URLS,
    DeliveryWorker,
    DeliveryResult,
    InvalidMessage,
    parse_message,
)
import features.delivery_worker.worker as delivery_worker_module


class DeliveryWorkerTests(unittest.TestCase):
    def test_health_status_counts_unique_processed_events(self):
        worker = DeliveryWorker()
        worker.database_path = os.path.join(tempfile.mkdtemp(), "worker.sqlite3")

        worker._mark_processed("event-1")
        worker._mark_processed("event-1")
        worker._mark_processed("event-2")

        with self.subTest("1.1 - contar cada evento processado uma única vez"):
            self.assertEqual(
                worker.health_status(),
                {"status": "ok", "processedCount": 2},
            )

    def test_reset_processed_clears_persisted_counter(self):
        worker = DeliveryWorker()
        worker.database_path = os.path.join(tempfile.mkdtemp(), "worker.sqlite3")
        worker._mark_processed("event-1")

        with self.subTest("2.1 - remover registros processados persistidos"):
            self.assertEqual(worker.reset_processed(), {"status": "ok", "deleted": 1})

        with self.subTest("2.2 - zerar contador após reset"):
            self.assertEqual(worker.health_status()["processedCount"], 0)

    def payload(self, call_center_id="call-center-a"):
        return {
            "event_id": "event-1",
            "lead_id": "lead-1",
            "distribution_id": "distribution-1",
            "call_center_id": call_center_id,
        }

    @patch("features.delivery_worker.worker._mark_delivery_as_delivered")
    @patch("features.delivery_worker.worker._record_delivery_attempt")
    @patch("features.delivery_worker.worker._get_or_create_delivery_record")
    def test_routes_to_each_call_center_and_ack_result_follows_http(self, ensure, attempt, delivered):
        for index, (call_center_id, expected_url) in enumerate(CALL_CENTER_URLS.items(), 1):
            with self.subTest(f"3.{index} - encaminhar para {call_center_id} e confirmar ACK"):
                http_post = Mock()
                ensure.return_value = SimpleNamespace(status="pending")
                worker = DeliveryWorker(http_post=http_post)

                result = worker.process(self.payload(call_center_id))

                self.assertTrue(result.ack)
                http_post.assert_called_once_with(expected_url, self.payload(call_center_id), worker.http_timeout)
                delivered.assert_called()
        with self.subTest("3.4 - confirmar todos os eventos entregues"):
            self.assertEqual(delivered.call_count, 3)

    @patch("features.delivery_worker.worker._mark_delivery_as_delivered")
    @patch("features.delivery_worker.worker._record_delivery_attempt")
    @patch("features.delivery_worker.worker._get_or_create_delivery_record")
    def test_ack_is_not_possible_before_http_completion(self, ensure, attempt, delivered):
        order = []
        ensure.return_value = SimpleNamespace(status="pending")
        attempt.return_value = 1

        def post(*_args):
            order.append("http")

        delivered.side_effect = lambda *_args: order.append("durable_state")
        worker = DeliveryWorker(http_post=post)
        result = worker.process(self.payload())
        order.append("ack")

        with self.subTest("4.1 - concluir chamada HTTP antes do estado durável"):
            self.assertEqual(order, ["http", "durable_state", "ack"])

        with self.subTest("4.2 - só confirmar ACK após persistência"):
            self.assertTrue(result.ack)

    @patch("features.delivery_worker.worker._mark_delivery_as_delivered")
    @patch("features.delivery_worker.worker._record_delivery_attempt")
    @patch("features.delivery_worker.worker._schedule_delivery_retry")
    @patch("features.delivery_worker.worker._get_or_create_delivery_record")
    def test_temporary_failure_is_scheduled_without_blocking_the_worker(self, ensure, mark_retry, attempt, delivered):
        ensure.return_value = SimpleNamespace(status="pending")
        attempt.return_value = 1
        from features.delivery_worker.worker import TemporaryDeliveryError
        http_post = Mock(side_effect=TemporaryDeliveryError("connection refused"))

        worker = DeliveryWorker(http_post=http_post)
        result = worker.process(self.payload("call-center-a"))

        with self.subTest("5.1 - confirmar a mensagem após falha temporária"):
            self.assertTrue(result.ack)

        with self.subTest("5.2 - agendar retry sem bloquear o worker"):
            http_post.assert_called_once()
            self.assertTrue(mark_retry.called)
            delivered.assert_not_called()

    def test_retry_due_survives_crash_during_http_and_is_retried_after_restart(self):
        due = datetime.now(timezone.utc) - timedelta(seconds=1)
        record = SimpleNamespace(status="retry_scheduled", next_retry_at=due)
        http_post = Mock(side_effect=[KeyboardInterrupt(), None])
        worker = DeliveryWorker(http_post=http_post)

        with patch("features.delivery_worker.worker._get_or_create_delivery_record", return_value=record), \
             patch("features.delivery_worker.worker._record_delivery_attempt", return_value=2), \
             patch("features.delivery_worker.worker._mark_delivery_as_delivered"):
            with self.assertRaises(KeyboardInterrupt):
                worker.process(self.payload())
            restarted_result = DeliveryWorker(http_post=http_post).process(self.payload())

        with self.subTest("6.1 - retomar retry pendente após reinício"):
            self.assertTrue(restarted_result.ack)
            self.assertEqual(http_post.call_count, 2)

    def test_recording_attempt_does_not_clear_due_retry_after_crash(self):
        due = datetime.now(timezone.utc) - timedelta(seconds=1)
        record = SimpleNamespace(attempts=1, last_error="timeout", next_retry_at=due)

        class Transaction:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        class Session:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def begin(self):
                return Transaction()

            def get(self, *_args):
                return record

        with patch.object(delivery_worker_module, "db_session", return_value=Session()):
            with self.subTest("7.1 - incrementar tentativa registrada"):
                self.assertEqual(delivery_worker_module._record_delivery_attempt("event-1"), 2)

        with self.subTest("7.2 - preservar horário do retry"):
            self.assertEqual(record.next_retry_at, due)

    @patch("features.delivery_worker.worker._get_or_create_delivery_record")
    def test_redelivery_of_delivered_event_does_not_post_again(self, ensure):
        ensure.return_value = SimpleNamespace(status="delivered")
        http_post = Mock()

        result = DeliveryWorker(http_post=http_post).process(self.payload())

        with self.subTest("8.1 - confirmar redelivery já entregue"):
            self.assertTrue(result.ack)

        with self.subTest("8.2 - não reenviar evento já entregue"):
            http_post.assert_not_called()

    def test_invalid_messages_are_not_retried(self):
        with self.subTest("9.1 - rejeitar payload incompleto"):
            with self.assertRaises(InvalidMessage):
                parse_message(b'{"event_id":"event-1"}')

        with self.subTest("9.2 - rejeitar call center desconhecido"):
            with self.assertRaises(InvalidMessage):
                parse_message(b'{"event_id":"event-1","lead_id":"l","distribution_id":"d","call_center_id":"unknown"}')

    @patch("features.delivery_worker.worker._mark_dead_letter_published")
    def test_final_failure_is_dead_lettered_before_ack(self, mark_dead_letter):
        calls = []
        publish_kwargs = []

        class Channel:
            def basic_publish(self, **kwargs):
                calls.append("dead_letter")
                publish_kwargs.append(kwargs)
                return None

            def basic_ack(self, **_kwargs):
                calls.append("ack")

            def basic_nack(self, **kwargs):
                calls.append(("nack", kwargs["requeue"]))

        DeliveryWorker._finish_ack(
            Channel(), 7,
            DeliveryResult(ack=True, dead_letter_reason="invalid destination"),
            b'{"event_id":"event-1"}',
        )

        self.assertEqual(calls, ["dead_letter", "ack"])
        self.assertTrue(publish_kwargs[0]["mandatory"])

    def test_dead_letter_publish_uses_confirmed_mandatory_delivery(self):
        calls = []

        class Channel:
            def basic_publish(self, **kwargs):
                calls.append(kwargs)
                return None

        DeliveryWorker()._dead_letter(Channel(), b"{}", "mensagem inválida")

        self.assertTrue(calls[0]["mandatory"])
        self.assertEqual(calls[0]["routing_key"], "lead.distributed.invalid")

    def test_dead_letter_connection_loss_does_not_escape_scheduler(self):
        connection = Mock(is_closed=False)
        connection.add_callback_threadsafe.side_effect = AMQPError("connection closed")
        worker = DeliveryWorker()
        worker._connection = connection

        worker._publish_retry_dead_letter(self.payload(), "falha permanente")

        connection.add_callback_threadsafe.assert_called_once()

    def test_nack_on_dead_letter_keeps_original_message(self):
        calls = []

        class Channel:
            def basic_publish(self, **_kwargs):
                calls.append("dead_letter")
                raise NackError([])

            def basic_nack(self, **kwargs):
                calls.append(("nack", kwargs["requeue"]))

        DeliveryWorker._finish_ack(
            Channel(), 7,
            DeliveryResult(ack=True, dead_letter_reason="falha permanente"),
            b'{"event_id":"event-1"}',
        )

        self.assertEqual(calls, ["dead_letter", ("nack", True)])

    def test_unroutable_dead_letter_keeps_original_message(self):
        calls = []

        class Channel:
            def basic_publish(self, **_kwargs):
                calls.append("dead_letter")
                raise UnroutableError([])

            def basic_nack(self, **kwargs):
                calls.append(("nack", kwargs["requeue"]))

        DeliveryWorker._finish_ack(
            Channel(), 7,
            DeliveryResult(ack=True, dead_letter_reason="falha permanente"),
            b'{"event_id":"event-1"}',
        )

        self.assertEqual(calls, ["dead_letter", ("nack", True)])

    @patch("features.delivery_worker.worker._mark_dead_letter_published")
    def test_failed_redelivery_acknowledges_after_dead_letter_confirmation(self, mark_dead_letter):
        calls = []

        class Channel:
            def basic_publish(self, **_kwargs):
                calls.append("dead_letter")
                return None

            def basic_ack(self, **_kwargs):
                calls.append("ack")

            def basic_nack(self, **_kwargs):
                calls.append("nack")

        DeliveryWorker._finish_ack(
            Channel(), 7,
            DeliveryResult(ack=False, requeue=True, dead_letter_reason="falha permanente"),
            b'{"event_id":"event-1"}',
        )

        self.assertEqual(calls, ["dead_letter", "ack"])
        mark_dead_letter.assert_called_once_with("event-1")


if __name__ == "__main__":
    unittest.main()
