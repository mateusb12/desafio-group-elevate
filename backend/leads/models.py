from uuid import uuid4
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Contact(Base):
    __tablename__ = 'contacts'

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)


class Lead(Base):
    __tablename__ = 'leads'

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
    product: Mapped[str] = mapped_column(String(80), nullable=False)
    funnel: Mapped[str] = mapped_column(String(80), nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    campaign: Mapped[str] = mapped_column(String(120), nullable=False)
    affiliate_id: Mapped[str] = mapped_column(String(80), nullable=False)
    utm: Mapped[dict] = mapped_column(JSONB, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default='new')
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class Event(Base):
    __tablename__ = 'events'

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
        String(30), nullable=False
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
