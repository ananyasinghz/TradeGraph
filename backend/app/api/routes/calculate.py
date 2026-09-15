"""Landed-cost calculator route."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.auth_deps import ViewerDep
from backend.app.api.dependencies import SessionDep
from backend.app.domain.trade import CustomsModeAvailability, LandedCostBreakdown, LandedCostInput
from backend.app.services import cost_service

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
