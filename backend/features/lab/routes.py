from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from flask import jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy import func, select

from features.auth.permissions import admin_required
from features.dispatcher.models import CallCenter
from features.leads.models import Distribution
from features.outbox.models import OutboxPendingDelivery
from shared.database import db_session

from . import lab_blueprint


CALL_CENTER_HEALTH = (
    ("Logicall", "call-center-a", "http://logicall:8101/health"),
    ("Salesbound", "call-center-b", "http://salesbound:8102/health"),
    ("AtendeMais", "call-center-c", "http://atendemais:8103/health"),
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
        select(OutboxPendingDelivery, Distribution, CallCenter)
        .join(Distribution, Distribution.id == OutboxPendingDelivery.distribution_id)
        .join(CallCenter, CallCenter.id == Distribution.call_center_id)
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
                "state": "published" if delivery.published_at is not None else "pending",
            }
            for delivery, distribution, center in rows
        ],
        counters={"total": total, "pending": pending, "published": published},
        pagination={
            "page": page,
            "pageSize": page_size,
            "total": total,
            "totalPages": (total + page_size - 1) // page_size if total else 0,
        },
    )


def _check_health(name: str, call_center_id: str, url: str) -> dict:
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
            return {
                "name": name,
                "id": call_center_id,
                "state": "available",
                "httpStatus": status_code,
            }
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        return {
            "name": name,
            "id": call_center_id,
            "state": "unavailable",
            "error": str(error.reason) if isinstance(error, URLError) else str(error),
        }


@lab_blueprint.get("/health")
@jwt_required()
@admin_required(forbidden_message="Acesso restrito ao administrador.")
def health():
    with ThreadPoolExecutor(max_workers=len(CALL_CENTER_HEALTH)) as executor:
        checks = list(executor.map(lambda item: _check_health(*item), CALL_CENTER_HEALTH))
    return jsonify(services=checks)
