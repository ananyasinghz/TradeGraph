"""Home dashboard API."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter

from backend.app.api.auth_deps import ViewerDep
from backend.app.api.dependencies import SessionDep, SettingsDep
from backend.app.domain.trade import DashboardOut
from backend.app.services import dashboard_service

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardOut)
def get_dashboard(
    session: SessionDep,
    settings: SettingsDep,
    _principal: ViewerDep,
    queue: Literal["blocked", "alerts", "all"] = "all",
) -> DashboardOut:
    return dashboard_service.build_dashboard(session, settings, queue=queue)
