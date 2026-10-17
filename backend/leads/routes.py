import hashlib
import json
import re
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

# Catálogo mínimo para os cenários atuais do LAB; futuramente virá do banco.
PRODUCTS = {'nutralean', 'curso-vendas', 'marketing-digital'}
FUNNELS = {'vsl-01', 'webinar-02', 'checkout-03'}
FIELDS = {
    'name': 120, 'email': 255, 'phone': 20, 'product': 80,
    'funnel': 80, 'source': 80, 'campaign': 120, 'affiliate_id': 80,
}
UTM_FIELDS = ('source', 'medium', 'campaign', 'content')


def validate_lead(body):
    if not isinstance(body, dict):
        return None, 'O payload deve ser um objeto JSON.'

    clean = {}
    for key, max_length in FIELDS.items():
        value = body.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > max_length:
            return None, f'Campo inválido ou ausente: {key}.'
        clean[key] = value.strip()

    clean['email'] = clean['email'].lower()
    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', clean['email']):
        return None, 'E-mail inválido.'
    if not re.fullmatch(r'\+55\d{11}', clean['phone']):
        return None, 'Telefone inválido. Use +55 seguido de DDD e 9 dígitos.'
    if clean['product'] not in PRODUCTS:
        return None, 'Produto desconhecido.'
    if clean['funnel'] not in FUNNELS:
        return None, 'Funil desconhecido.'

    utm = body.get('utm')
    if not isinstance(utm, dict):
        return None, 'UTM deve ser um objeto.'
    if any(not isinstance(utm.get(k), str) or not utm[k].strip() for k in UTM_FIELDS):
        return None, 'UTM malformada.'
    clean['utm'] = {key: utm[key].strip() for key in UTM_FIELDS}
    return clean, None


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
