"""Source archive, checksum, and lifecycle status machine (no live claim)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.data.models import SourceDocument
from backend.app.domain.trade import (
    SourceArchiveRequest,
    SourceDocumentOut,
    SourceStatusTransition,
)

SOURCE_STATUSES = frozenset(
    {
        "unverified",
        "fetched",
        "parsed",
        "validation_failed",
        "awaiting_review",
        "approved",
        "published",
        "superseded",
        "rejected",
        "expired",
        "active",  # legacy alias for published
    }
)

_TRANSITIONS: dict[str, frozenset[str]] = {
    "unverified": frozenset({"fetched", "rejected"}),
    "fetched": frozenset({"parsed", "validation_failed", "rejected"}),
    "parsed": frozenset({"awaiting_review", "validation_failed"}),
    "validation_failed": frozenset({"fetched", "rejected"}),
    "awaiting_review": frozenset({"approved", "rejected"}),
    "approved": frozenset({"published", "rejected"}),
    "published": frozenset({"superseded", "expired"}),
    "active": frozenset({"published", "superseded", "expired"}),
    "superseded": frozenset(),
    "rejected": frozenset(),
    "expired": frozenset(),
}

NO_LIVE_NOTICE = (
    "TradeGraph does not claim a live government feed. Sources are archived "
    "manually refreshed curated datasets unless a scheduler + approve pipeline is configured."
)


def _now() -> datetime:
    return datetime.now(UTC)


def normalize_status(status: str) -> str:
    return "published" if status == "active" else status


def source_to_out(doc: SourceDocument) -> SourceDocumentOut:
    return SourceDocumentOut(
        id=doc.id,
        title=doc.title,
        publisher=doc.publisher,
        url=doc.url,
        effective_from=doc.effective_from,
        status=normalize_status(doc.status),
        notes=doc.notes,
        checksum=doc.checksum,
        archive_path=doc.archive_path or doc.file_path,
        content_type=doc.content_type,
        source_kind=doc.source_kind or "curated_dataset",
        live_claim=False,  # never advertise live feeds
        live_government_feed=False,
        fetched_at=doc.fetched_at,
        parsed_at=doc.parsed_at,
        reviewed_at=doc.reviewed_at,
        published_at=doc.published_at,
        superseded_by=doc.superseded_by,
        review_notes=doc.review_notes,
        honesty_notice=NO_LIVE_NOTICE,
    )


def list_sources(session: Session) -> list[SourceDocumentOut]:
    rows = session.scalars(select(SourceDocument).order_by(SourceDocument.id)).all()
    return [source_to_out(r) for r in rows]


def get_source(session: Session, source_id: str) -> SourceDocumentOut:
    row = session.get(SourceDocument, source_id)
    if row is None:
        raise AppError(code="SOURCE_NOT_FOUND", message="Source not found", status_code=404)
    return source_to_out(row)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 64)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def archive_source(session: Session, payload: SourceArchiveRequest) -> SourceDocumentOut:
    """Register a local archive file with checksum; never sets live_claim."""
    path = Path(payload.archive_path)
    if not path.is_file():
        raise AppError(
            code="ARCHIVE_NOT_FOUND",
            message=f"Archive file not found: {payload.archive_path}",
            status_code=400,
        )
    checksum = _sha256_file(path)
    now = _now()
    source_id = payload.source_id or f"src_archive_{checksum[:12]}"
    existing = session.get(SourceDocument, source_id)
    if existing is not None:
        raise AppError(
            code="SOURCE_EXISTS",
            message=f"Source id already exists: {source_id}",
            status_code=409,
        )
    row = SourceDocument(
        id=source_id,
        title=payload.title,
        publisher=payload.publisher,
        url=payload.url,
        retrieved_at=now,
        effective_from=payload.effective_from,
        file_path=str(path),
        archive_path=str(path),
        checksum=checksum,
        status="fetched",
        notes=payload.notes,
        content_type=payload.content_type or "application/octet-stream",
        source_kind="manual_archive",
        live_claim=False,
        fetched_at=now,
    )
    session.add(row)
    session.flush()
    return source_to_out(row)


def transition_status(
    session: Session, source_id: str, payload: SourceStatusTransition
) -> SourceDocumentOut:
    row = session.get(SourceDocument, source_id)
    if row is None:
        raise AppError(code="SOURCE_NOT_FOUND", message="Source not found", status_code=404)
    target = payload.status
    if target not in SOURCE_STATUSES or target == "active":
        raise AppError(
            code="INVALID_SOURCE_STATUS",
            message=f"Unsupported target status: {target}",
            status_code=400,
        )
    current = normalize_status(row.status)
    allowed = _TRANSITIONS.get(row.status, _TRANSITIONS.get(current, frozenset()))
    if target not in allowed:
        raise AppError(
            code="INVALID_STATUS_TRANSITION",
            message=f"Cannot transition source from {current} to {target}",
            status_code=400,
            details={"from": current, "to": target, "allowed": sorted(allowed)},
        )
    now = _now()
    row.status = target
    if payload.notes:
        row.review_notes = payload.notes
    if target == "fetched":
        row.fetched_at = now
    elif target == "parsed":
        row.parsed_at = now
    elif target in {"approved", "rejected"}:
        row.reviewed_at = now
    elif target == "published":
        row.published_at = now
        row.reviewed_at = row.reviewed_at or now
    row.live_claim = False
    session.flush()
    return source_to_out(row)
