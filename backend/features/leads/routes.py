import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from flask import jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from features.auth.models import User, UserRole
from shared.database import db_session
from .idempotency import (
    acquire_idempotency_lock,
    normalize_idempotency_key,
    calculate_payload_hash,
)
from features.dispatcher.service import choose_call_center
from features.dispatcher.models import CallCenter
from . import leads_blueprint
from .affiliates import get_or_create_affiliate
from .models import (
    Contact,
    Distribution,
    Event,
    Funnel,
    Lead,
    Product,
    ProductFunnel,
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

    payload_hash = calculate_payload_hash(clean)

    with db_session() as db, db.begin():
        # Requisições com a mesma chave esperam umas pelas outras.
        acquire_idempotency_lock(db, key)

        existing = db.scalar(
            select(Lead).where(Lead.idempotency_key == key)
        )

        if existing is not None:
            if existing.payload_hash != payload_hash:
                return jsonify(
                    error='Idempotency-Key reutilizada com dados diferentes.'
                ), 409

            return jsonify(
                id=existing.id,
                status='new',
                duplicate=True,
            ), 200

        product_exists = db.scalar(
            select(Product.code).where(
                Product.code == clean['product'],
            )
        )
        if product_exists is None:
            return jsonify(error='Produto desconhecido.'), 400

        funnel_exists = db.scalar(
            select(Funnel.code).where(
                Funnel.code == clean['funnel'],
            )
        )
        if funnel_exists is None:
            return jsonify(error='Funil desconhecido.'), 400

        valid_association = db.scalar(
            select(ProductFunnel.product_code)
            .where(
                ProductFunnel.product_code == clean['product'],
                ProductFunnel.funnel_code == clean['funnel'],
            )
        )
        if valid_association is None:
            return jsonify(error='Combinação produto/funil inválida.'), 400

        get_or_create_affiliate(db, clean['affiliate_id'])

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
                select(Contact.id).where(
                    Contact.email == clean['email']
                )
            )

        lead_data = {
            field: value
            for field, value in clean.items()
            if field not in ('name', 'email', 'phone')
        }

        lead_id = str(uuid4())
        received_at = datetime.now(timezone.utc)
        call_center_id = choose_call_center(db)

        db.add(Lead(
            id=lead_id,
            contact_id=contact_id,
            call_center_id=call_center_id,
            idempotency_key=key,
            payload_hash=payload_hash,
            status='new',
            received_at=received_at,
            **lead_data,
        ))

        db.flush()

        db.add(Distribution(
            id=str(uuid4()),
            lead_id=lead_id,
            call_center_id=call_center_id,
            assigned_at=received_at,
            reason='initial',
        ))

        db.add(Event(
            lead_id=lead_id,
            status='new',
            event_at=datetime.now(timezone.utc),
        ))

    return jsonify(
        id=lead_id,
        status='new',
        duplicate=False,
    ), 201


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
