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
from . import leads_blueprint
from .models import Lead
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
    statement = (
        insert(Lead)
        .values(
            id=new_id, **clean, payload_hash=digest, status='new',
            received_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_nothing(index_elements=[Lead.payload_hash])
        .returning(Lead.id)
    )

    with db_session() as db, db.begin():
        created_id = db.scalar(statement)
        lead_id = created_id or db.scalar(
            select(Lead.id).where(Lead.payload_hash == digest)
        )

    return jsonify(id=lead_id, status='new', duplicate=created_id is None), (
        201 if created_id else 200
    )


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
        db.commit()

    return jsonify(deleted=deleted, status='ok')
