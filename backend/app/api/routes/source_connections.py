"""Source connection registry + fetch API (Phase A/B/C + live feed)."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from backend.app.api.auth_deps import OperatorDep, ViewerDep
from backend.app.api.dependencies import SessionDep, SettingsDep
from backend.app.domain.trade import (
    SourceConnectionOut,
    SourceFeedStatusOut,
    SourceFetchResult,
    SourcePipelineStatusOut,
)
from backend.app.services import source_connection_service
from backend.app.services.auth_service import audit_from_request

router = APIRouter(prefix="/source-connections", tags=["source-connections"])


@router.get("", response_model=list[SourceConnectionOut])
def list_source_connections(
    session: SessionDep, settings: SettingsDep, _principal: ViewerDep
) -> list[SourceConnectionOut]:
    source_connection_service.ensure_default_connections(session, settings)
    return source_connection_service.list_connections(session)


@router.get("/feed-status", response_model=SourceFeedStatusOut)
def get_feed_status(
    session: SessionDep, settings: SettingsDep, _principal: ViewerDep
) -> SourceFeedStatusOut:
    return source_connection_service.feed_status(session, settings)


@router.get("/{key}/pipeline-status", response_model=SourcePipelineStatusOut)
def get_pipeline_status(
    key: str, session: SessionDep, settings: SettingsDep, _principal: ViewerDep
) -> SourcePipelineStatusOut:
    return source_connection_service.connection_pipeline_status(session, key, settings)


@router.post("/fetch-all", response_model=list[SourceFetchResult])
def fetch_all_source_connections(
    session: SessionDep,
    request: Request,
    principal: OperatorDep,
    settings: SettingsDep,
    run_ingest: bool | None = Query(default=None),
) -> list[SourceFetchResult]:
    out = source_connection_service.fetch_all_enabled(
        session, run_ingest=run_ingest, settings=settings
    )
    audit_from_request(
        session,
        request,
        principal,
        action="source_connections.fetch_all",
        resource_type="source_connection",
    )
    return out


@router.post("/{key}/fetch", response_model=SourceFetchResult)
def fetch_source_connection(
    key: str,
    session: SessionDep,
    request: Request,
    principal: OperatorDep,
    settings: SettingsDep,
    run_ingest: bool | None = Query(default=None),
) -> SourceFetchResult:
    out = source_connection_service.fetch_connection(
        session, key, run_ingest=run_ingest, settings=settings
    )
    audit_from_request(
        session,
        request,
        principal,
        action="source_connections.fetch",
        resource_type="source_connection",
        resource_id=key,
    )
    return out
