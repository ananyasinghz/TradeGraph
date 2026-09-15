"""Scenario impact acknowledgement API (IF-12c)."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.dependencies import SessionDep
from backend.app.domain.trade import ScenarioImpactOut
from backend.app.services import impact_service

router = APIRouter(prefix="/impacts", tags=["impacts"])


@router.post("/{impact_id}/acknowledge", response_model=ScenarioImpactOut)
def acknowledge_impact(impact_id: str, session: SessionDep) -> ScenarioImpactOut:
    return impact_service.acknowledge_impact(session, impact_id)
