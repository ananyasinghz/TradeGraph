"""Scenario impact acknowledgement API (IF-12c)."""

from __future__ import annotations

from fastapi import APIRouter, Header, Request

from backend.app.api.auth_deps import OperatorDep, ViewerDep
from backend.app.api.dependencies import SessionDep, SettingsDep
from backend.app.domain.trade import ScenarioImpactOut
from backend.app.services import impact_service
from backend.app.services.auth_service import audit_from_request, resolve_organization_id

router = APIRouter(prefix="/impacts", tags=["impacts"])


@router.get("", response_model=list[ScenarioImpactOut])
def list_impacts(
    session: SessionDep,
    settings: SettingsDep,
    _principal: ViewerDep,
    include_acknowledged: bool = False,
    limit: int = 50,
) -> list[ScenarioImpactOut]:
    del settings  # org filter reserved for future multi-tenant list
    return impact_service.list_impacts(
        session, limit=limit, include_acknowledged=include_acknowledged
    )


@router.post("/{impact_id}/acknowledge", response_model=ScenarioImpactOut)
def acknowledge_impact(
    impact_id: str,
    session: SessionDep,
    settings: SettingsDep,
    request: Request,
    principal: OperatorDep,
    x_organization_id: str | None = Header(default=None),
) -> ScenarioImpactOut:
    org = resolve_organization_id(settings, principal, x_organization_id)
    out = impact_service.acknowledge_impact(
        session,
        impact_id,
        actor=principal.actor,
        organization_id=org,
    )
    audit_from_request(
        session,
        request,
        principal,
        action="impact.acknowledge",
        resource_type="impact",
        resource_id=impact_id,
    )
    return out
