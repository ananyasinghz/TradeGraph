"""Auth whoami and audit log routes (S12)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.api.dependencies import SessionDep, SettingsDep
from backend.app.domain.trade import AuditLogOut, AuthWhoAmI
from backend.app.services import auth_service
from backend.app.services.auth_service import Principal, require_role

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/whoami", response_model=AuthWhoAmI)
def whoami(
    settings: SettingsDep,
    principal: Annotated[Principal, Depends(auth_service.get_principal)],
) -> AuthWhoAmI:
    return auth_service.whoami(settings, principal)


@router.get("/audit", response_model=list[AuditLogOut])
def list_audit(
    session: SessionDep,
    _principal: Annotated[Principal, Depends(require_role("reviewer"))],
) -> list[AuditLogOut]:
    return auth_service.list_audit(session)
