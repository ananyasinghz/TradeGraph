"""System status and honesty coverage API (PRODUCT_USABILITY_PLAN S1)."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.auth_deps import ViewerDep
from backend.app.api.dependencies import SessionDep, SettingsDep
from backend.app.domain.trade import SystemStatusOut
from backend.app.services import system_status_service

router = APIRouter(tags=["system"])


@router.get("/system/status", response_model=SystemStatusOut)
def get_system_status(
    session: SessionDep, settings: SettingsDep, _principal: ViewerDep
) -> SystemStatusOut:
    return system_status_service.build_system_status(session, settings)
