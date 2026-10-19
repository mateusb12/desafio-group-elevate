from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base


class OutboxPendingDelivery(Base):
    __tablename__ = 'outbox_pending_deliveries'
    __table_args__ = (
        Index(
            'ix_outbox_pending_created_at_id',
            'created_at', 'id',
            postgresql_where=text('published_at IS NULL'),
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    distribution_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey('distributions.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
