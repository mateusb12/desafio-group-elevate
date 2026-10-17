"""Distribuição ponderada de leads entre call centers."""

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from dispatcher.models import CallCenter


def lock_call_center_distribution(db: Session) -> None:
    """Garante que as requisições façam a escolha uma por vez."""
    db.execute(text("SELECT pg_advisory_xact_lock(41625, 20261017)"))


def get_available_call_centers(db: Session) -> list[CallCenter]:
    """Retorna os call centers ativos que podem receber leads."""
    return db.scalars(
        select(CallCenter)
        .where(
            CallCenter.is_active.is_(True),
            CallCenter.distribution_weight > 0,
        )
        .order_by(CallCenter.id)
    ).all()


def count_leads_by_call_center(
    db: Session,
    call_center_ids: list[str],
) -> dict[str, int]:
    """Conta os leads já distribuídos para cada call center informado."""
    from leads.models import Lead

    return dict(
        db.execute(
            select(Lead.call_center_id, func.count(Lead.id))
            .where(Lead.call_center_id.in_(call_center_ids))
            .group_by(Lead.call_center_id)
        ).all()
    )


def calculate_expected_lead_count(
    call_center: CallCenter,
    leads_after_assignment: int,
    total_weight: float,
) -> float:
    """Calcula quantos leads esse call center deveria ter pelo percentual configurado."""
    return leads_after_assignment * call_center.distribution_weight / total_weight


def select_call_center(
    call_centers: list[CallCenter],
    lead_counts: dict[str, int],
    leads_after_assignment: int,
) -> CallCenter:
    """Escolhe o call center com a maior diferença entre o esperado e o atual."""
    total_weight = sum(
        call_center.distribution_weight for call_center in call_centers
    )

    def selection_key(call_center: CallCenter) -> tuple[float, float, str]:
        current_lead_count = lead_counts.get(call_center.id, 0)
        expected_lead_count = calculate_expected_lead_count(
            call_center,
            leads_after_assignment,
            total_weight,
        )
        distribution_deficit = expected_lead_count - current_lead_count

        return (
            distribution_deficit,
            call_center.distribution_weight,
            call_center.id,
        )

    return max(call_centers, key=selection_key)


def choose_call_center(db: Session) -> str:
    """Escolhe um call center para o próximo lead e retorna seu ID."""
    lock_call_center_distribution(db)

    call_centers = get_available_call_centers(db)
    if not call_centers:
        raise RuntimeError("Nenhum call center ativo com peso positivo.")

    lead_counts = count_leads_by_call_center(
        db,
        [call_center.id for call_center in call_centers],
    )
    leads_after_assignment = sum(lead_counts.values()) + 1
    selected_call_center = select_call_center(
        call_centers,
        lead_counts,
        leads_after_assignment,
    )

    return selected_call_center.id
