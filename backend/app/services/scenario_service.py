"""TradeScenario facade over Shipment (IF-11c)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.data.models import Shipment
from backend.app.domain.trade import (
    ClassificationConfirmRequest,
    LandedCostBreakdown,
    LandedCostInput,
    ShipmentCalculateRequest,
    ShipmentCreate,
    ShipmentOut,
    ShipmentUpdate,
    ShipmentWorkspaceOut,
    WatchlistItemCreate,
)
from backend.app.services import (
    classification_service,
    cost_service,
    fta_service,
    readiness_service,
    shipment_service,
    tariff_service,
    watchlist_service,
    workspace_service,
)


def create(session: Session, payload: ShipmentCreate) -> ShipmentOut:
    return shipment_service.create_shipment(session, payload)


def update(session: Session, scenario_id: str, payload: ShipmentUpdate) -> ShipmentOut:
    return shipment_service.update_shipment(session, scenario_id, payload)


def get(session: Session, scenario_id: str) -> ShipmentOut:
    return shipment_service.get_shipment(session, scenario_id)


def list_scenarios(
    session: Session, *, organization_id: str | None = None
) -> list[ShipmentOut]:
    if organization_id is None:
        return shipment_service.list_shipments(session)
    rows = session.scalars(
        select(Shipment)
        .where(Shipment.organization_id == organization_id)
        .order_by(Shipment.updated_at.desc())
    ).all()
    return [shipment_service._shipment_out(session, r) for r in rows]


def get_for_org(
    session: Session, scenario_id: str, *, organization_id: str
) -> ShipmentOut:
    row = session.get(Shipment, scenario_id)
    if row is None:
        raise AppError(code="SHIPMENT_NOT_FOUND", message="Scenario not found", status_code=404)
    if row.organization_id and row.organization_id != organization_id:
        raise AppError(
            code="SCENARIO_FORBIDDEN",
            message="Scenario not in organization",
            status_code=403,
        )
    return shipment_service.get_shipment(session, scenario_id)


def get_workspace(session: Session, scenario_id: str) -> ShipmentWorkspaceOut:
    return workspace_service.get_workspace(session, scenario_id)


def confirm_hs(
    session: Session, scenario_id: str, payload: ClassificationConfirmRequest
) -> ShipmentOut:
    return classification_service.confirm_classification(session, scenario_id, payload)


def calculate(
    session: Session,
    scenario_id: str,
    payload: ShipmentCalculateRequest | None = None,
) -> ShipmentOut:
    out = shipment_service.calculate_shipment(session, scenario_id, payload)
    from backend.app.services import timeline_service

    calc = out.latest_calculation
    timeline_service.record_event(
        session,
        scenario_id=scenario_id,
        organization_id=out.organization_id,
        event_type="calculation",
        summary=(
            f"Calculation · landed {calc.landed_cost} {calc.currency}"
            if calc
            else "Calculation saved"
        ),
        payload={
            "landed_cost": str(calc.landed_cost) if calc else None,
            "mode": calc.calculation_mode if calc else None,
        },
    )
    return out


def lookup_tariff(session: Session, scenario_id: str):
    row = shipment_service.get_shipment(session, scenario_id)
    if not row.hs_code_working:
        raise AppError(
            code="HS_REQUIRED",
            message="Confirm HS before tariff lookup",
            status_code=400,
        )
    return tariff_service.resolve_applicable_tariff(
        session,
        hs_code=row.hs_code_working,
        origin=row.origin,
        destination=row.destination,
        as_of=row.as_of_date,
    )


def check_fta(session: Session, scenario_id: str):
    row = shipment_service.get_shipment(session, scenario_id)
    if not row.hs_code_working:
        raise AppError(
            code="HS_REQUIRED",
            message="Confirm HS before FTA check",
            status_code=400,
        )
    return fta_service.check_fta(
        session,
        hs_code=row.hs_code_working,
        origin=row.origin,
        destination=row.destination,
        as_of=row.as_of_date,
        shipment_id=scenario_id,
        agreement_id=row.agreement_code,
    )


def build_checklist(session: Session, scenario_id: str) -> ShipmentOut:
    return shipment_service.build_shipment_checklist(session, scenario_id)


def score_readiness(session: Session, scenario_id: str):
    return readiness_service.score_shipment(session, scenario_id)


def link_watchlist(session: Session, scenario_id: str):
    return watchlist_service.add_item(
        session, WatchlistItemCreate(shipment_id=scenario_id)
    )


def cost_from_scenario(
    session: Session, scenario_id: str, *, mode: str | None = None
) -> LandedCostBreakdown:
    row = session.get(Shipment, scenario_id)
    if row is None:
        raise AppError(code="SHIPMENT_NOT_FOUND", message="Scenario not found", status_code=404)
    if not row.hs_code_working:
        raise AppError(code="HS_REQUIRED", message="Confirm HS first", status_code=400)
    return cost_service.calculate(
        session,
        LandedCostInput(
            hs_code=row.hs_code_working,
            origin=row.origin,
            destination=row.destination,
            as_of=row.as_of_date,
            invoice_value=row.invoice_value,
            currency=row.currency,
            incoterm=row.incoterm,
            freight=row.freight,
            insurance=row.insurance,
            requested_mode=mode,  # type: ignore[arg-type]
            shipment_id=row.id,
            persist_snapshot=True,
        ),
    )
