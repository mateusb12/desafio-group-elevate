from uuid import uuid4
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base


class Contact(Base):
    __tablename__ = 'contacts'

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)


class Product(Base):
    __tablename__ = 'products'

    code: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)


class Funnel(Base):
    __tablename__ = 'funnels'

    code: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)


class ProductFunnel(Base):
    __tablename__ = 'product_funnels'

    product_code: Mapped[str] = mapped_column(
        String(80), ForeignKey('products.code'), primary_key=True
    )
    funnel_code: Mapped[str] = mapped_column(
        String(80), ForeignKey('funnels.code'), primary_key=True
    )


class Affiliate(Base):
    __tablename__ = 'affiliates'

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)


class LeadStatus(Base):
    __tablename__ = 'lead_statuses'

    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    label: Mapped[str] = mapped_column(String(80), nullable=False)


class Lead(Base):
    __tablename__ = 'leads'
    __table_args__ = (
        ForeignKeyConstraint(
            ['product', 'funnel'],
            ['product_funnels.product_code', 'product_funnels.funnel_code'],
            name='fk_leads_product_funnel',
        ),
    )

    call_center_id: Mapped[str | None] = mapped_column(
        String(80),
        ForeignKey('call_centers.id'),
        nullable=True,
        index=True,
    )

    contact_id: Mapped[str] = mapped_column(
        String(36), ForeignKey('contacts.id'), nullable=False, index=True
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    product: Mapped[str] = mapped_column(
        String(80), ForeignKey('products.code', name='fk_leads_product'), nullable=False
    )
    funnel: Mapped[str] = mapped_column(
        String(80), ForeignKey('funnels.code', name='fk_leads_funnel'), nullable=False
    )
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    campaign: Mapped[str] = mapped_column(String(120), nullable=False)
    affiliate_id: Mapped[str] = mapped_column(
        String(80), ForeignKey('affiliates.id', name='fk_leads_affiliate'), nullable=False
    )
    utm: Mapped[dict] = mapped_column(JSONB, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(
        String(36), unique=True, nullable=True
    )
    payload_hash: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(30), ForeignKey('lead_statuses.code', name='fk_leads_status'), nullable=False, default='new'
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class Event(Base):
    __tablename__ = 'events'
    __table_args__ = (
        UniqueConstraint(
            'lead_id', 'external_id',
            name='uq_events_lead_external',
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True,
        default=lambda: str(uuid4())
    )

    lead_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey('leads.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(30), ForeignKey('lead_statuses.code', name='fk_events_status'), nullable=False
    )

    external_id: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )

    event_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class Distribution(Base):
    __tablename__ = 'distributions'
    __table_args__ = (
        Index('ix_distributions_lead_assigned_at', 'lead_id', 'assigned_at'),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    lead_id: Mapped[str] = mapped_column(
        String(36), ForeignKey('leads.id', ondelete='CASCADE'), nullable=False
    )
    call_center_id: Mapped[str] = mapped_column(
        String(80), ForeignKey('call_centers.id'), nullable=False
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    reason: Mapped[str] = mapped_column(
        String(40), nullable=False, default='initial', server_default='initial'
    )
