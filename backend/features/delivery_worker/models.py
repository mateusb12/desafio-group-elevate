from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base


class DeliveryLeadToCallCenter(Base):
    """Estado persistente da entrega de um lead ao call center selecionado."""

    __tablename__ = "delivery_leads_to_call_centers"
    __table_args__ = (
        Index(
            "ix_delivery_retry_due_at_event_id",
            "next_retry_at", "event_id",
            postgresql_where=text("status = 'retry_scheduled'"),
        ),
        Index(
            "ix_delivery_failed_pending_dlq_at_event_id",
            "failed_at", "event_id",
            postgresql_where=text(
                "status = 'failed' AND dead_letter_published_at IS NULL"
            ),
        ),
    )

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    call_center_id: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dead_letter_published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
