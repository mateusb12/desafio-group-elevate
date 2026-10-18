"""Persistência transacional de afiliados recebidos de sistemas externos."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from .models import Affiliate


def get_or_create_affiliate(db: Session, affiliate_id: str) -> Affiliate:
    """Obtém ou cadastra um afiliado sem reativar registros inativos."""
    affiliate = db.get(Affiliate, affiliate_id)
    if affiliate is not None:
        return affiliate

    inserted_id = db.scalar(
        insert(Affiliate)
        .values(id=affiliate_id, name=affiliate_id)
        .on_conflict_do_nothing(index_elements=[Affiliate.id])
        .returning(Affiliate.id)
    )
    if inserted_id is not None:
        return db.get(Affiliate, inserted_id)

    return db.scalar(select(Affiliate).where(Affiliate.id == affiliate_id))
