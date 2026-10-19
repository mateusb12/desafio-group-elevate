"""Adiciona índices para ordenação e filas de trabalho."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "c5d7e9f1a2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_leads_received_at_id",
        "leads",
        [sa.text("received_at DESC"), sa.text("id DESC")],
    )
    op.create_index(
        "ix_outbox_pending_created_at_id",
        "outbox_pending_deliveries",
        ["created_at", "id"],
        postgresql_where=sa.text("published_at IS NULL"),
    )
    op.create_index(
        "ix_delivery_retry_due_at_event_id",
        "delivery_leads_to_call_centers",
        ["next_retry_at", "event_id"],
        postgresql_where=sa.text("status = 'retry_scheduled'"),
    )
    op.create_index(
        "ix_delivery_failed_pending_dlq_at_event_id",
        "delivery_leads_to_call_centers",
        ["failed_at", "event_id"],
        postgresql_where=sa.text(
            "status = 'failed' AND dead_letter_published_at IS NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_delivery_failed_pending_dlq_at_event_id",
        table_name="delivery_leads_to_call_centers",
    )
    op.drop_index(
        "ix_delivery_retry_due_at_event_id",
        table_name="delivery_leads_to_call_centers",
    )
    op.drop_index(
        "ix_outbox_pending_created_at_id",
        table_name="outbox_pending_deliveries",
    )
    op.drop_index("ix_leads_received_at_id", table_name="leads")
