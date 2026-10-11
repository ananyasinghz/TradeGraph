"""Landed-cost calculator route + temporary duty structure endpoints."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Query

from backend.app.api.auth_deps import ViewerDep
from backend.app.api.dependencies import SessionDep
from backend.app.domain.trade import (
    CustomsModeAvailability,
    DutyStructureOut,
    ExemptionRuleOut,
    LandedCostBreakdown,
    LandedCostInput,
)
from backend.app.services import cost_service, exemption_service

router = APIRouter(tags=["calculate"])


@router.post("/calculate/landed-cost", response_model=LandedCostBreakdown)
def calculate_landed_cost(
    payload: LandedCostInput, session: SessionDep, _principal: ViewerDep
) -> LandedCostBreakdown:
    return cost_service.calculate(session, payload)


@router.get("/calculate/customs-availability", response_model=CustomsModeAvailability)
def customs_availability(
    session: SessionDep, _principal: ViewerDep
) -> CustomsModeAvailability:
    return cost_service.customs_mode_availability(session)


# Temporary dual-mount so Duty tab works even if /duty router was not reloaded.
@router.get("/duty/structure", response_model=DutyStructureOut)
def get_duty_structure(
    session: SessionDep,
    _principal: ViewerDep,
    hs: str = Query(..., min_length=4, max_length=16),
    origin: str = Query(..., min_length=2, max_length=2),
    destination: str = Query(default="IN", min_length=2, max_length=2),
    as_of: date = Query(...),
    assessable_value: Decimal = Query(default=Decimal("100000"), gt=0),
    currency: str = Query(default="INR", min_length=3, max_length=3),
    selected_exemption_id: str | None = Query(default=None),
    shipment_id: str | None = Query(default=None),
) -> DutyStructureOut:
    return cost_service.build_duty_structure(
        session,
        hs_code=hs,
        origin=origin,
        destination=destination,
        as_of=as_of,
        assessable_value=assessable_value,
        currency=currency,
        selected_exemption_id=selected_exemption_id,
        shipment_id=shipment_id,
    )


@router.get("/duty/exemptions", response_model=list[ExemptionRuleOut])
def list_duty_exemptions(
    session: SessionDep,
    _principal: ViewerDep,
    hs: str = Query(..., min_length=4, max_length=16),
    origin: str = Query(..., min_length=2, max_length=2),
    destination: str = Query(default="IN", min_length=2, max_length=2),
    as_of: date = Query(...),
    shipment_id: str | None = Query(default=None),
) -> list[ExemptionRuleOut]:
    return exemption_service.list_applicable_exemptions(
        session,
        hs_code=hs,
        origin=origin,
        destination=destination,
        as_of=as_of,
        shipment_id=shipment_id,
    )
