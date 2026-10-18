"""add affiliates catalog and lead foreign key"""

from alembic import op
import sqlalchemy as sa


revision = 'e53b7c0d2841'
down_revision = 'd42e6b9f1730'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'affiliates',
        sa.Column('id', sa.String(80), nullable=False),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.execute(sa.text('''
        INSERT INTO affiliates (id, name, is_active)
        SELECT DISTINCT affiliate_id, affiliate_id, TRUE
        FROM leads
        WHERE affiliate_id IS NOT NULL
        ON CONFLICT (id) DO NOTHING
    '''))
    op.create_foreign_key(
        'fk_leads_affiliate', 'leads', 'affiliates', ['affiliate_id'], ['id']
    )


def downgrade() -> None:
    op.drop_constraint('fk_leads_affiliate', 'leads', type_='foreignkey')
    op.drop_table('affiliates')
