"""Background-style jobs and watchlist impact notifications (S13 + R7/R10)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.data.models import JobRun, Notification, Organization, UserAccount
from backend.app.domain.trade import JobRunOut, NotificationOut
from backend.app.services import email_service, source_connection_service, watchlist_service


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
        user_id=getattr(row, "user_id", None),
        organization_id=getattr(row, "organization_id", None),
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


def _prefs_allow_in_app(prefs: dict | None) -> bool:
    if not prefs:
        return True
    return bool(prefs.get("in_app", True))


def _prefs_allow_email(prefs: dict | None) -> bool:
    if not prefs:
        return True
    return bool(prefs.get("watchlist_email", prefs.get("email", True)))


def run_watchlist_impact_job(session: Session) -> JobRunOut:
    started = _now()
    changes = watchlist_service.list_changes(session)
    users = session.scalars(select(UserAccount)).all()
    created = 0
    emailed = 0
    for change in changes:
        title = f"Rate change {change.hs_code} {change.origin}->{change.destination}"
        body = change.summary
        shipment_ids = change.affected_shipment_ids or [None]
        for user in users:
            prefs = dict(user.notification_prefs or {})
            if not _prefs_allow_in_app(prefs):
                continue
            for shipment_id in shipment_ids:
                session.add(
                    Notification(
                        kind="watchlist_impact",
                        title=title,
                        body=body,
                        watchlist_item_id=change.watchlist_item_id,
                        shipment_id=shipment_id,
                        user_id=user.id,
                        organization_id=user.organization_id,
                        is_read=False,
                        created_at=_now(),
                    )
                )
                created += 1
            if _prefs_allow_email(prefs):
                email_service.send_email(
                    to=user.email,
                    subject=title,
                    body=body,
                )
                emailed += 1
            org = session.get(Organization, user.organization_id)
            webhook = getattr(org, "slack_webhook_url", None) if org else None
            email_service.notify_slack(f"{title}\n{body}", webhook_url=webhook)
    finished = _now()
    job = JobRun(
        job_type="watchlist_impact",
        status="completed",
        started_at=started,
        finished_at=finished,
        summary_json={
            "changes": len(changes),
            "notifications_created": created,
            "emails_sent": emailed,
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


def run_retention_archive_job(session: Session, *, days: int = 90) -> JobRunOut:
    from backend.app.services import shipment_service

    started = _now()
    result = shipment_service.retention_archive(session, days=days)
    finished = _now()
    job = JobRun(
        job_type="retention_archive",
        status="completed",
        started_at=started,
        finished_at=finished,
        summary_json=result,
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


def run_source_fetch_job(session: Session, *, run_ingest: bool | None = None) -> JobRunOut:
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
