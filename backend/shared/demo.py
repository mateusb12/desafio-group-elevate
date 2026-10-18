"""Reinicialização e carga inicial dos dados locais usados pelo modo demonstração."""

from sqlalchemy import delete

from features.auth.models import TokenBlocklist, User
from shared.database import db_session
from features.dispatcher.models import CallCenter
from features.delivery_worker.models import DeliveryLeadToCallCenter
from features.outbox.models import OutboxPendingDelivery
from features.leads.models import (
    Affiliate,
    Contact,
    Distribution,
    Event,
    Funnel,
    Lead,
    LeadStatus,
    Product,
    ProductFunnel,
)


def reset_demo_data(db):
    for model in (
        DeliveryLeadToCallCenter,
        OutboxPendingDelivery,
        Distribution,
        Event,
        Lead,
        Contact,
        Affiliate,
        ProductFunnel,
        Product,
        Funnel,
        LeadStatus,
        TokenBlocklist,
        User,
        CallCenter,
    ):
        db.execute(delete(model))
    db.commit()


def reset_and_seed_demo():
    from features.auth.service import seed_demo_users
    from features.leads.products import seed_demo_catalog

    with db_session() as db:
        reset_demo_data(db)
        seed_demo_users(db)
        seed_demo_catalog(db)
