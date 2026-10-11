"""Watchlist routes."""

from __future__ import annotations

from fastapi import APIRouter, Header, Request, Response

from backend.app.api.auth_deps import OperatorDep
from backend.app.api.dependencies import SessionDep, SettingsDep
from backend.app.domain.trade import WatchlistChange, WatchlistItemCreate, WatchlistItemOut
from backend.app.services import watchlist_service
from backend.app.services.auth_service import audit_from_request, resolve_organization_id

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


def _org(
    settings: SettingsDep,
    principal: OperatorDep,
    x_organization_id: str | None,
) -> str:
    return resolve_organization_id(settings, principal, x_organization_id)


@router.get("", response_model=list[WatchlistItemOut])
def list_watchlist(
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
    x_organization_id: str | None = Header(default=None),
) -> list[WatchlistItemOut]:
    return watchlist_service.list_items(
        session, organization_id=_org(settings, principal, x_organization_id)
    )


@router.get("/changes", response_model=list[WatchlistChange])
def watchlist_changes(
    session: SessionDep,
    settings: SettingsDep,
    principal: OperatorDep,
    x_organization_id: str | None = Header(default=None),
) -> list[WatchlistChange]:
    return watchlist_service.list_changes(
        session, organization_id=_org(settings, principal, x_organization_id)
    )


@router.post("", response_model=WatchlistItemOut)
def add_watchlist(
    payload: WatchlistItemCreate,
    session: SessionDep,
    settings: SettingsDep,
    request: Request,
    principal: OperatorDep,
    x_organization_id: str | None = Header(default=None),
) -> WatchlistItemOut:
    org = _org(settings, principal, x_organization_id)
    item = watchlist_service.add_item(session, payload, organization_id=org)
    audit_from_request(
        session,
        request,
        principal,
        action="watchlist.create",
        resource_type="watchlist",
        resource_id=item.id,
    )
    return item


@router.delete("/{item_id}", status_code=204)
def delete_watchlist(
    item_id: str,
    session: SessionDep,
    settings: SettingsDep,
    request: Request,
    principal: OperatorDep,
    x_organization_id: str | None = Header(default=None),
) -> Response:
    org = _org(settings, principal, x_organization_id)
    watchlist_service.delete_item(session, item_id, organization_id=org)
    audit_from_request(
        session,
        request,
        principal,
        action="watchlist.delete",
        resource_type="watchlist",
        resource_id=item_id,
    )
    return Response(status_code=204)
