"""Regras para processar webhooks do call center."""

from datetime import timezone
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from features.leads.models import Event, Lead

from .schemas import CallCenterWebhookInput


def process_webhook(db: Session, payload: CallCenterWebhookInput) -> tuple[dict, int]:
    """Processa um webhook atomicamente, preservando idempotência e ordem dos eventos."""
    lead_id = payload.lead_id
    external_id = payload.external_id
    status = payload.status
    event_at = payload.event_at.astimezone(timezone.utc)

    with db.begin():
        lead = db.scalar(
            select(Lead)
            .where(Lead.id == lead_id)
            .with_for_update()
        )
        if lead is None:
            return {'error': 'Lead não encontrado.'}, 404

        existing = db.scalar(
            select(Event).where(
                Event.lead_id == lead_id,
                Event.external_id == external_id,
            )
        )
        if existing is not None:
            if existing.status != status or existing.event_at != event_at:
                return {'error': 'external_id reutilizado com dados diferentes.'}, 409
            return {
                'id': existing.id,
                'lead_id': lead_id,
                'status': status,
                'current_status': lead.status,
                'duplicate': True,
                'applied': False,
                'out_of_order': False,
            }, 200

        latest_event_time = db.scalar(
            select(func.max(Event.event_at)).where(Event.lead_id == lead_id)
        )
        comparison_time = latest_event_time or lead.received_at
        applied = comparison_time is None or event_at > comparison_time

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

    return {
        'id': event.id,
        'lead_id': lead_id,
        'status': status,
        'current_status': current_status,
        'duplicate': False,
        'applied': applied,
        'out_of_order': not applied,
    }, 201
