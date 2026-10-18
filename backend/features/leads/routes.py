from flask import jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import delete, select

from features.auth.models import User, UserRole
from features.auth.permissions import admin_required
from shared.database import db_session
from .idempotency import normalize_idempotency_key
from features.dispatcher.models import CallCenter
from . import leads_blueprint
from .service import create_lead
from .models import (
    Contact,
    Lead,
)
from pydantic import ValidationError
from .schemas import LeadInput, validation_error_message

def validate_lead(body):
    try:
        clean = LeadInput.model_validate(body).model_dump()

        return clean, None
    except ValidationError as exc:
        return None, validation_error_message(exc, body)


@leads_blueprint.post('')
def receive_lead():
    if not request.is_json:
        return jsonify(
            error='Envie Content-Type: application/json.'
        ), 415

    key = normalize_idempotency_key(
        request.headers.get('Idempotency-Key')
    )

    if key is None:
        return jsonify(
            error='Idempotency-Key obrigatória: informe um UUID v4.'
        ), 400

    clean, error = validate_lead(request.get_json(silent=True))
    if error:
        return jsonify(error=error), 400

    with db_session() as db:
        result = create_lead(db, clean, key)

    return jsonify(result.payload), result.status_code


@leads_blueprint.get('')
@jwt_required()
def list_leads():
    with db_session() as db:
        user = db.scalar(
            select(User).where(
                User.id == get_jwt_identity(),
                User.is_active.is_(True),
            )
        )

        if user is None:
            return jsonify(error='Acesso não autorizado.'), 403

        query = (
            select(Lead, Contact, CallCenter)
            .join(Contact, Lead.contact_id == Contact.id)
            .outerjoin(CallCenter, Lead.call_center_id == CallCenter.id)
            .order_by(Lead.received_at.desc(), Lead.id.desc())
        )

        if user.role == UserRole.OPERATOR:
            if not user.call_center_id:
                return jsonify(leads=[])

            query = query.where(
                Lead.call_center_id == user.call_center_id
            )

        rows = db.execute(query).all()

        leads = [
            {
                'id': lead.id,
                'name': contact.name,
                'email': contact.email,
                'phone': contact.phone,
                'product': lead.product,
                'funnel': lead.funnel,
                'source': lead.source,
                'campaign': lead.campaign,
                'callCenterId': lead.call_center_id or '',
                'callCenterName': center.name if center else 'Não distribuído',
                'status': lead.status,
                'receivedAt': lead.received_at.isoformat(),
            }
            for lead, contact, center in rows
        ]

    return jsonify(leads=leads)


@leads_blueprint.get('/lab')
@jwt_required()
@admin_required(forbidden_message='Acesso restrito ao administrador.')
def list_lab_leads():
    with db_session() as db:
        lead_ids = db.scalars(
            select(Lead.id)
            .order_by(Lead.received_at.desc())
            .limit(100)
        ).all()

    return jsonify(leads=lead_ids)


@leads_blueprint.delete('/lab')
@jwt_required()
@admin_required(forbidden_message='Apenas administradores podem limpar os leads do LAB.')
def clear_lab_leads():
    with db_session() as db:
        deleted = db.execute(delete(Lead)).rowcount or 0
        db.execute(delete(Contact))
        db.commit()

    return jsonify(deleted=deleted, status='ok')
