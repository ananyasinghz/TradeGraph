"""Official source connection registry + fetch (Phase A/B + IF-11a honesty)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import AppError
from backend.app.data.models import SourceConnection, SourceDocument, TariffRate
from backend.app.domain.trade import (
    SourceConnectionOut,
    SourceFeedStatusOut,
    SourceFetchResult,
)
from backend.app.services import source_adapters

ROOT = Path(__file__).resolve().parents[3]

SourceKind = Literal["none", "curated_mirror", "verified_published", "live_monitored"]

# Adapters that could someday power live_monitored (none shipped yet).
_LIVE_ADAPTERS = frozenset({"live_http_api", "government_live_feed"})


def _now() -> datetime:
    return datetime.now(UTC)


def _connection_out(row: SourceConnection) -> SourceConnectionOut:
    return SourceConnectionOut(
        id=row.id,
        key=row.key,
        title=row.title,
        publisher=row.publisher,
        fetch_mode=row.fetch_mode,
        source_url=row.source_url,
        local_path=row.local_path,
        enabled=row.enabled,
        origin=row.origin,
        destination=row.destination,
        hs_chapter=row.hs_chapter,
        adapter=row.adapter,
        honesty_label=row.honesty_label,
        notes=row.notes,
        last_checked_at=row.last_checked_at,
        last_success_at=row.last_success_at,
        last_error=row.last_error,
        last_checksum=row.last_checksum,
        last_archive_path=row.last_archive_path,
        last_source_document_id=row.last_source_document_id,
        created_at=row.created_at,
    )


def list_connections(session: Session) -> list[SourceConnectionOut]:
    rows = session.scalars(
        select(SourceConnection).order_by(SourceConnection.key)
    ).all()
    return [_connection_out(r) for r in rows]


def get_connection(session: Session, key: str) -> SourceConnection:
    row = session.scalar(select(SourceConnection).where(SourceConnection.key == key))
    if row is None:
        raise AppError(
            code="SOURCE_CONNECTION_NOT_FOUND",
            message=f"Source connection not found: {key}",
            status_code=404,
        )
    return row


def ensure_default_connections(session: Session) -> None:
    """Idempotent seed of curated mirrors + local HS PDF archives + optional live HTTP."""
    settings = get_settings()
    defaults: list[dict[str, str | None]] = [
        {
            "key": "cbic_notification_2026_q3",
            "title": "CBIC-style customs notice archive (Q3 2026 curated mirror)",
            "publisher": "CBIC (illustrative curated mirror for TradeGraph)",
            "fetch_mode": "curated_mirror",
            "adapter": "curated_json_mirror",
            "source_url": "https://example.invalid/tradegraph/archives/cbic-2026-q3",
            "local_path": "config/trade/fixtures/cbic/cbic_notification_2026_q3.json",
            "honesty_label": "Official-source-backed curated mirror (not a live CBIC API)",
            "notes": (
                "Bytes come from the local curated JSON archive. HTTP URL is "
                "documentary only unless fetch_mode is switched to http_get."
            ),
            "hs_chapter": "61",
        },
        {
            "key": "itc_hs_2022_pdf",
            "title": "ITC-HS 2022 nomenclature (local PDF archive)",
            "publisher": "India Customs / DGFT style ITC-HS pack (local archive)",
            "fetch_mode": "local_archive",
            "adapter": "local_pdf_archive",
            "source_url": None,
            "local_path": "config/trade/source/ITC-HS_2022.pdf",
            "honesty_label": (
                "Local official-style PDF archive — not a live government API "
                "until HTTP refresh succeeds."
            ),
            "notes": "Primary HS nomenclature PDF for full-catalog classification.",
            "hs_chapter": None,
        },
        {
            "key": "hs_code_mapping_pdf",
            "title": "HS code mapping crosswalk (local PDF archive)",
            "publisher": "TradeGraph local mapping pack",
            "fetch_mode": "local_archive",
            "adapter": "local_pdf_archive",
            "source_url": None,
            "local_path": "config/trade/source/HS_Code_Mappin.pdf",
            "honesty_label": (
                "Local official-style PDF archive — not a live government API "
                "until HTTP refresh succeeds."
            ),
            "notes": "Mapping / crosswalk aid for HS nomenclature load.",
            "hs_chapter": None,
        },
    ]
    if settings.live_tariff_http_url:
        defaults.append(
            {
                "key": "live_tariff_http",
                "title": "Live tariff JSON HTTP feed",
                "publisher": "Configured TRADE_LIVE_TARIFF_HTTP_URL",
                "fetch_mode": "http_get",
                "adapter": "live_http_api",
                "source_url": settings.live_tariff_http_url,
                "local_path": None,
                "honesty_label": "Live HTTP feed (allowlisted host only)",
                "notes": "Requires TRADE_LIVE_FEED_ENABLED and allowlisted host.",
                "hs_chapter": None,
            }
        )
    now = _now()
    for item in defaults:
        existing = session.scalar(
            select(SourceConnection).where(SourceConnection.key == item["key"])
        )
        if existing is not None:
            continue
        session.add(
            SourceConnection(
                key=str(item["key"]),
                title=str(item["title"]),
                publisher=str(item["publisher"]),
                fetch_mode=str(item["fetch_mode"]),
                adapter=str(item["adapter"]),
                source_url=item.get("source_url"),
                local_path=item.get("local_path"),
                enabled=True,
                origin="BD",
                destination="IN",
                hs_chapter=item.get("hs_chapter") or "61",
                honesty_label=str(item["honesty_label"]),
                notes=item.get("notes"),
                created_at=now,
            )
        )
    session.flush()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _approved_count(session: Session) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(TariffRate)
            .where(
                TariffRate.status == "active",
                TariffRate.data_quality.in_(("demo_verified", "source_verified")),
            )
        )
        or 0
    )


def derive_source_connection_kind(
    session: Session,
    *,
    configured: bool,
    last_success: datetime | None,
    enabled: list[SourceConnection],
    settings: Settings,
) -> tuple[SourceKind, str, bool, str]:
    """
    Return (kind, label, live_government_feed, live_reason).

    Curated mirrors never claim live_government_feed=true (IF-11a).
    """
    approved = _approved_count(session)
    has_live_adapter = any(r.adapter in _LIVE_ADAPTERS for r in enabled)

    if approved > 0:
        kind: SourceKind = "verified_published"
        label = "Verified source"
    elif configured and last_success is not None:
        kind = "curated_mirror"
        label = "Curated demonstration source"
    elif configured:
        kind = "curated_mirror"
        label = "Official source not connected"
    else:
        kind = "none"
        label = "Official source not connected"

    live = False
    live_reason = "Live government feed disabled (TRADE_LIVE_FEED_ENABLED=false)."
    if not has_live_adapter:
        live_reason = (
            "Curated demonstration source — not a live government API. "
            "Approve a published batch for Verified source status."
        )
        if settings.live_feed_enabled:
            live_reason = (
                "TRADE_LIVE_FEED_ENABLED is on, but connections use curated mirrors only. "
                "live_government_feed stays false until a real live adapter exists."
            )
    elif settings.live_feed_enabled and configured and last_success is not None:
        max_age = timedelta(hours=settings.live_feed_max_age_hours)
        age = _now() - last_success
        if age <= max_age:
            live = True
            kind = "live_monitored"
            label = "Live monitored"
            live_reason = "Live adapter freshness SLA met."
        else:
            live_reason = (
                f"Live feed enabled but last success is stale "
                f"({int(age.total_seconds() // 3600)}h ago)."
            )
    elif settings.live_feed_enabled and configured:
        live_reason = "Live feed enabled but no successful fetch yet."
    elif settings.live_feed_enabled:
        live_reason = "Live feed enabled but no source connections configured."

    return kind, label, live, live_reason


def feed_status(session: Session, settings: Settings | None = None) -> SourceFeedStatusOut:
    settings = settings or get_settings()
    ensure_default_connections(session)
    rows = session.scalars(select(SourceConnection)).all()
    enabled = [r for r in rows if r.enabled]
    last_success = max(
        (_as_utc(r.last_success_at) for r in enabled if r.last_success_at is not None),
        default=None,
    )
    configured = len(enabled) > 0
    if not configured:
        connection_label = "Not configured"
    elif last_success is None:
        connection_label = f"Configured · {len(enabled)} source(s) · never fetched"
    else:
        connection_label = (
            f"Configured · {len(enabled)} source(s) · last fetch "
            f"{last_success.isoformat()}"
        )

    kind, kind_label, live, live_reason = derive_source_connection_kind(
        session,
        configured=configured,
        last_success=last_success,
        enabled=enabled,
        settings=settings,
    )
    has_live_adapter = any(r.adapter in _LIVE_ADAPTERS for r in enabled)

    return SourceFeedStatusOut(
        configured=configured,
        enabled_connection_count=len(enabled),
        official_source_connection=connection_label,
        source_connection_kind=kind,
        source_connection_label=kind_label,
        live_government_feed=live,
        live_feed_enabled_setting=settings.live_feed_enabled,
        live_feed_reason=live_reason,
        last_successful_fetch_at=last_success,
        scheduler_interval_minutes=settings.source_fetch_interval_minutes,
        has_live_adapter=has_live_adapter,
    )


def fetch_connection(
    session: Session,
    key: str,
    *,
    run_ingest: bool = False,
) -> SourceFetchResult:
    from backend.app.services import ingestion_service

    row = get_connection(session, key)
    now = _now()
    row.last_checked_at = now
    try:
        resolved = source_adapters.resolve_payload(
            adapter=row.adapter,
            fetch_mode=row.fetch_mode,
            local_path=row.local_path,
            source_url=row.source_url,
            allowlist=get_settings().http_source_allowlist
            if row.adapter.lower() in _LIVE_ADAPTERS
            or row.fetch_mode.lower() == "http_get"
            else None,
        )
        checksum = hashlib.sha256(resolved.content).hexdigest()
        archive_dir = ROOT / "data" / "processed" / "source_archives"
        archive_dir.mkdir(parents=True, exist_ok=True)
        safe_name = f"{row.key}_{checksum[:12]}.bin"
        archive_path = archive_dir / safe_name
        if not archive_path.exists():
            archive_path.write_bytes(resolved.content)
        rel_archive = str(archive_path.relative_to(ROOT)).replace("\\", "/")

        is_live_adapter = row.adapter.lower() in _LIVE_ADAPTERS
        source_id = f"src_fetch_{row.key}"
        existing = session.get(SourceDocument, source_id)
        honesty = (
            "Live HTTP fetch archived locally. Approve an ingest batch before "
            "treating rates as verified."
            if is_live_adapter
            else (
                "Curated / local archive fetch only — not a live government API. "
                "Approve an ingest batch before treating rates as verified."
            )
        )
        if existing is None:
            session.add(
                SourceDocument(
                    id=source_id,
                    title=row.title,
                    publisher=row.publisher,
                    url=row.source_url,
                    retrieved_at=now,
                    effective_from=None,
                    file_path=rel_archive,
                    archive_path=rel_archive,
                    checksum=checksum,
                    status="fetched",
                    notes=honesty,
                    source_kind="live_feed" if is_live_adapter else "curated_dataset",
                    live_claim=is_live_adapter,
                    fetched_at=now,
                )
            )
        else:
            existing.checksum = checksum
            existing.file_path = rel_archive
            existing.archive_path = rel_archive
            existing.fetched_at = now
            existing.status = "fetched"
            existing.live_claim = is_live_adapter
            existing.notes = honesty
            existing.source_kind = "live_feed" if is_live_adapter else "curated_dataset"

        row.last_success_at = now
        row.last_error = None
        row.last_checksum = checksum
        row.last_archive_path = rel_archive
        row.last_source_document_id = source_id
        session.flush()

        ingest_batch_id = None
        if run_ingest and row.adapter.lower() not in {"local_pdf_archive"}:
            from backend.app.domain.trade import IngestRunRequest

            ingest_path = row.local_path or rel_archive
            batch = ingestion_service.run_ingest(
                session,
                IngestRunRequest(
                    source_key=row.key,
                    archive_path=ingest_path,
                    force=True,
                ),
            )
            ingest_batch_id = batch.id

        session.flush()
        return SourceFetchResult(
            connection=_connection_out(row),
            checksum=checksum,
            archive_path=rel_archive,
            source_document_id=source_id,
            resolved_from=resolved.resolved_from,
            ingest_batch_id=ingest_batch_id,
            message=(
                "Fetched source into local archive. Review and "
                "approve ingest proposals before treating rates as verified."
            ),
        )
    except Exception as exc:
        row.last_error = str(exc)[:2000]
        session.flush()
        raise


def fetch_all_enabled(
    session: Session, *, run_ingest: bool = False
) -> list[SourceFetchResult]:
    ensure_default_connections(session)
    rows = session.scalars(
        select(SourceConnection).where(SourceConnection.enabled.is_(True))
    ).all()
    results: list[SourceFetchResult] = []
    for row in rows:
        results.append(fetch_connection(session, row.key, run_ingest=run_ingest))
    return results
