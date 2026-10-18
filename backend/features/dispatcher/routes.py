import math

from flask import jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy import select

from features.auth.permissions import admin_required
from shared.database import db_session

from . import dispatcher_blueprint
from .models import CallCenter


def serialize_call_center(call_center: CallCenter) -> dict[str, str | float]:
    return {
        "id": call_center.id,
        "name": call_center.name,
        "percentage": call_center.distribution_weight,
    }


def parse_allocations(body):
    if not isinstance(body, dict) or not isinstance(body.get("allocations"), list):
        return None, "Envie allocations como uma lista."

    allocations = body["allocations"]
    if not allocations:
        return None, "Informe pelo menos um call center."

    parsed = []
    seen_ids = set()
    for item in allocations:
        if not isinstance(item, dict):
            return None, "Cada alocação deve ser um objeto."

        center_id = item.get("id")
        percentage = item.get("percentage")
        if not isinstance(center_id, str) or not center_id.strip():
            return None, "Cada alocação precisa de um id válido."
        if isinstance(percentage, bool) or not isinstance(percentage, (int, float)):
            return None, "Cada porcentagem precisa ser numérica."
        if not math.isfinite(percentage) or percentage < 0:
            return None, "As porcentagens não podem ser negativas ou inválidas."
        if center_id in seen_ids:
            return None, "Não repita o mesmo call center."

        seen_ids.add(center_id)
        parsed.append((center_id, float(percentage)))

    if not math.isclose(sum(percentage for _, percentage in parsed), 100.0, abs_tol=1e-6):
        return None, "A soma das porcentagens precisa ser igual a 100%."

    return parsed, None


@dispatcher_blueprint.get("/weights")
@jwt_required()
@admin_required
def get_weights():
    with db_session() as db:
        call_centers = db.scalars(
            select(CallCenter).order_by(CallCenter.id)
        ).all()
        return jsonify(
            allocations=[serialize_call_center(call_center) for call_center in call_centers]
        )


@dispatcher_blueprint.put("/weights")
@jwt_required()
@admin_required
def update_weights():
    with db_session() as db:
        allocations, validation_error = parse_allocations(request.get_json(silent=True))
        if validation_error:
            return jsonify(error=validation_error), 400

        call_centers = db.scalars(select(CallCenter)).all()
        centers_by_id = {call_center.id: call_center for call_center in call_centers}
        submitted_ids = {center_id for center_id, _ in allocations}
        known_ids = set(centers_by_id)

        if submitted_ids != known_ids:
            return jsonify(error="Informe exatamente todos os call centers cadastrados."), 400

        for center_id, percentage in allocations:
            centers_by_id[center_id].distribution_weight = percentage

        db.commit()
        saved = sorted(call_centers, key=lambda call_center: call_center.id)
        return jsonify(
            allocations=[serialize_call_center(call_center) for call_center in saved]
        )
