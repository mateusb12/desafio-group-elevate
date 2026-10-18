"""add product and funnel associations"""

from alembic import op
import sqlalchemy as sa


revision = 'd42e6b9f1730'
down_revision = 'c31f7a8e9021'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'product_funnels',
        sa.Column('product_code', sa.String(80), nullable=False),
        sa.Column('funnel_code', sa.String(80), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.ForeignKeyConstraint(['product_code'], ['products.code']),
        sa.ForeignKeyConstraint(['funnel_code'], ['funnels.code']),
        sa.PrimaryKeyConstraint('product_code', 'funnel_code'),
    )

    op.execute(sa.text('''
        INSERT INTO product_funnels (product_code, funnel_code, is_active)
        SELECT DISTINCT product, funnel, TRUE
        FROM leads
        ON CONFLICT (product_code, funnel_code) DO NOTHING
    '''))
    op.execute(sa.text('''
        INSERT INTO product_funnels (product_code, funnel_code, is_active)
        SELECT products.code, funnels.code, TRUE
        FROM products
        CROSS JOIN funnels
        WHERE products.code IN ('nutralean', 'curso-vendas', 'marketing-digital')
          AND funnels.code IN ('vsl-01', 'webinar-02', 'checkout-03')
        ON CONFLICT (product_code, funnel_code) DO NOTHING
    '''))


def downgrade() -> None:
    op.drop_table('product_funnels')
