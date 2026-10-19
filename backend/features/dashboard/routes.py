from datetime import datetime, timezone

from flask import jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import func, select

from features.auth.permissions import admin_required
from features.leads.models import Lead, LeadStatus
from shared.database import db_session

from . import dashboard_blueprint


@dashboard_blueprint.get("/metrics")
@jwt_required()
@admin_required
def metrics():
    with db_session() as db:
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        total = db.scalar(select(func.count()).select_from(Lead)) or 0
        received_today = db.scalar(
            select(func.count()).select_from(Lead).where(
                Lead.received_at >= today_start
            )
        ) or 0
        distributed = db.scalar(
            select(func.count()).select_from(Lead).where(
                Lead.call_center_id.is_not(None)
            )
        ) or 0
        pending = total - distributed
        sales = db.scalar(
            select(func.count()).select_from(Lead).where(Lead.status == "sale")
        ) or 0
        conversion_rate = round((sales / total) * 100, 1) if total else 0.0

        return jsonify(
            total=total,
            receivedToday=received_today,
            distributed=distributed,
            pending=pending,
            sales=sales,
            conversionRate=conversion_rate,
        )


@dashboard_blueprint.get("/funnel")
@jwt_required()
@admin_required
def funnel():
    """Retorna o fluxo dos leads desde a entrada até o status atual."""
    with db_session() as db:
        total = db.scalar(select(func.count()).select_from(Lead)) or 0
        status_counts = db.execute(
            select(Lead.status, LeadStatus.label, func.count(Lead.id))
            .join(LeadStatus, LeadStatus.code == Lead.status)
            .group_by(Lead.status, LeadStatus.label)
            .order_by(Lead.status)
        ).all()

        status_counts = sorted(
            status_counts,
            key=lambda row: (
                0 if row[0] in {'sale', 'qualified'}
                else 2 if row[0] in {'refund', 'invalid'}
                else 1,
                0 if row[0] == 'sale' else 1,
                row[0],
            ),
        )

        nodes = [{'id': 'received', 'label': 'Leads recebidos'}]
        links = []
        for code, label, count in status_counts:
            target_id = f'status-{code}'
            display_label = {
                'new': 'Sem atualização',
                'callback': 'Aguardando resposta',
            }.get(code, label)
            nodes.append({'id': target_id, 'label': display_label})
            links.append({'source': 'received', 'target': target_id, 'value': count})

        return jsonify(total=total, nodes=nodes, links=links)
