"""add funnels catalog and lead foreign key"""

from alembic import op
import sqlalchemy as sa


revision = 'c31f7a8e9021'
down_revision = 'b78e4a5c2f19'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'funnels',
        sa.Column('code', sa.String(80), nullable=False),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.PrimaryKeyConstraint('code'),
    )

    funnels = sa.table(
        'funnels',
        sa.column('code', sa.String),
        sa.column('name', sa.String),
        sa.column('is_active', sa.Boolean),
    )
    op.bulk_insert(funnels, [
        {'code': 'vsl-01', 'name': 'VSL 01', 'is_active': True},
        {'code': 'webinar-02', 'name': 'Webinar 02', 'is_active': True},
        {'code': 'checkout-03', 'name': 'Checkout 03', 'is_active': True},
    ])
    op.execute(sa.text('''
        INSERT INTO funnels (code, name, is_active)
        SELECT DISTINCT funnel, funnel, TRUE
        FROM leads
        WHERE funnel IS NOT NULL
        ON CONFLICT (code) DO NOTHING
    '''))
    op.create_foreign_key(
        'fk_leads_funnel', 'leads', 'funnels', ['funnel'], ['code']
    )


def downgrade() -> None:
    op.drop_constraint('fk_leads_funnel', 'leads', type_='foreignkey')
    op.drop_table('funnels')
