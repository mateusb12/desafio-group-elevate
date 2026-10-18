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

from features.auth.models import User, UserRole
from shared.database import db_session
from features.leads.models import Event, Lead

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


def has_valid_webhook_key(configured_key, supplied_key):
    """Verifica se a chave enviada pelo call center é válida."""
    return bool(configured_key) and hmac.compare_digest(
        configured_key,
        supplied_key,
    )


def is_active_admin(db, user_id):
    """Verifica se o usuário está ativo e é administrador."""
    user = db.get(User, user_id)
    return bool(
        user
        and user.is_active
        and user.role == UserRole.ADMIN
    )


def get_locked_lead(db, lead_id):
    """Busca o lead e bloqueia sua linha na tabela SQL até o fim da transação."""
    return db.scalar(
        select(Lead)
        .where(Lead.id == lead_id)
        .with_for_update()
    )


def get_event_by_external_id(db, lead_id, external_id):
    """Busca um evento já registrado para este lead usando o external_id."""
    return db.scalar(
        select(Event).where(
            Event.lead_id == lead_id,
            Event.external_id == external_id,
        )
    )


def get_latest_event_time(db, lead_id):
    """Retorna o horário mais recente de evento do lead."""
    return db.scalar(
        select(func.max(Event.event_at))
        .where(Event.lead_id == lead_id)
    )


def is_newer_event(event_at, latest_event_time, lead_received_at):
    """Verifica se o evento recebido deve atualizar o status atual do lead."""
    comparison_time = latest_event_time or lead_received_at
    return comparison_time is None or event_at > comparison_time


def create_webhook_event(lead_id, payload, event_at):
    """Cadastra um evento a partir do payload recebido."""
    return Event(
        id=str(uuid4()),
        lead_id=lead_id,
        status=payload.status,
        external_id=payload.external_id,
        event_at=event_at,
    )


def validate_webhook_payload(body):
    """Valida o payload e retorna uma mensagem de erro, se houver."""
    try:
        return CallcenterWebhookInput.model_validate(body), None
    except ValidationError as exc:
        location = exc.errors()[0]['loc']
        field = location[0] if location else None
        messages = {
            'lead_id': 'lead_id é obrigatório.',
            'external_id': 'external_id é obrigatório (até 120 caracteres).',
            'status': 'Status desconhecido.',
            'event_at': 'event_at inválido: informe data e timezone.',
        }
        return None, messages.get(field, 'Payload inválido.')


@webhooks_blueprint.post('/callcenter')
@jwt_required(optional=True)
def callcenter_webhook():
    configured_key = os.getenv('CALLCENTER_WEBHOOK_KEY', '')
    supplied_key = request.headers.get('X-Webhook-Key', '')
    webhook_key_is_valid = has_valid_webhook_key(
        configured_key, supplied_key
    )

    if not webhook_key_is_valid:
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify(error='Webhook não autorizado.'), 401

        with db_session() as db:
            if not is_active_admin(db, user_id):
                return jsonify(
                    error='Apenas administradores podem simular webhooks.'
                ), 403

    if not request.is_json:
        return jsonify(error='Envie JSON.'), 415

    payload, validation_error = validate_webhook_payload(
        request.get_json(silent=True)
    )
    if validation_error:
        return jsonify(error=validation_error), 400

    lead_id = payload.lead_id
    external_id = payload.external_id
    status = payload.status
    event_at = payload.event_at.astimezone(timezone.utc)

    with db_session() as db, db.begin():
        lead = get_locked_lead(db, lead_id)

        if lead is None:
            return jsonify(error='Lead não encontrado.'), 404

        existing = get_event_by_external_id(db, lead_id, external_id)

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

        latest_event_time = get_latest_event_time(db, lead_id)
        applied = is_newer_event(
            event_at,
            latest_event_time,
            lead.received_at,
        )
        event = create_webhook_event(lead_id, payload, event_at)
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
