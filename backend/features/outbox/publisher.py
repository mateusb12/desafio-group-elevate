"""Publica a Outbox no RabbitMQ com semântica at-least-once."""

import json
import logging
import os
import signal
import threading
from datetime import datetime, timezone

import pika
from pika.exceptions import AMQPError, NackError, UnroutableError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from shared.database import db_session

from features.leads import models as leads_models  # noqa: F401 - registra Distribution no metadata
from .models import OutboxPendingDelivery

LOGGER = logging.getLogger("outbox-publisher")
QUEUE_NAME = "lead.distributed"


class PublishError(RuntimeError):
    pass


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
    """Retorna apenas disponibilidade; nunca expõe credenciais."""
    connection = None
    try:
        connection, channel = open_confirmed_channel()
        channel.close()
        connection.close()
        return {"state": "available"}
    except (AMQPError, OSError, TimeoutError) as error:
        if connection is not None and not connection.is_closed:
            connection.close()
        return {"state": "unavailable", "error": error.__class__.__name__}


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
    confirmed = channel.basic_publish(
        exchange="",
        routing_key=QUEUE_NAME,
        body=json.dumps(event.payload, separators=(",", ":"), sort_keys=True).encode(),
        properties=properties,
        mandatory=True,
    )
    if confirmed is False:
        raise PublishError("broker did not confirm the message")


def process_batch(channel, events: list[OutboxPendingDelivery]) -> int:
    published = 0
    for event in events:
        try:
            publish_event(channel, event)
            mark_published(event.id)
            published += 1
            LOGGER.info("event_id=%s result=published_confirmed", event.id)
        except (NackError, UnroutableError, PublishError) as error:
            LOGGER.warning("event_id=%s result=publish_rejected reason=%s", event.id, error.__class__.__name__)
            raise
        except SQLAlchemyError:
            LOGGER.exception("event_id=%s result=database_update_failed", event.id)
            raise
    return published


class Publisher:
    def __init__(self) -> None:
        self.stop_event = threading.Event()
        self.batch_size = int(os.getenv("OUTBOX_BATCH_SIZE", "10"))
        self.poll_interval = float(os.getenv("OUTBOX_POLL_INTERVAL_SECONDS", "2"))
        self.retry_initial = float(os.getenv("OUTBOX_RETRY_INITIAL_SECONDS", "1"))
        self.retry_max = float(os.getenv("OUTBOX_RETRY_MAX_SECONDS", "30"))

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
                process_batch(channel, events)
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
    signal.signal(signal.SIGTERM, publisher.stop)
    signal.signal(signal.SIGINT, publisher.stop)
    publisher.run()


if __name__ == "__main__":
    main()
