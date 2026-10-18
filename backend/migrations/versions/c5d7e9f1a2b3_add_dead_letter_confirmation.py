"""Registra a confirmação da publicação de falhas no RabbitMQ."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c5d7e9f1a2b3"
down_revision: Union[str, Sequence[str], None] = "b4c8e2a1d7f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "delivery_leads_to_call_centers",
        sa.Column("dead_letter_published_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("delivery_leads_to_call_centers", "dead_letter_published_at")
