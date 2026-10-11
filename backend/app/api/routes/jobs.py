"""Jobs and notifications routes (S13 + R7/R10)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from backend.app.api.auth_deps import OperatorDep
from backend.app.api.dependencies import SessionDep
from backend.app.domain.trade import JobRunOut, NotificationOut
from backend.app.services import jobs_service

router = APIRouter(tags=["jobs"])


@router.get("/notifications", response_model=list[NotificationOut])
def list_notifications(
    session: SessionDep,
    _principal: OperatorDep,
    unread_only: bool = False,
) -> list[NotificationOut]:
    return jobs_service.list_notifications(session, unread_only=unread_only)


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(
    notification_id: str, session: SessionDep, _principal: OperatorDep
) -> NotificationOut:
    return jobs_service.mark_read(session, notification_id)


@router.post("/jobs/watchlist-impact", response_model=JobRunOut)
def run_watchlist_impact(
    session: SessionDep,
    _principal: OperatorDep,
) -> JobRunOut:
    return jobs_service.run_watchlist_impact_job(session)


@router.post("/jobs/source-fetch", response_model=JobRunOut)
def run_source_fetch(
    session: SessionDep,
    _principal: OperatorDep,
    run_ingest: bool = Query(default=False),
) -> JobRunOut:
    return jobs_service.run_source_fetch_job(session, run_ingest=run_ingest)


@router.post("/jobs/retention-archive", response_model=JobRunOut)
def run_retention_archive(
    session: SessionDep,
    _principal: OperatorDep,
    days: int = Query(default=90, ge=1, le=3650),
) -> JobRunOut:
    return jobs_service.run_retention_archive_job(session, days=days)


@router.get("/jobs", response_model=list[JobRunOut])
def list_jobs(session: SessionDep, _principal: OperatorDep) -> list[JobRunOut]:
    return jobs_service.list_jobs(session)
