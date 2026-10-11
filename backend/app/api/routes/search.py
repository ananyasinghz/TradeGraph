"""Org-scoped search (clearance R11)."""

from __future__ import annotations

from fastapi import APIRouter, Header, Query

from backend.app.api.auth_deps import OperatorDep
from backend.app.api.dependencies import SessionDep, SettingsDep
from backend.app.domain.trade import SearchOut
from backend.app.services import search_service
from backend.app.services.auth_service import resolve_organization_id

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchOut)
def search(
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
    q: str = Query(default="", min_length=0, max_length=200),
    x_organization_id: str | None = Header(default=None),
) -> SearchOut:
    org = resolve_organization_id(settings, principal, x_organization_id)
    return search_service.search(session, q, organization_id=org)
