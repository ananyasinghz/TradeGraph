"""Background-style jobs and watchlist impact notifications (S13)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.data.models import JobRun, Notification
from backend.app.domain.trade import JobRunOut, NotificationOut
from backend.app.services import source_connection_service, watchlist_service


def _now() -> datetime:
    return datetime.now(UTC)


def notification_to_out(row: Notification) -> NotificationOut:
    return NotificationOut(
        id=row.id,
        kind=row.kind,
        title=row.title,
        body=row.body,
        watchlist_item_id=row.watchlist_item_id,
        shipment_id=row.shipment_id,
        is_read=row.is_read,
        created_at=row.created_at,
    )


def list_notifications(session: Session, *, unread_only: bool = False) -> list[NotificationOut]:
    stmt = select(Notification).order_by(Notification.created_at.desc())
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    return [notification_to_out(r) for r in session.scalars(stmt).all()]


def mark_read(session: Session, notification_id: str) -> NotificationOut:
    row = session.get(Notification, notification_id)
    if row is None:
        from backend.app.core.errors import AppError

        raise AppError(
            code="NOTIFICATION_NOT_FOUND", message="Notification not found", status_code=404
        )
    row.is_read = True
    session.flush()
    return notification_to_out(row)


def run_watchlist_impact_job(session: Session) -> JobRunOut:
    started = _now()
    changes = watchlist_service.list_changes(session)
    created = 0
    for change in changes:
        for shipment_id in change.affected_shipment_ids or [None]:
            session.add(
                Notification(
                    kind="watchlist_impact",
                    title=f"Rate change {change.hs_code} {change.origin}->{change.destination}",
                    body=change.summary,
                    watchlist_item_id=change.watchlist_item_id,
                    shipment_id=shipment_id,
                    is_read=False,
                    created_at=_now(),
                )
            )
            created += 1
    finished = _now()
    job = JobRun(
        job_type="watchlist_impact",
        status="completed",
        started_at=started,
        finished_at=finished,
        summary_json={
            "changes": len(changes),
            "notifications_created": created,
        },
    )
    session.add(job)
    session.flush()
    return JobRunOut(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        started_at=job.started_at,
        finished_at=job.finished_at,
        summary=dict(job.summary_json or {}),
    )


def run_source_fetch_job(session: Session, *, run_ingest: bool = False) -> JobRunOut:
    """Phase B: fetch all enabled official-source connections."""
    started = _now()
    results = source_connection_service.fetch_all_enabled(session, run_ingest=run_ingest)
    finished = _now()
    job = JobRun(
        job_type="source_fetch",
        status="completed",
        started_at=started,
        finished_at=finished,
        summary_json={
            "fetched": len(results),
            "keys": [r.connection.key for r in results],
            "checksums": [r.checksum for r in results],
            "run_ingest": run_ingest,
        },
    )
    session.add(job)
    session.flush()
    return JobRunOut(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        started_at=job.started_at,
        finished_at=job.finished_at,
        summary=dict(job.summary_json or {}),
    )


def list_jobs(session: Session, *, limit: int = 20) -> list[JobRunOut]:
    rows = session.scalars(
        select(JobRun).order_by(JobRun.started_at.desc()).limit(limit)
    ).all()
    return [
        JobRunOut(
            id=r.id,
            job_type=r.job_type,
            status=r.status,
            started_at=r.started_at,
            finished_at=r.finished_at,
            summary=dict(r.summary_json or {}),
        )
        for r in rows
    ]
