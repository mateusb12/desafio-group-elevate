from datetime import datetime, timezone

from flask import jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import func, select

from features.auth.routes import current_user
from features.auth.models import UserRole
from features.leads.models import Lead
from shared.database import db_session

from . import dashboard_blueprint


@dashboard_blueprint.get("/metrics")
@jwt_required()
def metrics():
    with db_session() as db:
        user = current_user(db)
        if user is None:
            return jsonify(error="Autenticação necessária."), 401
        if user.role != UserRole.ADMIN:
            return jsonify(error="Acesso restrito a administradores."), 403

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
