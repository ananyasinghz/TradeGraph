"""Home dashboard aggregation (V1.1c + IF-12a)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.data.models import Shipment
from backend.app.domain.trade import (
    DashboardAlert,
    DashboardOut,
    DashboardShipmentCard,
)
from backend.app.services import shipment_service, system_status_service, watchlist_service


def _chips_for_shipment(
    shipment_id: str, session: Session
) -> tuple[list[str], list[DashboardAlert]]:
    from backend.app.services import readiness_service

    detail = shipment_service.get_shipment(session, shipment_id)
    chips: list[str] = []
    alerts: list[DashboardAlert] = []

    readiness = readiness_service.score_shipment(session, shipment_id)
    if detail.hs_code_working:
        chips.append(f"HS {detail.hs_code_working}")
    else:
        chips.append("HS pending")
        alerts.append(
            DashboardAlert(
                kind="shipment",
                severity="warn",
                message=f"“{detail.title}” has no working HS code.",
                shipment_id=detail.id,
            )
        )

    if readiness.calculation_ready:
        chips.append("Estimate ready")
    elif detail.latest_calculation is not None:
        chips.append("Estimate partial")
    else:
        chips.append("Duty not calculated")
        if detail.hs_code_working:
            alerts.append(
                DashboardAlert(
                    kind="shipment",
                    severity="info",
                    message=f"“{detail.title}” is ready for landed-cost calculation.",
                    shipment_id=detail.id,
                )
            )

    if readiness.documents_incomplete:
        chips.append("Documents incomplete")
        alerts.append(
            DashboardAlert(
                kind="shipment",
                severity="warn",
                message=f"“{detail.title}” still has missing shipping papers.",
                shipment_id=detail.id,
            )
        )
    else:
        chips.append("Documents ready")

    if readiness.fta_unverified:
        chips.append("FTA unverified")
    if readiness.human_review_required:
        chips.append("Needs broker review")

    return chips, alerts


def build_dashboard(session: Session, settings: Settings | None = None) -> DashboardOut:
    if settings is None:
        from backend.app.core.config import get_settings

        settings = get_settings()

    rows = session.scalars(select(Shipment).order_by(Shipment.updated_at.desc()).limit(12)).all()
    cards: list[DashboardShipmentCard] = []
    alerts: list[DashboardAlert] = []

    for row in rows:
        chips, shipment_alerts = _chips_for_shipment(row.id, session)
        alerts.extend(shipment_alerts)
        cards.append(
            DashboardShipmentCard(
                id=row.id,
                title=row.title,
                origin=row.origin,
                destination=row.destination,
                hs_code_working=row.hs_code_working,
                status=row.status,
                as_of_date=row.as_of_date,
                chips=chips,
                updated_at=row.updated_at,
            )
        )

    for change in watchlist_service.list_changes(session):
        alerts.append(
            DashboardAlert(
                kind="watchlist",
                severity="warn",
                message=change.summary,
                shipment_id=(
                    change.affected_shipment_ids[0] if change.affected_shipment_ids else None
                ),
            )
        )

    from backend.app.services import impact_service

    for impact in impact_service.list_impacts(session, limit=20, include_acknowledged=False):
        alerts.insert(
            0,
            DashboardAlert(
                kind="tariff_impact",
                severity="warn",
                message=impact.summary,
                shipment_id=impact.shipment_id,
                hs_code=impact.hs_code,
                old_rate=impact.old_rate,
                new_rate=impact.new_rate,
                duty_delta=impact.duty_delta,
                landed_delta=impact.landed_delta,
                currency=impact.currency,
                recommended_action=impact.recommended_action,
                impact_id=impact.id,
                shipment_title=impact.shipment_title,
                source_document_id=impact.source_document_id,
                effective_from=impact.effective_from,
                previous_calculation_id=impact.old_snapshot_id,
                new_calculation_id=impact.new_snapshot_id,
            ),
        )

    status = system_status_service.build_system_status(session, settings)
    data_status = system_status_service.data_status_from_system(status)

    return DashboardOut(shipments=cards, alerts=alerts[:20], data_status=data_status)
