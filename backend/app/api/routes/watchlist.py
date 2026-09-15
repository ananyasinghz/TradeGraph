"""Watchlist routes."""

from __future__ import annotations

from fastapi import APIRouter, Response

from backend.app.api.dependencies import SessionDep
from backend.app.domain.trade import WatchlistChange, WatchlistItemCreate, WatchlistItemOut
from backend.app.services import watchlist_service

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


@router.get("", response_model=list[WatchlistItemOut])
def list_watchlist(session: SessionDep) -> list[WatchlistItemOut]:
    return watchlist_service.list_items(session)


@router.get("/changes", response_model=list[WatchlistChange])
def watchlist_changes(session: SessionDep) -> list[WatchlistChange]:
    return watchlist_service.list_changes(session)


@router.post("", response_model=WatchlistItemOut)
def add_watchlist(payload: WatchlistItemCreate, session: SessionDep) -> WatchlistItemOut:
    return watchlist_service.add_item(session, payload)


@router.delete("/{item_id}", status_code=204)
def delete_watchlist(item_id: str, session: SessionDep) -> Response:
    watchlist_service.delete_item(session, item_id)
    return Response(status_code=204)
