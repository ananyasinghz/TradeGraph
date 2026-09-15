"""Source connection registry + fetch API (Phase A/B/C)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from backend.app.api.dependencies import SessionDep, SettingsDep
from backend.app.domain.trade import (
    SourceConnectionOut,
    SourceFeedStatusOut,
    SourceFetchResult,
)
from backend.app.services import source_connection_service
from backend.app.services.auth_service import Principal, require_role

router = APIRouter(prefix="/source-connections", tags=["source-connections"])


@router.get("", response_model=list[SourceConnectionOut])
def list_source_connections(session: SessionDep) -> list[SourceConnectionOut]:
    source_connection_service.ensure_default_connections(session)
    return source_connection_service.list_connections(session)


@router.get("/feed-status", response_model=SourceFeedStatusOut)
def get_feed_status(session: SessionDep, settings: SettingsDep) -> SourceFeedStatusOut:
    return source_connection_service.feed_status(session, settings)


@router.post("/fetch-all", response_model=list[SourceFetchResult])
def fetch_all_source_connections(
    session: SessionDep,
    _principal: Annotated[Principal, Depends(require_role("operator"))],
    run_ingest: bool = Query(default=False),
) -> list[SourceFetchResult]:
    return source_connection_service.fetch_all_enabled(session, run_ingest=run_ingest)


@router.post("/{key}/fetch", response_model=SourceFetchResult)
def fetch_source_connection(
    key: str,
    session: SessionDep,
    _principal: Annotated[Principal, Depends(require_role("operator"))],
    run_ingest: bool = Query(default=False),
) -> SourceFetchResult:
    return source_connection_service.fetch_connection(
        session, key, run_ingest=run_ingest
    )
