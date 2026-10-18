"""Reset e seed dos dados locais usados pelo modo demo."""

from sqlalchemy import delete

from auth.models import TokenBlocklist, User
from database import db_session
from dispatcher.models import CallCenter
from leads.models import (
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
    from auth.service import seed_demo_users
    from leads.products import seed_demo_catalog

    with db_session() as db:
        reset_demo_data(db)
        seed_demo_users(db)
        seed_demo_catalog(db)
