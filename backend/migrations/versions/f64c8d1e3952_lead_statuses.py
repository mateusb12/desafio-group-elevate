"""add lead status catalog and foreign keys"""

from alembic import op
import sqlalchemy as sa


revision = 'f64c8d1e3952'
down_revision = 'e53b7c0d2841'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'lead_statuses',
        sa.Column('code', sa.String(30), nullable=False),
        sa.Column('label', sa.String(80), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.PrimaryKeyConstraint('code'),
    )
    statuses = sa.table(
        'lead_statuses',
        sa.column('code', sa.String),
        sa.column('label', sa.String),
        sa.column('is_active', sa.Boolean),
    )
    op.bulk_insert(statuses, [
        {'code': 'new', 'label': 'Novo', 'is_active': True},
        {'code': 'contacted', 'label': 'Contatado', 'is_active': True},
        {'code': 'no_answer', 'label': 'Sem resposta', 'is_active': True},
        {'code': 'callback', 'label': 'Retorno', 'is_active': True},
        {'code': 'qualified', 'label': 'Qualificado', 'is_active': True},
        {'code': 'sale', 'label': 'Venda', 'is_active': True},
        {'code': 'refund', 'label': 'Reembolso', 'is_active': True},
        {'code': 'invalid', 'label': 'Inválido', 'is_active': True},
    ])
    op.execute(sa.text('''
        INSERT INTO lead_statuses (code, label, is_active)
        SELECT status, status, TRUE
        FROM (
            SELECT status FROM leads
            UNION
            SELECT status FROM events
        ) AS legacy_statuses
        ON CONFLICT (code) DO NOTHING
    '''))
    op.create_foreign_key(
        'fk_leads_status', 'leads', 'lead_statuses', ['status'], ['code']
    )
    op.create_foreign_key(
        'fk_events_status', 'events', 'lead_statuses', ['status'], ['code']
    )


def downgrade() -> None:
    op.drop_constraint('fk_events_status', 'events', type_='foreignkey')
    op.drop_constraint('fk_leads_status', 'leads', type_='foreignkey')
    op.drop_table('lead_statuses')
