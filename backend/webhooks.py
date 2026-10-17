# Group Elevate webhook callcenter
import hmac
import os
from datetime import timezone
from typing import Literal
from uuid import uuid4

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import func, select
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    ValidationError,
    field_validator,
)

from auth.models import User, UserRole
from database import db_session
from leads.models import Event, Lead

webhooks_blueprint = Blueprint(
    'webhooks', __name__, url_prefix='/api/webhooks'
)

class CallcenterWebhookInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    lead_id: StrictStr = Field(min_length=1)
    external_id: StrictStr = Field(min_length=1, max_length=120)
    status: Literal[
        'new', 'contacted', 'no_answer', 'callback',
        'qualified', 'sale', 'refund', 'invalid',
    ]
    event_at: AwareDatetime

    @field_validator('event_at', mode='before')
    @classmethod
    def require_iso_string(cls, value):
        if not isinstance(value, str):
            raise ValueError('Informe uma data ISO 8601.')
        return value


@webhooks_blueprint.post('/callcenter')
@jwt_required(optional=True)
def callcenter_webhook():
    configured_key = os.getenv('CALLCENTER_WEBHOOK_KEY', '')
    supplied_key = request.headers.get('X-Webhook-Key', '')
    via_key = bool(configured_key) and hmac.compare_digest(
        configured_key, supplied_key
    )

    if not via_key:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify(error='Webhook não autorizado.'), 401

        with db_session() as db:
            user = db.get(User, user_id)
            if not user or not user.is_active or user.role != UserRole.ADMIN:
                return jsonify(
                    error='Apenas administradores podem simular webhooks.'
                ), 403

    if not request.is_json:
        return jsonify(error='Envie JSON.'), 415

    try:
        payload = CallcenterWebhookInput.model_validate(
            request.get_json(silent=True)
        )
    except ValidationError as exc:
        location = exc.errors()[0]['loc']
        field = location[0] if location else None

        messages = {
            'lead_id': 'lead_id é obrigatório.',
            'external_id': 'external_id é obrigatório (até 120 caracteres).',
            'status': 'Status desconhecido.',
            'event_at': 'event_at inválido: informe data e timezone.',
        }

        return jsonify(
            error=messages.get(field, 'Payload inválido.')
        ), 400

    lead_id = payload.lead_id
    external_id = payload.external_id
    status = payload.status
    event_at = payload.event_at.astimezone(timezone.utc)

    with db_session() as db, db.begin():
        # Serializa webhooks concorrentes para o mesmo lead.
        lead = db.scalar(
            select(Lead)
            .where(Lead.id == lead_id)
            .with_for_update()
        )

        if lead is None:
            return jsonify(error='Lead não encontrado.'), 404

        existing = db.scalar(
            select(Event).where(
                Event.lead_id == lead_id,
                Event.external_id == external_id,
            )
        )

        if existing is not None:
            if existing.status != status or existing.event_at != event_at:
                return jsonify(
                    error='external_id reutilizado com dados diferentes.'
                ), 409

            return jsonify(
                id=existing.id,
                lead_id=lead_id,
                status=status,
                current_status=lead.status,
                duplicate=True,
                applied=False,
                out_of_order=False,
            ), 200

        latest_time = db.scalar(
            select(func.max(Event.event_at))
            .where(Event.lead_id == lead_id)
        )

        if latest_time is None:
            latest_time = lead.received_at

        applied = latest_time is None or event_at > latest_time

        event = Event(
            id=str(uuid4()),
            lead_id=lead_id,
            status=status,
            external_id=external_id,
            event_at=event_at,
        )
        db.add(event)

        if applied:
            lead.status = status

        current_status = lead.status

    return jsonify(
        id=event.id,
        lead_id=lead_id,
        status=status,
        current_status=current_status,
        duplicate=False,
        applied=applied,
        out_of_order=not applied,
    ), 201
