"""Publica a Outbox no RabbitMQ com semântica de entrega pelo menos uma vez."""

import json
import logging
import os
import signal
import sqlite3
import threading
from datetime import datetime, timezone

import pika
from pika.exceptions import AMQPError, NackError, UnroutableError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from shared.database import db_session
from shared.health_server import start_health_server

from features.leads import models as leads_models  # noqa: F401 - registra Distribution no metadata
from .models import OutboxPendingDelivery

LOGGER = logging.getLogger("outbox-publisher")
QUEUE_NAME = "lead.distributed"
INVALID_QUEUE_NAME = "lead.distributed.invalid"
HEALTH_PORT = int(os.getenv("OUTBOX_HEALTH_PORT", "8091"))
OUTBOX_DB_PATH = os.getenv("OUTBOX_DB_PATH", "/tmp/outbox-service.sqlite3")
SLOW_DELIVERY_INTERVAL_SECONDS = 0.25


class PublishError(RuntimeError):
    pass


class OutboxCounters:
    def __init__(self, database_path: str = OUTBOX_DB_PATH) -> None:
        self.database_path = database_path
        self._lock = threading.Lock()

    def _open(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self.database_path) or ".", exist_ok=True)
        connection = sqlite3.connect(self.database_path)
        connection.execute(
            "CREATE TABLE IF NOT EXISTS publication_events "
            "(event_id TEXT PRIMARY KEY, rabbit_published INTEGER NOT NULL DEFAULT 0, "
            "sql_marked INTEGER NOT NULL DEFAULT 0)"
        )
        connection.commit()
        return connection

    def _mark(self, event_id: str, column: str) -> None:
        with self._lock, self._open() as connection:
            connection.execute(
                "INSERT INTO publication_events(event_id, {column}) VALUES (?, 1) "
                "ON CONFLICT(event_id) DO UPDATE SET {column}=1".format(column=column),
                (event_id,),
            )
            connection.commit()

    def mark_rabbit_published(self, event_id: str) -> None:
        self._mark(event_id, "rabbit_published")

    def mark_sql_published(self, event_id: str) -> None:
        self._mark(event_id, "sql_marked")

    def health_status(self) -> dict:
        with self._lock, self._open() as connection:
            published, marked = connection.execute(
                "SELECT "
                "COALESCE(SUM(rabbit_published), 0), "
                "COALESCE(SUM(sql_marked), 0) "
                "FROM publication_events"
            ).fetchone()
        return {
            "status": "ok",
            "publishedCount": published,
            "markedPublishedCount": marked,
        }

    def reset(self) -> dict:
        with self._lock, self._open() as connection:
            deleted = connection.execute("DELETE FROM publication_events").rowcount
            connection.commit()
        return {"status": "ok", "deleted": deleted}


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


def open_confirmed_channel():
    connection = pika.BlockingConnection(rabbitmq_parameters())
    channel = connection.channel()
    channel.confirm_delivery()
    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    return connection, channel


def check_rabbitmq() -> dict:
    """Retorna apenas a disponibilidade; nunca expõe credenciais."""
    connection = None
    try:
        connection, channel = open_confirmed_channel()
        queue_state = channel.queue_declare(queue=QUEUE_NAME, passive=True)
        invalid_queue_state = channel.queue_declare(queue=INVALID_QUEUE_NAME, passive=True)
        channel.close()
        connection.close()
        return {
            "state": "available",
            "messageCount": queue_state.method.message_count,
            "deadLetterCount": invalid_queue_state.method.message_count,
        }
    except (AMQPError, OSError, TimeoutError) as error:
        if connection is not None and not connection.is_closed:
            connection.close()
        return {"state": "unavailable", "error": error.__class__.__name__}


def clear_delivery_dead_letter_queue() -> int:
    """Remove as mensagens persistidas na fila de falhas das entregas."""
    connection = None
    try:
        connection, channel = open_confirmed_channel()
        result = channel.queue_purge(queue=INVALID_QUEUE_NAME)
        channel.close()
        connection.close()
        return result.method.message_count
    except (AMQPError, OSError, TimeoutError):
        if connection is not None and not connection.is_closed:
            connection.close()
        raise


def pending_batch(limit: int) -> list[OutboxPendingDelivery]:
    with db_session() as db:
        return list(db.scalars(
            select(OutboxPendingDelivery)
            .where(OutboxPendingDelivery.published_at.is_(None))
            .order_by(OutboxPendingDelivery.created_at, OutboxPendingDelivery.id)
            .limit(limit)
        ).all())


def mark_published(event_id: str) -> None:
    with db_session() as db, db.begin():
        event = db.get(OutboxPendingDelivery, event_id)
        if event is not None and event.published_at is None:
            event.published_at = datetime.now(timezone.utc)


def publish_event(channel, event: OutboxPendingDelivery) -> None:
    properties = pika.BasicProperties(
        content_type="application/json",
        delivery_mode=2,
        message_id=event.id,
    )
    channel.basic_publish(
        exchange="",
        routing_key=QUEUE_NAME,
        body=json.dumps(event.payload, separators=(",", ":"), sort_keys=True).encode(),
        properties=properties,
        mandatory=True,
    )


def publish_outbox_batch(channel, events: list[OutboxPendingDelivery], memory: OutboxCounters | None = None) -> int:
    published = 0
    for event in events:
        try:
            publish_event(channel, event)
            if memory is not None:
                memory.mark_rabbit_published(event.id)
            mark_published(event.id)
            if memory is not None:
                memory.mark_sql_published(event.id)
            published += 1
            LOGGER.info("event_id=%s result=published_confirmed", event.id)
        except (NackError, UnroutableError, AMQPError, OSError, TimeoutError, PublishError) as error:
            LOGGER.warning("event_id=%s result=publish_rejected reason=%s", event.id, error.__class__.__name__)
            raise
        except SQLAlchemyError:
            LOGGER.exception("event_id=%s result=database_update_failed", event.id)
            raise
    return published


class Publisher:
    def __init__(self) -> None:
        self.stop_event = threading.Event()
        self.slow_delivery = os.getenv("LAB_DELIVERY_SPEED", "normal").lower() == "slow"
        self.batch_size = 1 if self.slow_delivery else int(os.getenv("OUTBOX_BATCH_SIZE", "10"))
        self.delivery_interval = SLOW_DELIVERY_INTERVAL_SECONDS if self.slow_delivery else 0
        self.poll_interval = float(os.getenv("OUTBOX_POLL_INTERVAL_SECONDS", "2"))
        self.retry_initial = float(os.getenv("OUTBOX_RETRY_INITIAL_SECONDS", "1"))
        self.retry_max = float(os.getenv("OUTBOX_RETRY_MAX_SECONDS", "30"))
        self.memory = OutboxCounters()

    def stop(self, _signum=None, _frame=None) -> None:
        LOGGER.info("shutdown_requested")
        self.stop_event.set()

    def run(self) -> None:
        connection = channel = None
        retry_delay = self.retry_initial
        LOGGER.info("started batch_size=%s queue=%s", self.batch_size, QUEUE_NAME)
        while not self.stop_event.is_set():
            if connection is None or connection.is_closed:
                try:
                    connection, channel = open_confirmed_channel()
                    retry_delay = self.retry_initial
                    LOGGER.info("broker_connected")
                except (AMQPError, OSError, TimeoutError) as error:
                    LOGGER.warning("broker_unavailable retry_seconds=%s reason=%s", retry_delay, error.__class__.__name__)
                    self.stop_event.wait(retry_delay)
                    retry_delay = min(retry_delay * 2, self.retry_max)
                    continue

            try:
                events = pending_batch(self.batch_size)
                if not events:
                    self.stop_event.wait(self.poll_interval)
                    continue
                publish_outbox_batch(channel, events, self.memory)
                if self.delivery_interval:
                    self.stop_event.wait(self.delivery_interval)
            except (NackError, UnroutableError, PublishError, AMQPError, OSError, TimeoutError):
                LOGGER.warning("broker_connection_lost")
                if connection is not None and not connection.is_closed:
                    connection.close()
                connection = channel = None
                self.stop_event.wait(retry_delay)
                retry_delay = min(retry_delay * 2, self.retry_max)
            except SQLAlchemyError:
                LOGGER.exception("database_operation_failed retry_seconds=%s", self.poll_interval)
                self.stop_event.wait(self.poll_interval)
        if connection is not None and not connection.is_closed:
            connection.close()
        LOGGER.info("stopped")


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")
    publisher = Publisher()
    health_server = start_health_server(HEALTH_PORT, publisher.memory.health_status, publisher.memory.reset)
    signal.signal(signal.SIGTERM, publisher.stop)
    signal.signal(signal.SIGINT, publisher.stop)
    try:
        publisher.run()
    finally:
        health_server.stop()


if __name__ == "__main__":
    main()
