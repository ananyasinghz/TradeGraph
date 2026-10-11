"""TradeScenario API aliases over shipments (IF-11c + IF-12e org scoping)."""

from __future__ import annotations

from fastapi import APIRouter, Header, Request

from backend.app.api.auth_deps import OperatorDep
from backend.app.api.dependencies import SessionDep, SettingsDep
from backend.app.domain.trade import (
    CalculationSnapshotOut,
    ClassificationConfirmRequest,
    ScenarioTimelineOut,
    ShipmentCalculateRequest,
    ShipmentCreate,
    ShipmentOut,
    ShipmentUpdate,
    ShipmentWorkspaceOut,
)
from backend.app.services import cost_service, scenario_service, timeline_service
from backend.app.services.auth_service import audit_from_request, resolve_organization_id

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


def _org(
    settings: SettingsDep,
    principal: OperatorDep,
    x_organization_id: str | None,
) -> str:
    return resolve_organization_id(settings, principal, x_organization_id)


@router.get("", response_model=list[ShipmentOut])
def list_scenarios(
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
    x_organization_id: str | None = Header(default=None),
) -> list[ShipmentOut]:
    return scenario_service.list_scenarios(
        session, organization_id=_org(settings, principal, x_organization_id)
    )


@router.post("", response_model=ShipmentOut)
def create_scenario(
    payload: ShipmentCreate,
    session: SessionDep,
    settings: SettingsDep,
    request: Request,
    principal: OperatorDep,
    x_organization_id: str | None = Header(default=None),
) -> ShipmentOut:
    org = _org(settings, principal, x_organization_id)
    data = payload.model_copy(
        update={"organization_id": payload.organization_id or org}
    )
    out = scenario_service.create(session, data)
    audit_from_request(
        session,
        request,
        principal,
        action="scenario.create",
        resource_type="scenario",
        resource_id=out.id,
    )
    return out


@router.get("/{scenario_id}", response_model=ShipmentOut)
def get_scenario(
    scenario_id: str,
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
    x_organization_id: str | None = Header(default=None),
) -> ShipmentOut:
    return scenario_service.get_for_org(
        session, scenario_id, organization_id=_org(settings, principal, x_organization_id)
    )


@router.patch("/{scenario_id}", response_model=ShipmentOut)
def patch_scenario(
    scenario_id: str,
    payload: ShipmentUpdate,
    session: SessionDep,
    settings: SettingsDep,
    request: Request,
    principal: OperatorDep,
    x_organization_id: str | None = Header(default=None),
) -> ShipmentOut:
    scenario_service.get_for_org(
        session, scenario_id, organization_id=_org(settings, principal, x_organization_id)
    )
    out = scenario_service.update(session, scenario_id, payload)
    audit_from_request(
        session,
        request,
        principal,
        action="scenario.update",
        resource_type="scenario",
        resource_id=scenario_id,
    )
    return out


@router.get("/{scenario_id}/workspace", response_model=ShipmentWorkspaceOut)
def scenario_workspace(
    scenario_id: str,
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
    x_organization_id: str | None = Header(default=None),
) -> ShipmentWorkspaceOut:
    scenario_service.get_for_org(
        session, scenario_id, organization_id=_org(settings, principal, x_organization_id)
    )
    return scenario_service.get_workspace(session, scenario_id)


@router.post("/{scenario_id}/confirm-hs", response_model=ShipmentOut)
def confirm_hs(
    scenario_id: str,
    payload: ClassificationConfirmRequest,
    session: SessionDep,
    settings: SettingsDep,
    request: Request,
    principal: OperatorDep,
    x_organization_id: str | None = Header(default=None),
) -> ShipmentOut:
    scenario_service.get_for_org(
        session, scenario_id, organization_id=_org(settings, principal, x_organization_id)
    )
    out = scenario_service.confirm_hs(session, scenario_id, payload)
    audit_from_request(
        session,
        request,
        principal,
        action="scenario.confirm_hs",
        resource_type="scenario",
        resource_id=scenario_id,
        detail={
            "hs_code": payload.hs_code,
            "override_hs": payload.override_hs,
            "reason": payload.reason,
            "effective_hs": payload.override_hs or payload.hs_code,
        },
    )
    return out


@router.post("/{scenario_id}/calculate", response_model=ShipmentOut)
def calculate_scenario(
    scenario_id: str,
    session: SessionDep,
    settings: SettingsDep,
    request: Request,
    principal: OperatorDep,
    payload: ShipmentCalculateRequest | None = None,
    x_organization_id: str | None = Header(default=None),
) -> ShipmentOut:
    scenario_service.get_for_org(
        session, scenario_id, organization_id=_org(settings, principal, x_organization_id)
    )
    out = scenario_service.calculate(session, scenario_id, payload)
    audit_from_request(
        session,
        request,
        principal,
        action="scenario.calculate",
        resource_type="scenario",
        resource_id=scenario_id,
    )
    return out


@router.get("/{scenario_id}/calculations", response_model=list[CalculationSnapshotOut])
def list_scenario_calculations(
    scenario_id: str,
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
    x_organization_id: str | None = Header(default=None),
) -> list[CalculationSnapshotOut]:
    scenario_service.get_for_org(
        session, scenario_id, organization_id=_org(settings, principal, x_organization_id)
    )
    return cost_service.list_snapshots_for_scenario(session, scenario_id)


@router.get("/{scenario_id}/timeline", response_model=ScenarioTimelineOut)
def scenario_timeline(
    scenario_id: str,
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
    x_organization_id: str | None = Header(default=None),
) -> ScenarioTimelineOut:
    org = _org(settings, principal, x_organization_id)
    scenario_service.get_for_org(session, scenario_id, organization_id=org)
    return timeline_service.get_timeline(session, scenario_id, organization_id=org)
