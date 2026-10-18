"""Adiciona estado persistente da entrega de leads aos call centers

Revision ID: b4c8e2a1d7f0
Revises: 66fcb28c63ba
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b4c8e2a1d7f0"
down_revision: Union[str, Sequence[str], None] = "66fcb28c63ba"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "delivery_leads_to_call_centers",
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("lead_id", sa.String(length=36), nullable=False),
        sa.Column("call_center_id", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "ix_delivery_leads_to_call_centers_lead_id",
        "delivery_leads_to_call_centers",
        ["lead_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_delivery_leads_to_call_centers_lead_id",
        table_name="delivery_leads_to_call_centers",
    )
    op.drop_table("delivery_leads_to_call_centers")
