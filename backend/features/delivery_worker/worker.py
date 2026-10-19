"""Consumidor RabbitMQ com entrega pelo menos uma vez e tentativas HTTP limitadas."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import signal
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pika
from pika.exceptions import AMQPError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from shared.database import db_session
from shared.health_server import start_health_server

from .models import DeliveryLeadToCallCenter
from features.outbox.models import OutboxPendingDelivery

LOGGER = logging.getLogger("delivery-worker")
QUEUE_NAME = "lead.distributed"
INVALID_QUEUE_NAME = "lead.distributed.invalid"
HEALTH_PORT = int(os.getenv("DELIVERY_WORKER_HEALTH_PORT", "8092"))
WORKER_DB_PATH = os.getenv("DELIVERY_WORKER_DB_PATH", "/tmp/delivery-worker.sqlite3")
CALL_CENTER_URLS = {
    "call-center-a": os.getenv("LOGICALL_URL", "http://logicall:8101/leads"),
    "call-center-b": os.getenv("SALESBOUND_URL", "http://salesbound:8102/leads"),
    "call-center-c": os.getenv("ATENDEMAIS_URL", "http://atendemais:8103/leads"),
}


class InvalidMessage(ValueError):
    pass


class PermanentDeliveryError(RuntimeError):
    pass


class TemporaryDeliveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class DeliveryResult:
    ack: bool
    requeue: bool = False
    dead_letter_reason: str | None = None


def rabbitmq_parameters() -> pika.ConnectionParameters:
    return pika.ConnectionParameters(
        host=os.getenv("RABBITMQ_HOST", "rabbitmq"),
        port=int(os.getenv("RABBITMQ_PORT", "5672")),
        virtual_host=os.getenv("RABBITMQ_VHOST", "/"),
        credentials=pika.PlainCredentials(
            os.getenv("RABBITMQ_USER", "elevate"),
            os.getenv("RABBITMQ_PASSWORD", "elevate-local-only"),
        ),
        connection_attempts=1,
        socket_timeout=float(os.getenv("RABBITMQ_CONNECTION_TIMEOUT_SECONDS", "2")),
        blocked_connection_timeout=2,
        heartbeat=30,
    )


def parse_message(body: bytes) -> dict:
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InvalidMessage("JSON inválido") from error
    if not isinstance(payload, dict):
        raise InvalidMessage("payload deve ser um objeto JSON")
    required = ("event_id", "lead_id", "distribution_id", "call_center_id")
    if any(not isinstance(payload.get(key), str) or not payload[key].strip() for key in required):
        raise InvalidMessage("event_id, lead_id, distribution_id e call_center_id são obrigatórios")
    if payload["call_center_id"] not in CALL_CENTER_URLS:
        raise InvalidMessage(f"call_center_id desconhecido: {payload['call_center_id']}")
    return payload


def _get_or_create_delivery_record(payload: dict) -> DeliveryLeadToCallCenter:
    with db_session() as db, db.begin():
        record = db.get(DeliveryLeadToCallCenter, payload["event_id"])
        if record is None:
            record = DeliveryLeadToCallCenter(
                event_id=payload["event_id"],
                lead_id=payload["lead_id"],
                call_center_id=payload["call_center_id"],
                status="pending",
            )
            db.add(record)
            db.flush()
        return record


def _record_delivery_attempt(event_id: str, error: str | None = None) -> int:
    with db_session() as db, db.begin():
        record = db.get(DeliveryLeadToCallCenter, event_id)
        if record is None:
            raise SQLAlchemyError("registro de entrega desapareceu")
        record.attempts += 1
        record.last_error = error
        return record.attempts


def _mark_delivery_as_delivered(event_id: str) -> None:
    with db_session() as db, db.begin():
        record = db.get(DeliveryLeadToCallCenter, event_id)
        if record is None:
            raise SQLAlchemyError("registro de entrega desapareceu")
        record.status = "delivered"
        record.last_error = None
        record.next_retry_at = None
        record.delivered_at = datetime.now(timezone.utc)


def _schedule_delivery_retry(event_id: str, error: str, delay: float) -> None:
    with db_session() as db, db.begin():
        record = db.get(DeliveryLeadToCallCenter, event_id)
        if record is None:
            raise SQLAlchemyError("registro de entrega desapareceu")
        record.last_error = error[:500]
        record.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
        record.status = "retry_scheduled"


def _due_retries(limit: int) -> list[dict]:
    """Carrega retries vencidos junto com o payload durável da Outbox."""
    with db_session() as db:
        rows = db.execute(
            select(DeliveryLeadToCallCenter, OutboxPendingDelivery.payload)
            .join(OutboxPendingDelivery, OutboxPendingDelivery.id == DeliveryLeadToCallCenter.event_id)
            .where(
                DeliveryLeadToCallCenter.status == "retry_scheduled",
                DeliveryLeadToCallCenter.next_retry_at <= datetime.now(timezone.utc),
            )
            .order_by(DeliveryLeadToCallCenter.next_retry_at, DeliveryLeadToCallCenter.event_id)
            .limit(limit)
        ).all()
        return [payload for _record, payload in rows]


def _failed_deliveries_without_confirmed_dead_letter(limit: int) -> list[dict]:
    """Carrega falhas cujo encaminhamento ainda não foi confirmado."""
    with db_session() as db:
        rows = db.execute(
            select(DeliveryLeadToCallCenter, OutboxPendingDelivery.payload)
            .join(OutboxPendingDelivery, OutboxPendingDelivery.id == DeliveryLeadToCallCenter.event_id)
            .where(
                DeliveryLeadToCallCenter.status == "failed",
                DeliveryLeadToCallCenter.dead_letter_published_at.is_(None),
            )
            .order_by(DeliveryLeadToCallCenter.failed_at, DeliveryLeadToCallCenter.event_id)
            .limit(limit)
        ).all()
        return [
            {"payload": payload, "reason": record.last_error or "falha permanente"}
            for record, payload in rows
        ]


def _mark_dead_letter_published(event_id: str) -> None:
    with db_session() as db, db.begin():
        record = db.get(DeliveryLeadToCallCenter, event_id)
        if record is not None:
            record.dead_letter_published_at = datetime.now(timezone.utc)


def _mark_delivery_as_failed(event_id: str, error: str) -> None:
    with db_session() as db, db.begin():
        record = db.get(DeliveryLeadToCallCenter, event_id)
        if record is None:
            raise SQLAlchemyError("registro de entrega desapareceu")
        record.status = "failed"
        record.last_error = error[:500]
        record.failed_at = datetime.now(timezone.utc)
        record.next_retry_at = None


def post_lead_to_call_center(url: str, payload: dict, timeout: float) -> None:
    body = json.dumps(
        {key: payload[key] for key in ("event_id", "lead_id", "distribution_id", "call_center_id")},
        separators=(",", ":"),
    ).encode()
    request = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            if not 200 <= response.status < 300:
                raise TemporaryDeliveryError(f"HTTP {response.status}")
    except HTTPError as error:
        if 400 <= error.code < 500 and error.code not in (408, 429):
            raise PermanentDeliveryError(f"HTTP {error.code}") from error
        raise TemporaryDeliveryError(f"HTTP {error.code}") from error
    except (URLError, TimeoutError, OSError) as error:
        raise TemporaryDeliveryError(str(error)) from error


class DeliveryWorker:
    def __init__(self, http_post=post_lead_to_call_center) -> None:
        self.stop_event = threading.Event()
        self.http_post = http_post
        self.http_timeout = float(os.getenv("DELIVERY_HTTP_TIMEOUT_SECONDS", "3"))
        self.max_attempts = int(os.getenv("DELIVERY_MAX_ATTEMPTS", "10"))
        self.retry_initial = float(os.getenv("DELIVERY_RETRY_INITIAL_SECONDS", "1"))
        self.retry_max = float(os.getenv("DELIVERY_RETRY_MAX_SECONDS", "30"))
        self.workers = int(os.getenv("DELIVERY_WORKERS", "8"))
        self.scheduler_interval = float(os.getenv("DELIVERY_SCHEDULER_INTERVAL_SECONDS", "1"))
        self.database_path = os.getenv("DELIVERY_WORKER_DB_PATH", WORKER_DB_PATH)
        self._connection = None
        self._channel = None
        self._processed_lock = threading.Lock()

    def _open_worker_processed_events_db(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self.database_path) or ".", exist_ok=True)
        connection = sqlite3.connect(self.database_path)
        connection.execute(
            "CREATE TABLE IF NOT EXISTS processed_events "
            "(event_id TEXT PRIMARY KEY, processed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        connection.commit()
        return connection

    def health_status(self) -> dict:
        """Retorna liveness e a quantidade persistida de eventos processados."""
        with self._processed_lock:
            with self._open_worker_processed_events_db() as connection:
                count = connection.execute("SELECT COUNT(*) FROM processed_events").fetchone()[0]
            return {"status": "ok", "processedCount": count}

    def _mark_processed(self, event_id: str) -> None:
        with self._processed_lock:
            with self._open_worker_processed_events_db() as connection:
                connection.execute("INSERT OR IGNORE INTO processed_events(event_id) VALUES (?)", (event_id,))
                connection.commit()

    def reset_processed(self) -> dict:
        with self._processed_lock:
            with self._open_worker_processed_events_db() as connection:
                deleted = connection.execute("DELETE FROM processed_events").rowcount
                connection.commit()
            return {"status": "ok", "deleted": deleted}

    def stop(self, _signum=None, _frame=None) -> None:
        LOGGER.info("shutdown_requested")
        self.stop_event.set()
        connection = self._connection
        channel = self._channel
        if connection is not None and channel is not None and not connection.is_closed:
            try:
                connection.add_callback_threadsafe(channel.stop_consuming)
            except (AMQPError, OSError):
                LOGGER.debug("consumo já estava encerrado", exc_info=True)

    def process(self, payload: dict) -> DeliveryResult:
        record = _get_or_create_delivery_record(payload)
        if record.status == "delivered":
            LOGGER.info("event_id=%s result=%s duplicate=true", payload["event_id"], record.status)
            return DeliveryResult(ack=True)
        if record.status == "failed":
            if record.dead_letter_published_at is not None:
                return DeliveryResult(ack=True)
            return DeliveryResult(
                ack=False,
                requeue=True,
                dead_letter_reason=record.last_error or "falha permanente",
            )
        if record.status == "retry_scheduled" and record.next_retry_at is not None:
            if record.next_retry_at > datetime.now(timezone.utc):
                return DeliveryResult(ack=True)

        url = CALL_CENTER_URLS[payload["call_center_id"]]
        try:
            attempt = _record_delivery_attempt(payload["event_id"])
            self.http_post(url, payload, self.http_timeout)
            _mark_delivery_as_delivered(payload["event_id"])
            LOGGER.info("event_id=%s call_center_id=%s result=delivered attempt=%s", payload["event_id"], payload["call_center_id"], attempt)
            return DeliveryResult(ack=True)
        except PermanentDeliveryError as error:
            _mark_delivery_as_failed(payload["event_id"], str(error))
            LOGGER.error("event_id=%s result=failed_final reason=%s", payload["event_id"], error)
            return DeliveryResult(ack=True, dead_letter_reason=str(error))
        except TemporaryDeliveryError as error:
            if attempt >= self.max_attempts:
                _mark_delivery_as_failed(payload["event_id"], str(error))
                LOGGER.error("event_id=%s result=failed_final attempts=%s reason=%s", payload["event_id"], attempt, error)
                return DeliveryResult(ack=True, dead_letter_reason=str(error))
            delay = min(self.retry_initial * (2 ** (attempt - 1)), self.retry_max)
            _schedule_delivery_retry(payload["event_id"], str(error), delay)
            LOGGER.warning("event_id=%s call_center_id=%s result=retry_scheduled retry_seconds=%s attempt=%s reason=%s", payload["event_id"], payload["call_center_id"], delay, attempt, error)
            return DeliveryResult(ack=True)
        except SQLAlchemyError:
            LOGGER.exception("event_id=%s result=database_error", payload["event_id"])
            return DeliveryResult(ack=False, requeue=True)

    def _declare(self, channel) -> None:
        channel.queue_declare(queue=QUEUE_NAME, durable=True)
        channel.queue_declare(queue=INVALID_QUEUE_NAME, durable=True)
        channel.confirm_delivery()
        channel.basic_qos(prefetch_count=self.workers)

    def _dead_letter(self, channel, body: bytes, reason: str) -> None:
        payload = json.dumps({"reason": reason, "body": body.decode("utf-8", errors="replace")}).encode()
        channel.basic_publish(
            exchange="", routing_key=INVALID_QUEUE_NAME, body=payload,
            properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
            mandatory=True,
        )

    @staticmethod
    def _payload_event_id(payload: dict) -> str:
        return payload["event_id"]

    def _scheduler_loop(self, executor: ThreadPoolExecutor) -> None:
        """Submete somente tentativas vencidas; nunca espera dentro de uma thread de trabalho."""
        scheduled: set[str] = set()
        while not self.stop_event.wait(self.scheduler_interval):
            try:
                for payload in _due_retries(self.workers):
                    event_id = self._payload_event_id(payload)
                    if event_id in scheduled:
                        continue
                    scheduled.add(event_id)
                    future = executor.submit(self.process, payload)

                    def finish(done, event_id=event_id, payload=payload):
                        scheduled.discard(event_id)
                        try:
                            result = done.result()
                            if result.dead_letter_reason is not None:
                                self._publish_retry_dead_letter(
                                    payload, result.dead_letter_reason
                                )
                        except Exception:
                            LOGGER.exception("event_id=%s result=retry_worker_error", event_id)

                    future.add_done_callback(finish)

                for failed in _failed_deliveries_without_confirmed_dead_letter(self.workers):
                    self._publish_retry_dead_letter(failed["payload"], failed["reason"])
            except SQLAlchemyError:
                LOGGER.exception("retry_scheduler_database_error")

    def _publish_retry_dead_letter(self, payload: dict, reason: str) -> None:
        connection = self._connection
        if connection is None or connection.is_closed:
            return
        body = json.dumps(payload, separators=(",", ":")).encode()

        def publish() -> None:
            try:
                self._dead_letter(self._channel, body, reason)
                _mark_dead_letter_published(payload["event_id"])
            except (AMQPError, OSError, TimeoutError, SQLAlchemyError):
                LOGGER.warning("event_id=%s result=dead_letter_pending", payload["event_id"], exc_info=True)

        try:
            connection.add_callback_threadsafe(publish)
        except (AMQPError, OSError, TimeoutError):
            LOGGER.info(
                "event_id=%s result=dead_letter_connection_closed",
                payload["event_id"],
            )

    def run(self) -> None:
        retry_delay = 1.0
        executor = ThreadPoolExecutor(max_workers=self.workers, thread_name_prefix="delivery")
        scheduler = threading.Thread(
            target=self._scheduler_loop, args=(executor,), name="delivery-retry-scheduler", daemon=True
        )
        scheduler.start()
        LOGGER.info("started queue=%s workers=%s max_attempts=%s", QUEUE_NAME, self.workers, self.max_attempts)
        try:
            while not self.stop_event.is_set():
                connection = None
                try:
                    connection = pika.BlockingConnection(rabbitmq_parameters())
                    channel = connection.channel()
                    self._connection = connection
                    self._channel = channel
                    self._declare(channel)
                    retry_delay = 1.0
                    LOGGER.info("broker_connected")

                    def callback(ch, method, _properties, body):
                        try:
                            payload = parse_message(body)
                        except InvalidMessage as error:
                            try:
                                self._dead_letter(ch, body, str(error))
                                ch.basic_ack(method.delivery_tag)
                            except (AMQPError, OSError, TimeoutError):
                                ch.basic_nack(method.delivery_tag, requeue=True)
                            LOGGER.error("delivery_tag=%s result=invalid_message reason=%s", method.delivery_tag, error)
                            return
                        future = executor.submit(self.process, payload)

                        def finish(done):
                            try:
                                result = done.result()
                                if result.ack or result.dead_letter_reason is not None:
                                    self._mark_processed(payload["event_id"])
                            except Exception:
                                LOGGER.exception("event_id=%s result=unhandled_worker_error", payload["event_id"])
                                result = DeliveryResult(ack=False, requeue=True)
                            try:
                                connection.add_callback_threadsafe(
                                    lambda: self._finish_ack(ch, method.delivery_tag, result, body)
                                )
                            except (AMQPError, OSError):
                                LOGGER.info("delivery_tag=%s result=connection_closed", method.delivery_tag)

                        future.add_done_callback(finish)

                    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback, auto_ack=False)
                    channel.start_consuming()
                except (AMQPError, OSError, TimeoutError) as error:
                    LOGGER.warning("broker_unavailable retry_seconds=%s reason=%s", retry_delay, error.__class__.__name__)
                    self.stop_event.wait(retry_delay)
                    retry_delay = min(retry_delay * 2, 30)
                finally:
                    self._connection = None
                    self._channel = None
                    if connection is not None and not connection.is_closed:
                        connection.close()
        finally:
            self.stop_event.set()
            scheduler.join(timeout=max(self.scheduler_interval * 2, 1))
            executor.shutdown(wait=True)
            LOGGER.info("stopped")

    @staticmethod
    def _finish_ack(channel, delivery_tag: int, result: DeliveryResult, body: bytes) -> None:
        try:
            if result.dead_letter_reason is not None:
                payload = json.dumps({
                    "reason": result.dead_letter_reason,
                    "body": body.decode("utf-8", errors="replace"),
                }).encode()
                channel.basic_publish(
                    exchange="", routing_key=INVALID_QUEUE_NAME, body=payload,
                    properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
                    mandatory=True,
                )
                try:
                    failed_payload = json.loads(body)
                    if isinstance(failed_payload, dict) and isinstance(failed_payload.get("event_id"), str):
                        _mark_dead_letter_published(failed_payload["event_id"])
                except (json.JSONDecodeError, SQLAlchemyError):
                    LOGGER.warning("não foi possível registrar confirmação da fila de falhas", exc_info=True)
            if result.ack or result.dead_letter_reason is not None:
                channel.basic_ack(delivery_tag=delivery_tag)
            else:
                channel.basic_nack(delivery_tag=delivery_tag, requeue=result.requeue)
        except (AMQPError, OSError, TimeoutError):
            channel.basic_nack(delivery_tag=delivery_tag, requeue=True)


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")
    worker = DeliveryWorker()
    health_server = start_health_server(HEALTH_PORT, worker.health_status, worker.reset_processed)
    signal.signal(signal.SIGTERM, worker.stop)
    signal.signal(signal.SIGINT, worker.stop)
    try:
        worker.run()
    finally:
        health_server.stop()


if __name__ == "__main__":
    main()
