"""Jobs and notifications routes (S13)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from backend.app.api.dependencies import SessionDep
from backend.app.domain.trade import JobRunOut, NotificationOut
from backend.app.services import jobs_service
from backend.app.services.auth_service import Principal, require_role

router = APIRouter(tags=["jobs"])


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(
    session: SessionDep,
    unread_only: bool = False,
) -> list[NotificationOut]:
    return jobs_service.list_notifications(session, unread_only=unread_only)


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(
    notification_id: str, session: SessionDep
) -> NotificationOut:
    return jobs_service.mark_read(session, notification_id)


@router.post("/jobs/watchlist-impact", response_model=JobRunOut)
def run_watchlist_impact(
    session: SessionDep,
    _principal: Annotated[Principal, Depends(require_role("operator"))],
) -> JobRunOut:
    return jobs_service.run_watchlist_impact_job(session)


@router.post("/jobs/source-fetch", response_model=JobRunOut)
def run_source_fetch(
    session: SessionDep,
    _principal: Annotated[Principal, Depends(require_role("operator"))],
    run_ingest: bool = Query(default=False),
) -> JobRunOut:
    return jobs_service.run_source_fetch_job(session, run_ingest=run_ingest)


@router.get("/jobs", response_model=list[JobRunOut])
def list_jobs(session: SessionDep) -> list[JobRunOut]:
    return jobs_service.list_jobs(session)
