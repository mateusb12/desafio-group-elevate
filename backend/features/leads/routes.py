from flask import jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import delete, or_, select
from datetime import datetime, timedelta, timezone

from features.auth.models import User, UserRole
from features.auth.permissions import admin_required
from shared.database import db_session
from shared.pagination import paginate_query
from .idempotency import normalize_idempotency_key
from features.dispatcher.models import CallCenter
from . import leads_blueprint
from .service import create_lead, update_lead_status
from .models import (
    Contact,
    Event,
    Lead,
)
from pydantic import ValidationError
from .schemas import (
    LeadInput,
    validate_lead_list_query,
    validate_lead_status_update,
    validation_error_message,
)

def validate_lead(body):
    try:
        clean = LeadInput.model_validate(body).model_dump()

        return clean, None
    except ValidationError as exc:
        return None, validation_error_message(exc, body)


def create_leads_base_query():
    return (
        select(Lead, Contact, CallCenter)
        .join(Contact, Lead.contact_id == Contact.id)
        .outerjoin(CallCenter, Lead.call_center_id == CallCenter.id)
        .order_by(Lead.received_at.desc(), Lead.id.desc())
    )


def get_active_user(db):
    return db.scalar(
        select(User).where(
            User.id == get_jwt_identity(),
            User.is_active.is_(True),
        )
    )


def get_user_visibility_filters(user):
    if user.role == UserRole.OPERATOR:
        if not user.call_center_id:
            return None
        return [Lead.call_center_id == user.call_center_id]
    return []


def serialize_lead_detail(lead, contact, call_center, events):
    return {
        'id': lead.id,
        'name': contact.name,
        'email': contact.email,
        'phone': contact.phone,
        'product': lead.product,
        'funnel': lead.funnel,
        'source': lead.source,
        'campaign': lead.campaign,
        'affiliateId': lead.affiliate_id,
        'utm': lead.utm,
        'callCenterId': lead.call_center_id or '',
        'callCenterName': call_center.name if call_center else 'Não distribuído',
        'status': lead.status,
        'receivedAt': lead.received_at.isoformat(),
        'events': [
            {
                'id': event.id,
                'status': event.status,
                'eventAt': event.event_at.isoformat(),
                'receivedAt': event.received_at.isoformat(),
            }
            for event in events
        ],
    }


def apply_frontend_filters_to_leads_query(
    query,
    frontend_filters,
):
    if frontend_filters.search:
        search_term = f'%{frontend_filters.search}%'
        query = query.where(or_(
            Lead.id.ilike(search_term),
            Contact.name.ilike(search_term),
            Contact.email.ilike(search_term),
            Contact.phone.ilike(search_term),
        ))
    if frontend_filters.product:
        query = query.where(Lead.product == frontend_filters.product)
    if frontend_filters.funnel:
        query = query.where(Lead.funnel == frontend_filters.funnel)
    if frontend_filters.source:
        query = query.where(Lead.source == frontend_filters.source)
    if frontend_filters.call_center_id:
        query = query.where(
            Lead.call_center_id == frontend_filters.call_center_id
        )
    if frontend_filters.status:
        query = query.where(Lead.status == frontend_filters.status)

    if frontend_filters.from_date:
        start = datetime.combine(
            frontend_filters.from_date,
            datetime.min.time(),
            tzinfo=timezone.utc,
        )
        query = query.where(Lead.received_at >= start)
    if frontend_filters.to_date:
        end = datetime.combine(
            frontend_filters.to_date,
            datetime.min.time(),
            tzinfo=timezone.utc,
        )
        query = query.where(Lead.received_at < end + timedelta(days=1))

    return query


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
        user = get_active_user(db)

        if user is None:
            return jsonify(error='Acesso não autorizado.'), 403

        frontend_filters, validation_error = validate_lead_list_query(
            request.args.to_dict()
        )
        if validation_error:
            return jsonify(error=validation_error), 400

        user_visibility_filters = get_user_visibility_filters(user)
        if user_visibility_filters is None:
            return jsonify(
                leads=[],
                filters={
                    'products': [],
                    'funnels': [],
                    'sources': [],
                    'callCenters': [],
                },
                pagination={
                    'page': frontend_filters.page,
                    'pageSize': frontend_filters.page_size,
                    'total': 0,
                    'totalPages': 0,
                },
            )

        leads_query_without_filters = create_leads_base_query()
        leads_query_with_frontend_filters = (
            apply_frontend_filters_to_leads_query(
                leads_query_without_filters,
                frontend_filters,
            )
        )
        leads_query_with_frontend_and_user_visibility_filters = (
            leads_query_with_frontend_filters.where(
                *user_visibility_filters
            )
        )

        products = db.scalars(
            select(Lead.product)
            .where(*user_visibility_filters)
            .distinct()
            .order_by(Lead.product)
        ).all()
        funnels = db.scalars(
            select(Lead.funnel)
            .where(*user_visibility_filters)
            .distinct()
            .order_by(Lead.funnel)
        ).all()
        sources = db.scalars(
            select(Lead.source)
            .where(*user_visibility_filters)
            .distinct()
            .order_by(Lead.source)
        ).all()
        call_centers = db.execute(
            select(CallCenter.id, CallCenter.name)
            .join(Lead, Lead.call_center_id == CallCenter.id)
            .where(*user_visibility_filters)
            .distinct()
            .order_by(CallCenter.name)
        ).all()

        rows, pagination = paginate_query(
            db,
            leads_query_with_frontend_and_user_visibility_filters,
            frontend_filters.page,
            frontend_filters.page_size,
        )

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

    return jsonify(
        leads=leads,
        filters={
            'products': products,
            'funnels': funnels,
            'sources': sources,
            'callCenters': [
                {'id': center_id, 'name': center_name}
                for center_id, center_name in call_centers
            ],
        },
        pagination=pagination,
    )


@leads_blueprint.get('/<lead_id>')
@jwt_required()
def get_lead_detail(lead_id):
    with db_session() as db:
        user = get_active_user(db)
        if user is None:
            return jsonify(error='Acesso não autorizado.'), 403

        user_visibility_filters = get_user_visibility_filters(user)
        if user_visibility_filters is None:
            return jsonify(error='Lead não encontrado.'), 404

        lead_row = db.execute(
            select(Lead, Contact, CallCenter)
            .join(Contact, Lead.contact_id == Contact.id)
            .outerjoin(CallCenter, Lead.call_center_id == CallCenter.id)
            .where(Lead.id == lead_id, *user_visibility_filters)
        ).first()
        if lead_row is None:
            return jsonify(error='Lead não encontrado.'), 404

        lead, contact, call_center = lead_row
        events = db.scalars(
            select(Event)
            .where(Event.lead_id == lead.id)
            .order_by(Event.event_at.desc(), Event.received_at.desc())
        ).all()

    return jsonify(serialize_lead_detail(lead, contact, call_center, events))


@leads_blueprint.patch('/<lead_id>/status')
@jwt_required()
def update_status(lead_id):
    body, validation_error = validate_lead_status_update(
        request.get_json(silent=True)
    )
    if validation_error:
        return jsonify(error=validation_error), 400

    with db_session() as db:
        user = get_active_user(db)
        if user is None:
            return jsonify(error='Acesso não autorizado.'), 403

        user_visibility_filters = get_user_visibility_filters(user)
        if user_visibility_filters is None:
            return jsonify(error='Lead não encontrado.'), 404

        result = update_lead_status(
            db,
            lead_id,
            body.status,
            user_visibility_filters,
        )
        if result.status_code == 200:
            db.commit()

    return jsonify(result.payload), result.status_code


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
