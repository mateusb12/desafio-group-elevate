from flask import jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy import select

from features.auth.permissions import admin_required
from shared.database import db_session

from . import dispatcher_blueprint
from .models import CallCenter
from .schemas import validate_weights

def serialize_call_center(call_center: CallCenter) -> dict[str, str | float]:
    return {
        "id": call_center.id,
        "name": call_center.name,
        "percentage": call_center.distribution_weight,
    }


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
        allocations, validation_error = validate_weights(request.get_json(silent=True))
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
