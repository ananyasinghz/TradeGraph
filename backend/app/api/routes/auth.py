"""Auth whoami and audit log routes (S12 + R7)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.api.auth_deps import AdminDep, OperatorDep
from backend.app.api.dependencies import SessionDep, SettingsDep
from backend.app.domain.trade import AuditLogOut, AuthMeUpdate, AuthWhoAmI, UserAccountOut
from backend.app.services import auth_service, org_service
from backend.app.services.auth_service import Principal

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/whoami", response_model=AuthWhoAmI)
def whoami(
    settings: SettingsDep,
    session: SessionDep,
    principal: Annotated[Principal, Depends(auth_service.get_principal_optional)],
) -> AuthWhoAmI:
    return auth_service.whoami(settings, principal, session=session)


@router.patch("/me", response_model=UserAccountOut)
def patch_me(
    payload: AuthMeUpdate,
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
) -> UserAccountOut:
    return org_service.update_me(
        session,
        principal,
        display_name=payload.display_name,
        notification_prefs=payload.notification_prefs,
        settings=settings,
    )


@router.get("/audit", response_model=list[AuditLogOut])
def list_audit(session: SessionDep, _principal: AdminDep) -> list[AuditLogOut]:
    return auth_service.list_audit(session)
