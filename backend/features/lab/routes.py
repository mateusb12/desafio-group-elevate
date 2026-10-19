import json
import os
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from flask import jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy import func, select

from features.auth.permissions import admin_required
from features.dispatcher.models import CallCenter
from features.delivery_worker.models import DeliveryLeadToCallCenter
from features.leads.models import Distribution
from features.outbox.models import OutboxPendingDelivery
from features.outbox.publisher import check_rabbitmq
from shared.database import db_session

from . import lab_blueprint


CALL_CENTER_HEALTH = (
    ("Logicall", "call-center-a", "http://logicall:8101/health"),
    ("Salesbound", "call-center-b", "http://salesbound:8102/health"),
    ("AtendeMais", "call-center-c", "http://atendemais:8103/health"),
)
PROCESS_HEALTH = (
    (
        "Outbox Service",
        "outbox-service",
        os.getenv("OUTBOX_SERVICE_HEALTH_URL", "http://outbox-service:8091/health"),
    ),
    (
        "Worker",
        "delivery-worker",
        os.getenv("DELIVERY_WORKER_HEALTH_URL", "http://delivery-worker:8092/health"),
    ),
)
HEALTH_TIMEOUT_SECONDS = 0.8


def _positive_int(value: str | None, default: int, maximum: int) -> int:
    try:
        parsed = int(value) if value is not None else default
    except ValueError:
        return default
    return min(max(parsed, 1), maximum)


def _iso(value):
    return value.isoformat() if value is not None else None


@lab_blueprint.get("/deliveries")
@jwt_required()
@admin_required(forbidden_message="Acesso restrito ao administrador.")
def list_deliveries():
    page = _positive_int(request.args.get("page"), 1, 1000000)
    page_size = _positive_int(request.args.get("pageSize"), 20, 100)

    query = (
        select(OutboxPendingDelivery, Distribution, CallCenter, DeliveryLeadToCallCenter)
        .join(Distribution, Distribution.id == OutboxPendingDelivery.distribution_id)
        .join(CallCenter, CallCenter.id == Distribution.call_center_id)
        .outerjoin(DeliveryLeadToCallCenter, DeliveryLeadToCallCenter.event_id == OutboxPendingDelivery.id)
        .order_by(OutboxPendingDelivery.created_at.desc(), OutboxPendingDelivery.id.desc())
    )

    with db_session() as db:
        total = db.scalar(
            select(func.count()).select_from(OutboxPendingDelivery)
        ) or 0
        pending = db.scalar(
            select(func.count()).select_from(OutboxPendingDelivery).where(
                OutboxPendingDelivery.published_at.is_(None)
            )
        ) or 0
        published = total - pending
        delivery_total = db.scalar(select(func.count()).select_from(DeliveryLeadToCallCenter)) or 0
        delivered = db.scalar(select(func.count()).select_from(DeliveryLeadToCallCenter).where(DeliveryLeadToCallCenter.status == "delivered")) or 0
        initial_pending = db.scalar(select(func.count()).select_from(DeliveryLeadToCallCenter).where(DeliveryLeadToCallCenter.status == "pending")) or 0
        retrying = db.scalar(select(func.count()).select_from(DeliveryLeadToCallCenter).where(DeliveryLeadToCallCenter.status == "retry_scheduled")) or 0
        failed = db.scalar(select(func.count()).select_from(DeliveryLeadToCallCenter).where(DeliveryLeadToCallCenter.status == "failed")) or 0
        rows = db.execute(
            query.offset((page - 1) * page_size).limit(page_size)
        ).all()

    return jsonify(
        deliveries=[
            {
                "eventId": delivery.id,
                "eventType": delivery.event_type,
                "leadId": delivery.payload.get("lead_id"),
                "distributionId": delivery.distribution_id,
                "callCenter": center.name,
                "callCenterId": distribution.call_center_id,
                "createdAt": _iso(delivery.created_at),
                "publishedAt": _iso(delivery.published_at),
                "deliveryStatus": record.status if record is not None else None,
                "state": (
                    record.status if record is not None
                    else "published" if delivery.published_at is not None else "pending"
                ),
            }
            for delivery, distribution, center, record in rows
        ],
        counters={
            "total": total, "pending": pending, "published": published,
            "deliveryTotal": delivery_total, "initialPending": initial_pending,
            "delivered": delivered,
            "retrying": retrying, "failed": failed,
        },
        pagination={
            "page": page,
            "pageSize": page_size,
            "total": total,
            "totalPages": (total + page_size - 1) // page_size if total else 0,
        },
    )


def _check_call_center_health(name: str, call_center_id: str, url: str) -> dict:
    try:
        with urlopen(url, timeout=HEALTH_TIMEOUT_SECONDS) as response:
            status_code = response.status
            if not 200 <= status_code < 300:
                return {
                    "name": name,
                    "id": call_center_id,
                    "state": "unavailable",
                    "httpStatus": status_code,
                }
            read_body = getattr(response, "read", None)
            if read_body is None:
                return {
                    "name": name,
                    "id": call_center_id,
                    "state": "available",
                    "httpStatus": status_code,
                }
            body = read_body(4096)
            try:
                payload = json.loads(body)
            except (TypeError, ValueError):
                return {
                    "name": name,
                    "id": call_center_id,
                    "state": "unavailable",
                }
            accepted_count = payload.get("acceptedCount") if isinstance(payload, dict) else None
            if accepted_count is not None and (not isinstance(accepted_count, int) or accepted_count < 0):
                return {
                    "name": name,
                    "id": call_center_id,
                    "state": "unavailable",
                }
            result = {
                "name": name,
                "id": call_center_id,
                "state": "available",
                "httpStatus": status_code,
            }
            if accepted_count is not None:
                result["acceptedCount"] = accepted_count
            return result
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        return {
            "name": name,
            "id": call_center_id,
            "state": "unavailable",
            "error": str(error.reason) if isinstance(error, URLError) else str(error),
        }


def _check_internal_process_health(name: str, service_id: str, url: str) -> dict:
    try:
        with urlopen(url, timeout=HEALTH_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read(128))
            if response.status != 200 or not isinstance(payload, dict):
                return {"name": name, "id": service_id, "state": "unavailable"}
            processed_count = payload.get("processedCount")
            published_count = payload.get("publishedCount")
            marked_published_count = payload.get("markedPublishedCount")
            if (
                payload.get("status") != "ok"
                or (
                    processed_count is not None
                    and (not isinstance(processed_count, int) or processed_count < 0)
                )
                or any(
                    count is not None and (not isinstance(count, int) or count < 0)
                    for count in (published_count, marked_published_count)
                )
            ):
                return {"name": name, "id": service_id, "state": "unavailable"}
            result = {
                "name": name,
                "id": service_id,
                "state": "available",
                "httpStatus": response.status,
            }
            if processed_count is not None:
                result["processedCount"] = processed_count
            if published_count is not None:
                result["publishedCount"] = published_count
            if marked_published_count is not None:
                result["markedPublishedCount"] = marked_published_count
            return result
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return {"name": name, "id": service_id, "state": "unavailable"}


@lab_blueprint.get("/health")
@jwt_required()
@admin_required(forbidden_message="Acesso restrito ao administrador.")
def health():
    with ThreadPoolExecutor(max_workers=len(CALL_CENTER_HEALTH)) as executor:
        checks = list(executor.map(lambda item: _check_call_center_health(*item), CALL_CENTER_HEALTH))
    return jsonify(services=checks)


@lab_blueprint.get("/rabbitmq")
@jwt_required()
@admin_required(forbidden_message="Acesso restrito ao administrador.")
def rabbitmq_health():
    return jsonify(check_rabbitmq())


@lab_blueprint.get("/outbox-service/health")
@jwt_required()
@admin_required(forbidden_message="Acesso restrito ao administrador.")
def outbox_service_health():
    return jsonify(_check_internal_process_health(*PROCESS_HEALTH[0]))


@lab_blueprint.get("/delivery-worker/health")
@jwt_required()
@admin_required(forbidden_message="Acesso restrito ao administrador.")
def delivery_worker_health():
    return jsonify(_check_internal_process_health(*PROCESS_HEALTH[1]))
