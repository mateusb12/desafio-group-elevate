"""Regras para receber e salvar leads."""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from features.dispatcher.service import choose_call_center

from .affiliates import get_or_create_affiliate
from .idempotency import acquire_idempotency_lock, calculate_payload_hash
from .models import Contact, Distribution, Event, Funnel, Lead, Product, ProductFunnel


@dataclass(frozen=True)
class LeadCreationResult:
    payload: dict
    status_code: int


def create_lead(db: Session, clean_payload: dict, idempotency_key: str) -> LeadCreationResult:
    """Cria o lead e o resto do cadastro junto, na mesma transação."""
    payload_hash = calculate_payload_hash(clean_payload)

    with db.begin():
        acquire_idempotency_lock(db, idempotency_key)

        existing = db.scalar(
            select(Lead).where(Lead.idempotency_key == idempotency_key)
        )
        if existing is not None:
            if existing.payload_hash != payload_hash:
                return LeadCreationResult(
                    payload={'error': 'Idempotency-Key reutilizada com dados diferentes.'},
                    status_code=409,
                )
            return LeadCreationResult(
                payload={'id': existing.id, 'status': 'new', 'duplicate': True},
                status_code=200,
            )

        product_exists = db.scalar(
            select(Product.code).where(Product.code == clean_payload['product'])
        )
        if product_exists is None:
            return LeadCreationResult(
                payload={'error': 'Produto desconhecido.'}, status_code=400
            )

        funnel_exists = db.scalar(
            select(Funnel.code).where(Funnel.code == clean_payload['funnel'])
        )
        if funnel_exists is None:
            return LeadCreationResult(
                payload={'error': 'Funil desconhecido.'}, status_code=400
            )

        valid_association = db.scalar(
            select(ProductFunnel.product_code).where(
                ProductFunnel.product_code == clean_payload['product'],
                ProductFunnel.funnel_code == clean_payload['funnel'],
            )
        )
        if valid_association is None:
            return LeadCreationResult(
                payload={'error': 'Combinação produto/funil inválida.'},
                status_code=400,
            )

        get_or_create_affiliate(db, clean_payload['affiliate_id'])

        contact_id = db.scalar(
            insert(Contact)
            .values(
                id=str(uuid4()),
                name=clean_payload['name'],
                email=clean_payload['email'],
                phone=clean_payload['phone'],
            )
            .on_conflict_do_nothing(index_elements=[Contact.email])
            .returning(Contact.id)
        )
        if contact_id is None:
            contact_id = db.scalar(
                select(Contact.id).where(Contact.email == clean_payload['email'])
            )

        lead_data = {
            field: value
            for field, value in clean_payload.items()
            if field not in ('name', 'email', 'phone')
        }
        lead_id = str(uuid4())
        received_at = datetime.now(timezone.utc)
        call_center_id = choose_call_center(db)

        db.add(Lead(
            id=lead_id,
            contact_id=contact_id,
            call_center_id=call_center_id,
            idempotency_key=idempotency_key,
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

    return LeadCreationResult(
        payload={'id': lead_id, 'status': 'new', 'duplicate': False},
        status_code=201,
    )
