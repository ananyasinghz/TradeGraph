"""Admin users and invites (clearance R6–R7)."""

from __future__ import annotations

from fastapi import APIRouter, Header

from backend.app.api.auth_deps import AdminDep
from backend.app.api.dependencies import SessionDep, SettingsDep
from backend.app.domain.trade import (
    AdminUserOut,
    AdminUserRoleUpdate,
    UserInviteCreate,
    UserInviteOut,
)
from backend.app.services import admin_service, org_service
from backend.app.services.auth_service import resolve_organization_id

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[AdminUserOut])
def list_users(
    session: SessionDep,
    settings: SettingsDep,
    principal: AdminDep,
    x_organization_id: str | None = Header(default=None),
) -> list[AdminUserOut]:
    org_service.ensure_demo_org(session, settings)
    org = resolve_organization_id(settings, principal, x_organization_id)
    return admin_service.list_users(session, organization_id=org)


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def patch_user_role(
    user_id: str,
    payload: AdminUserRoleUpdate,
    session: SessionDep,
    settings: SettingsDep,
    principal: AdminDep,
    x_organization_id: str | None = Header(default=None),
) -> AdminUserOut:
    org = resolve_organization_id(settings, principal, x_organization_id)
    return admin_service.set_user_role(
        session, user_id, payload, organization_id=org
    )


@router.post("/invites", response_model=UserInviteOut)
def create_invite(
    payload: UserInviteCreate,
    session: SessionDep,
    settings: SettingsDep,
    principal: AdminDep,
    x_organization_id: str | None = Header(default=None),
) -> UserInviteOut:
    org = resolve_organization_id(settings, principal, x_organization_id)
    return admin_service.create_invite(
        session, payload, principal=principal, organization_id=org
    )


@router.get("/invites", response_model=list[UserInviteOut])
def list_invites(
    session: SessionDep,
    settings: SettingsDep,
    principal: AdminDep,
    x_organization_id: str | None = Header(default=None),
) -> list[UserInviteOut]:
    org = resolve_organization_id(settings, principal, x_organization_id)
    return admin_service.list_invites(session, organization_id=org)
