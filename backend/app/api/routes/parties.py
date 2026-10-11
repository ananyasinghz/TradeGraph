"""Party CRUD routes (clearance R8)."""

from __future__ import annotations

from fastapi import APIRouter, Header

from backend.app.api.auth_deps import OperatorDep
from backend.app.api.dependencies import SessionDep, SettingsDep
from backend.app.domain.trade import PartyCreate, PartyOut, PartyUpdate
from backend.app.services import party_service
from backend.app.services.auth_service import resolve_organization_id

router = APIRouter(prefix="/parties", tags=["parties"])


@router.get("", response_model=list[PartyOut])
def list_parties(
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
    x_organization_id: str | None = Header(default=None),
) -> list[PartyOut]:
    org = resolve_organization_id(settings, principal, x_organization_id)
    return party_service.list_parties(session, organization_id=org)


@router.post("", response_model=PartyOut)
def create_party(
    payload: PartyCreate,
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
    x_organization_id: str | None = Header(default=None),
) -> PartyOut:
    org = resolve_organization_id(settings, principal, x_organization_id)
    return party_service.create_party(session, payload, organization_id=org)


@router.patch("/{party_id}", response_model=PartyOut)
def patch_party(
    party_id: str,
    payload: PartyUpdate,
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
    x_organization_id: str | None = Header(default=None),
) -> PartyOut:
    org = resolve_organization_id(settings, principal, x_organization_id)
    return party_service.update_party(
        session, party_id, payload, organization_id=org
    )
