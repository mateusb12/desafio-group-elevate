import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from flask import jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from auth.models import User, UserRole
from database import db_session
from dispatcher.service import choose_call_center
from dispatcher.models import CallCenter
from . import leads_blueprint
from .models import Contact, Event, Lead
from pydantic import ValidationError
from .schemas import LeadInput, validation_error_message

# Catálogo mínimo para os cenários atuais do LAB; futuramente virá do banco.
PRODUCTS = {'nutralean', 'curso-vendas', 'marketing-digital'}
FUNNELS = {'vsl-01', 'webinar-02', 'checkout-03'}


def validate_lead(body):
    try:
        clean = LeadInput.model_validate(body).model_dump()

        if clean['product'] not in PRODUCTS:
            return None, 'Produto desconhecido.'
        if clean['funnel'] not in FUNNELS:
            return None, 'Funil desconhecido.'

        return clean, None
    except ValidationError as exc:
        return None, validation_error_message(exc, body)


@leads_blueprint.post('')
def receive_lead():
    if not request.is_json:
        return jsonify(error='Envie Content-Type: application/json.'), 415

    clean, error = validate_lead(request.get_json(silent=True))
    if error:
        return jsonify(error=error), 400

    # Idempotência demonstrativa por conteúdo; futuramente usar ID da origem.
    canonical = json.dumps(clean, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    digest = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    new_id = str(uuid4())

    with db_session() as db, db.begin():
        # O e-mail normalizado identifica o contato.
        # Reenvios não sobrescrevem os dados do cadastro original.
        contact_id = db.scalar(
            insert(Contact)
            .values(
                id=str(uuid4()),
                name=clean['name'],
                email=clean['email'],
                phone=clean['phone'],
            )
            .on_conflict_do_nothing(index_elements=[Contact.email])
            .returning(Contact.id)
        )

        if contact_id is None:
            contact_id = db.scalar(
                select(Contact.id).where(Contact.email == clean['email'])
            )

        lead_data = {
            key: value
            for key, value in clean.items()
            if key not in ('name', 'email', 'phone')
        }

        created_id = db.scalar(
            insert(Lead)
            .values(
                id=new_id,
                contact_id=contact_id,
                call_center_id=choose_call_center(db),
                **lead_data,
                payload_hash=digest,
                status='new',
                received_at=datetime.now(timezone.utc),
            )
            .on_conflict_do_nothing(index_elements=[Lead.payload_hash])
            .returning(Lead.id)
        )

        lead_id = created_id or db.scalar(
            select(Lead.id).where(Lead.payload_hash == digest)
        )

        if created_id is not None:
            db.add(Event(
                lead_id=created_id,
                status='new',
                event_at=datetime.now(timezone.utc),
            ))

    return jsonify(id=lead_id, status='new', duplicate=created_id is None), (
        201 if created_id else 200
    )


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
def list_lab_leads():
    with db_session() as db:
        user = db.scalar(
            select(User).where(
                User.id == get_jwt_identity(),
                User.is_active.is_(True),
            )
        )

        if user is None or user.role != UserRole.ADMIN:
            return jsonify(error='Acesso restrito ao administrador.'), 403

        lead_ids = db.scalars(
            select(Lead.id)
            .order_by(Lead.received_at.desc())
            .limit(100)
        ).all()

    return jsonify(leads=lead_ids)


@leads_blueprint.delete('/lab')
@jwt_required()
def clear_lab_leads():
    with db_session() as db:
        user = db.scalar(
            select(User).where(
                User.id == get_jwt_identity(),
                User.is_active.is_(True),
            )
        )
        if user is None or user.role != UserRole.ADMIN:
            return jsonify(error='Apenas administradores podem limpar os leads do LAB.'), 403

        deleted = db.execute(delete(Lead)).rowcount or 0
        db.execute(delete(Contact))
        db.commit()

    return jsonify(deleted=deleted, status='ok')
