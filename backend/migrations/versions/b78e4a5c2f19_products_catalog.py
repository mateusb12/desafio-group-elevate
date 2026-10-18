'''products catalog and lead FK

Revision ID: b78e4a5c2f19
Revises: d86498fb27a3
'''
from alembic import op
import sqlalchemy as sa

revision = 'b78e4a5c2f19'
down_revision = 'd86498fb27a3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'products',
        sa.Column('code', sa.String(80), primary_key=True),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
    )
    products = sa.table(
        'products',
        sa.column('code', sa.String),
        sa.column('name', sa.String),
        sa.column('is_active', sa.Boolean),
    )
    op.bulk_insert(products, [
        {'code': 'nutralean', 'name': 'Nutralean', 'is_active': True},
        {'code': 'curso-vendas', 'name': 'Curso de Vendas', 'is_active': True},
        {'code': 'marketing-digital', 'name': 'Marketing Digital', 'is_active': True},
    ])
    # Mantem todos os leads legados, mesmo se usavam outros produtos.
    op.execute(sa.text('''
        INSERT INTO products (code, name, is_active)
        SELECT DISTINCT product, product, TRUE FROM leads
        WHERE product IS NOT NULL
        ON CONFLICT (code) DO NOTHING
    '''))
    op.create_foreign_key(
        'fk_leads_product', 'leads', 'products', ['product'], ['code']
    )


def downgrade():
    op.drop_constraint('fk_leads_product', 'leads', type_='foreignkey')
    op.drop_table('products')
