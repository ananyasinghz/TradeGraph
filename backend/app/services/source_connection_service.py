"""Official source connection registry + fetch (Phase A/B + live feed path)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import AppError
from backend.app.data.models import DataVersion, IngestionBatch, SourceConnection, SourceDocument, TariffRate
from backend.app.domain.trade import (
    SourceConnectionOut,
    SourceFeedStatusOut,
    SourceFetchResult,
    SourcePipelineStatusOut,
)
from backend.app.services import live_feed_normalize, official_doc_normalize, source_adapters

ROOT = Path(__file__).resolve().parents[3]

SourceKind = Literal["none", "curated_mirror", "verified_published", "live_monitored"]

_LIVE_ADAPTERS = frozenset({"live_http_api", "government_live_feed"})
_OFFICIAL_DOC_ADAPTERS = frozenset(source_adapters.OFFICIAL_DOCUMENT_ADAPTERS)
_INGEST_AUTO_ADAPTERS = _LIVE_ADAPTERS | _OFFICIAL_DOC_ADAPTERS

# Locked verified CBIC Ch61 IGST path (LIVE_SOURCE_VERIFICATION_CBIC_CH61.md).
VERIFIED_CBIC_CH61_KEY = "cbic_ch61_igst_notif_9_2025"
VERIFIED_CBIC_CH61_PORTAL = "https://courier.cbic.gov.in/notification.jsp"
VERIFIED_CBIC_CH61_DOCUMENT = (
    "https://courier.cbic.gov.in/advisory/2025/"
    "NOTIFICATION%20NO.%209_2025-INTEGRATED%20TAX%20(RATE)%20-1759486719.pdf"
)


def _now() -> datetime:
    return datetime.now(UTC)


def _pipeline(row: SourceConnection) -> dict[str, Any]:
    raw = row.capabilities_json
    if isinstance(raw, dict) and isinstance(raw.get("pipeline"), dict):
        return dict(raw["pipeline"])
    return {}


def _set_pipeline(row: SourceConnection, updates: dict[str, Any]) -> None:
    base: dict[str, Any] = {}
    if isinstance(row.capabilities_json, dict):
        base = dict(row.capabilities_json)
    pipe = dict(base.get("pipeline") or {})
    pipe.update(updates)
    base["pipeline"] = pipe
    row.capabilities_json = base


def _connection_lane(row: SourceConnection) -> Literal["live_official", "demo_fixture", "local_archive", "other"]:
    if row.key in {VERIFIED_CBIC_CH61_KEY, "cbic_customs_docs", "cbic_taxinfo_docs", "icegate_public_docs"}:
        return "live_official"
    if row.adapter in _LIVE_ADAPTERS or row.adapter in _OFFICIAL_DOC_ADAPTERS:
        return "live_official"
    if row.key == "cbic_notification_2026_q3" or row.fetch_mode == "curated_mirror":
        return "demo_fixture"
    if row.fetch_mode == "local_archive" or "pdf" in (row.adapter or "").lower():
        return "local_archive"
    return "other"


def _connection_out(
    row: SourceConnection,
    *,
    settings: Settings | None = None,
    published_rates_usable: bool = True,
) -> SourceConnectionOut:
    settings = settings or get_settings()
    pipe = _pipeline(row)
    caps = dict(row.capabilities_json or {}) if isinstance(row.capabilities_json, dict) else {}
    document_url = caps.get("document_url")
    lane = _connection_lane(row)
    sched_on = bool(settings.source_fetch_scheduler_enabled)
    is_monitored = lane == "live_official" or row.adapter in _LIVE_ADAPTERS
    refresh_mode: Literal["manual_only", "scheduled"] = (
        "scheduled" if sched_on and is_monitored else "manual_only"
    )
    sla = (
        int(settings.live_feed_max_age_hours)
        if is_monitored
        else (24 * 30 if lane == "demo_fixture" else None)
    )
    next_attempt = None
    fetch_overdue = False
    if refresh_mode == "scheduled" and row.last_success_at is not None:
        next_attempt = _as_utc(row.last_success_at) + timedelta(
            minutes=settings.source_fetch_interval_minutes
        )
        fetch_overdue = _now() > next_attempt
    elif refresh_mode == "scheduled" and row.last_success_at is None and row.enabled:
        fetch_overdue = True
    return SourceConnectionOut(
        id=row.id,
        key=row.key,
        title=row.title,
        publisher=row.publisher,
        fetch_mode=row.fetch_mode,
        source_url=row.source_url,
        document_url=str(document_url) if document_url else None,
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
        pipeline_stage=str(pipe.get("stage") or ("configured" if row.source_url or row.local_path else "none")),
        last_final_url=pipe.get("final_url"),
        last_content_type=pipe.get("content_type"),
        last_http_status=pipe.get("http_status"),
        last_semantic_fingerprint=pipe.get("semantic_fingerprint"),
        last_ingest_batch_id=pipe.get("ingest_batch_id"),
        last_published_version_id=pipe.get("published_version_id"),
        last_published_at=_parse_dt(pipe.get("published_at")),
        next_attempt_at=next_attempt,
        refresh_mode=refresh_mode,
        fetch_overdue=fetch_overdue,
        freshness_sla_hours=sla,
        published_rates_usable=published_rates_usable,
        lane=lane,
    )


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _as_utc(value)
    try:
        return _as_utc(datetime.fromisoformat(str(value).replace("Z", "+00:00")))
    except ValueError:
        return None


def list_connections(session: Session) -> list[SourceConnectionOut]:
    settings = get_settings()
    ensure_default_connections(session, settings)
    usable = _approved_count(session) > 0 or session.scalar(
        select(func.count())
        .select_from(TariffRate)
        .where(TariffRate.status == "active")
    )
    rows = session.scalars(
        select(SourceConnection).order_by(SourceConnection.key)
    ).all()
    return [
        _connection_out(r, settings=settings, published_rates_usable=bool(usable))
        for r in rows
    ]


def get_connection(session: Session, key: str) -> SourceConnection:
    row = session.scalar(select(SourceConnection).where(SourceConnection.key == key))
    if row is None:
        raise AppError(
            code="SOURCE_CONNECTION_NOT_FOUND",
            message=f"Source connection not found: {key}",
            status_code=404,
        )
    return row


def ensure_default_connections(session: Session, settings: Settings | None = None) -> None:
    """Idempotent seed of curated mirrors + local HS PDF archives + optional live HTTP."""
    settings = settings or get_settings()
    # Always-present verified Ch61 IGST connection (distinct from curated Q3 fixture).
    verified_portal = settings.cbic_customs_url or VERIFIED_CBIC_CH61_PORTAL
    verified_doc = settings.cbic_customs_document_url or VERIFIED_CBIC_CH61_DOCUMENT
    defaults: list[dict[str, str | None]] = [
        {
            "key": VERIFIED_CBIC_CH61_KEY,
            "title": "CBIC Ch61 IGST — Notification 9/2025 (verified official PDF)",
            "publisher": "CBIC Courier / Integrated Tax (Rate)",
            "fetch_mode": "official_document",
            "adapter": "official_document_http",
            "source_url": verified_portal,
            "document_url": verified_doc,
            "local_path": None,
            "honesty_label": (
                "Official IGST Schedule I (Ch61 knitted apparel) — not a BCD tariff pack; "
                "partial component update only after human approve"
            ),
            "notes": (
                "Pinned Notification No. 9/2025-Integrated Tax (Rate). Refresh fetches the "
                "remote PDF (allowlist courier.cbic.gov.in). Never confuses with curated Q3 JSON."
            ),
            "hs_chapter": "61",
        },
        {
            "key": "cbic_notification_2026_q3",
            "title": "Demo fixture — CBIC-style Q3 2026 curated JSON mirror",
            "publisher": "TradeGraph demo fixture (not live CBIC)",
            "fetch_mode": "curated_mirror",
            "adapter": "curated_json_mirror",
            "source_url": "https://example.invalid/tradegraph/archives/cbic-2026-q3",
            "local_path": "config/trade/fixtures/cbic/cbic_notification_2026_q3.json",
            "honesty_label": "Demo curated fixture — not a live government feed",
            "notes": (
                "Local JSON only. Use Demo fixture panel to promote. Do not treat as live CBIC."
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
                "hs_chapter": "61",
            }
        )
    official_seeds: list[tuple[str | None, str | None, dict[str, str | None]]] = [
        (
            settings.cbic_taxinfo_url,
            settings.cbic_taxinfo_document_url,
            {
                "key": "cbic_taxinfo_docs",
                "title": "CBIC Tax Information Portal (official documents)",
                "publisher": "CBIC Tax Information Portal",
                "fetch_mode": "official_document",
                "adapter": "official_document_http",
                "honesty_label": (
                    "Official CBIC portal document fetch (HTML/PDF) — not a public tariff API"
                ),
                "notes": "Pinned document URL used when index listing is not a rate pack.",
                "hs_chapter": "61",
            },
        ),
        (
            settings.cbic_customs_url,
            settings.cbic_customs_document_url,
            {
                "key": "cbic_customs_docs",
                "title": "CBIC Customs official resources",
                "publisher": "CBIC Customs",
                "fetch_mode": "official_document",
                "adapter": "official_document_http",
                "honesty_label": (
                    "Official CBIC customs document fetch (HTML/PDF) — human review required"
                ),
                "notes": "Tariff notifications/circulars; Chapter 61 BD→IN extract when clear.",
                "hs_chapter": "61",
            },
        ),
        (
            settings.icegate_public_url,
            settings.icegate_public_document_url,
            {
                "key": "icegate_public_docs",
                "title": "ICEGATE public reference pages",
                "publisher": "ICEGATE (public pages only)",
                "fetch_mode": "official_document",
                "adapter": "official_document_http",
                "honesty_label": (
                    "ICEGATE public page monitor — no login/API; preferential calculator not automated"
                ),
                "notes": "Secondary evidence only; not ECCS/filing APIs.",
                "hs_chapter": "61",
            },
        ),
    ]
    for portal_url, document_url, meta in official_seeds:
        if not portal_url:
            continue
        defaults.append(
            {
                **meta,
                "source_url": portal_url,
                "local_path": None,
                "document_url": document_url,
            }
        )
    now = _now()

    def _path_exists(rel: str | None) -> bool:
        if not rel:
            return False
        p = Path(rel)
        if not p.is_absolute():
            p = ROOT / p
        return p.is_file()

    for item in defaults:
        existing = session.scalar(
            select(SourceConnection).where(SourceConnection.key == item["key"])
        )
        if existing is not None:
            if item["key"] == "live_tariff_http" and settings.live_tariff_http_url:
                existing.source_url = settings.live_tariff_http_url
                existing.adapter = "live_http_api"
                existing.fetch_mode = "http_get"
                existing.enabled = True
            if item.get("adapter") in _OFFICIAL_DOC_ADAPTERS and item.get("source_url"):
                existing.source_url = item.get("source_url")
                existing.adapter = str(item["adapter"])
                existing.fetch_mode = str(item["fetch_mode"])
                existing.enabled = True
                if item.get("honesty_label"):
                    existing.honesty_label = str(item["honesty_label"])
                caps = dict(existing.capabilities_json or {})
                if item.get("document_url"):
                    caps["document_url"] = item["document_url"]
                pipe = dict(caps.get("pipeline") or {})
                pipe.setdefault("stage", "configured")
                caps["pipeline"] = pipe
                existing.capabilities_json = caps
            desired_path = item.get("local_path")
            if desired_path:
                current = existing.local_path
                if current != desired_path and (
                    not _path_exists(current) or _path_exists(desired_path)
                ):
                    existing.local_path = desired_path
                if item.get("honesty_label"):
                    existing.honesty_label = str(item["honesty_label"])
                if item.get("adapter"):
                    existing.adapter = str(item["adapter"])
                if item.get("fetch_mode"):
                    existing.fetch_mode = str(item["fetch_mode"])
            continue
        caps: dict[str, Any] = {"pipeline": {"stage": "configured"}}
        if item.get("document_url"):
            caps["document_url"] = item["document_url"]
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
                capabilities_json=caps,
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


def _live_rows(enabled: list[SourceConnection]) -> list[SourceConnection]:
    """Live JSON feeds and official document HTTP adapters (not curated mirrors)."""
    return [r for r in enabled if r.adapter in _INGEST_AUTO_ADAPTERS]


def _live_published(session: Session, live_keys: list[str]) -> bool:
    if not live_keys:
        return False
    source_ids = [f"src_{k}" for k in live_keys]
    count = session.scalar(
        select(func.count())
        .select_from(TariffRate)
        .where(
            TariffRate.status == "active",
            TariffRate.data_quality == "source_verified",
            TariffRate.source_document_id.in_(source_ids),
        )
    )
    return int(count or 0) > 0


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
    live_enabled = _live_rows(enabled)
    has_live_adapter = len(live_enabled) > 0

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
    elif settings.live_feed_enabled and configured:
        live_success = max(
            (_as_utc(r.last_success_at) for r in live_enabled if r.last_success_at is not None),
            default=None,
        )
        published = _live_published(session, [r.key for r in live_enabled])
        if live_success is None:
            live_reason = "Live feed enabled but no successful live-adapter fetch yet."
        elif not published:
            live_reason = (
                "Live fetch succeeded but approved rates from the live source are not published yet."
            )
        else:
            max_age = timedelta(hours=settings.live_feed_max_age_hours)
            age = _now() - live_success
            if age <= max_age:
                live = True
                kind = "live_monitored"
                label = "Live monitored"
                live_reason = "Live adapter freshness SLA met and live source rates are published."
            else:
                live_reason = (
                    f"Live feed enabled but last live success is stale "
                    f"({int(age.total_seconds() // 3600)}h ago)."
                )
    elif settings.live_feed_enabled:
        live_reason = "Live feed enabled but no source connections configured."

    return kind, label, live, live_reason


def feed_status(session: Session, settings: Settings | None = None) -> SourceFeedStatusOut:
    settings = settings or get_settings()
    ensure_default_connections(session, settings)
    rows = session.scalars(select(SourceConnection)).all()
    enabled = [r for r in rows if r.enabled]
    live_enabled = _live_rows(enabled)
    # Freshness for honesty uses live adapters only when present.
    last_success = max(
        (
            _as_utc(r.last_success_at)
            for r in (live_enabled or enabled)
            if r.last_success_at is not None
        ),
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
    has_live_adapter = len(live_enabled) > 0
    sched_on = bool(settings.source_fetch_scheduler_enabled)
    refresh_mode: Literal["manual_only", "scheduled"] = (
        "scheduled" if sched_on else "manual_only"
    )
    next_attempt = None
    fetch_overdue = False
    if sched_on and last_success is not None:
        next_attempt = last_success + timedelta(minutes=settings.source_fetch_interval_minutes)
        fetch_overdue = _now() > next_attempt
    elif sched_on and last_success is None and configured:
        fetch_overdue = True
    last_attempt = max(
        (
            _as_utc(r.last_checked_at)
            for r in enabled
            if r.last_checked_at is not None
        ),
        default=None,
    )
    last_err = next(
        (r.last_error for r in enabled if r.last_error),
        None,
    )
    published_usable = _approved_count(session) > 0 or int(
        session.scalar(
            select(func.count())
            .select_from(TariffRate)
            .where(TariffRate.status == "active")
        )
        or 0
    ) > 0

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
        last_attempt_at=last_attempt,
        scheduler_enabled=sched_on,
        refresh_mode=refresh_mode,
        scheduler_interval_minutes=settings.source_fetch_interval_minutes,
        has_live_adapter=has_live_adapter,
        next_attempt_at=next_attempt,
        fetch_overdue=fetch_overdue,
        published_rates_usable=published_usable,
        last_error=last_err,
    )


def connection_pipeline_status(
    session: Session, key: str, settings: Settings | None = None
) -> SourcePipelineStatusOut:
    row = get_connection(session, key)
    pipe = _pipeline(row)
    settings = settings or get_settings()
    next_attempt = None
    if settings.source_fetch_scheduler_enabled and row.last_success_at is not None:
        next_attempt = _as_utc(row.last_success_at) + timedelta(
            minutes=settings.source_fetch_interval_minutes
        )
    return SourcePipelineStatusOut(
        key=row.key,
        stage=str(pipe.get("stage") or "configured"),
        last_attempt_at=row.last_checked_at,
        last_success_at=row.last_success_at,
        last_error=row.last_error,
        last_checksum=row.last_checksum,
        last_archive_path=row.last_archive_path,
        final_url=pipe.get("final_url"),
        content_type=pipe.get("content_type"),
        http_status=pipe.get("http_status"),
        semantic_fingerprint=pipe.get("semantic_fingerprint"),
        ingest_batch_id=pipe.get("ingest_batch_id"),
        published_version_id=pipe.get("published_version_id"),
        published_at=_parse_dt(pipe.get("published_at")),
        next_attempt_at=next_attempt,
        parser_version=pipe.get("parser_version"),
        outcome=pipe.get("outcome"),
    )


def fetch_connection(
    session: Session,
    key: str,
    *,
    run_ingest: bool | None = None,
    settings: Settings | None = None,
) -> SourceFetchResult:
    from backend.app.services import ingestion_service

    settings = settings or get_settings()
    ensure_default_connections(session, settings)
    row = get_connection(session, key)
    now = _now()
    row.last_checked_at = now
    adapter_l = row.adapter.lower()
    is_live_adapter = adapter_l in _LIVE_ADAPTERS
    is_official_doc = adapter_l in _OFFICIAL_DOC_ADAPTERS
    is_auto_ingest = adapter_l in _INGEST_AUTO_ADAPTERS
    # Live / official document adapters auto-ingest pending proposals; curated stays opt-in.
    do_ingest = is_auto_ingest if run_ingest is None else run_ingest
    needs_allowlist = (
        is_auto_ingest
        or row.fetch_mode.lower() in {"http_get", "official_document"}
    )

    try:
        resolved = source_adapters.resolve_payload(
            adapter=row.adapter,
            fetch_mode=row.fetch_mode,
            local_path=row.local_path,
            source_url=row.source_url,
            allowlist=settings.http_source_allowlist if needs_allowlist else None,
            live_mode=is_auto_ingest,
        )

        # Optional pinned document when the portal URL is an HTML index.
        caps = dict(row.capabilities_json or {})
        pinned = caps.get("document_url")
        index_content = resolved.content
        index_ctype = resolved.content_type
        index_url = resolved.final_url or row.source_url
        if (
            is_official_doc
            and pinned
            and isinstance(pinned, str)
            and pinned.strip()
            and pinned.strip() != (row.source_url or "")
        ):
            discovery = official_doc_normalize.extract_discovery_links(
                index_content.decode("utf-8", errors="replace"),
                base_url=index_url or "",
            )
            manifest_dir = ROOT / "data" / "processed" / "source_archives"
            manifest_dir.mkdir(parents=True, exist_ok=True)
            official_doc_normalize.write_discovery_manifest(
                manifest_dir / f"{row.key}_discovery.json",
                discovery,
                base_url=index_url or "",
            )
            resolved = source_adapters.resolve_payload(
                adapter=row.adapter,
                fetch_mode=row.fetch_mode,
                local_path=None,
                source_url=pinned.strip(),
                allowlist=settings.http_source_allowlist,
                live_mode=True,
            )

        checksum = hashlib.sha256(resolved.content).hexdigest()
        archive_dir = ROOT / "data" / "processed" / "source_archives"
        archive_dir.mkdir(parents=True, exist_ok=True)
        safe_name = f"{row.key}_{checksum[:12]}.bin"
        archive_path = archive_dir / safe_name
        if not archive_path.exists():
            archive_path.write_bytes(resolved.content)
        rel_archive = str(archive_path.relative_to(ROOT)).replace("\\", "/")

        source_id = f"src_fetch_{row.key}"
        existing = session.get(SourceDocument, source_id)
        if is_official_doc:
            honesty = (
                "Official portal document archived locally (HTML/PDF). "
                "Approve an ingest batch before treating rates as verified."
            )
            source_kind = "official_document"
        elif is_live_adapter:
            honesty = (
                "Live HTTP fetch archived locally. Approve an ingest batch before "
                "treating rates as verified."
            )
            source_kind = "live_feed"
        else:
            honesty = (
                "Curated / local archive fetch only — not a live government API. "
                "Approve an ingest batch before treating rates as verified."
            )
            source_kind = "curated_dataset"
        if existing is None:
            session.add(
                SourceDocument(
                    id=source_id,
                    title=row.title,
                    publisher=row.publisher,
                    url=resolved.final_url or row.source_url,
                    retrieved_at=now,
                    effective_from=None,
                    file_path=rel_archive,
                    archive_path=rel_archive,
                    checksum=checksum,
                    status="fetched",
                    notes=honesty,
                    source_kind=source_kind,
                    live_claim=is_auto_ingest,
                    fetched_at=now,
                    content_type=resolved.content_type,
                )
            )
        else:
            existing.checksum = checksum
            existing.file_path = rel_archive
            existing.archive_path = rel_archive
            existing.fetched_at = now
            existing.status = "fetched"
            existing.live_claim = is_auto_ingest
            existing.notes = honesty
            existing.source_kind = source_kind
            existing.content_type = resolved.content_type
            existing.url = resolved.final_url or row.source_url

        row.last_success_at = now
        row.last_error = None
        row.last_checksum = checksum
        row.last_archive_path = rel_archive
        row.last_source_document_id = source_id
        _set_pipeline(
            row,
            {
                "stage": "fetch_success",
                "final_url": resolved.final_url or row.source_url,
                "content_type": resolved.content_type,
                "http_status": resolved.http_status,
                "outcome": "fetched",
                "artifact_checksum": checksum,
                "index_content_type": index_ctype,
                "index_url": index_url,
            },
        )
        session.flush()

        ingest_batch_id = None
        message = (
            "Fetched source into local archive. Review and "
            "approve ingest proposals before treating rates as verified."
        )

        if do_ingest and row.adapter.lower() not in {"local_pdf_archive"}:
            ingest_path = rel_archive
            if is_auto_ingest:
                try:
                    if is_official_doc:
                        normalized = official_doc_normalize.normalize_official_document(
                            resolved.content,
                            source_key=row.key,
                            content_type=resolved.content_type,
                            source_url=resolved.final_url or row.source_url,
                            publisher=row.publisher,
                        )
                        if normalized.discovery:
                            official_doc_normalize.write_discovery_manifest(
                                archive_dir / f"{row.key}_{checksum[:12]}_discovery.json",
                                normalized.discovery,
                                base_url=resolved.final_url or row.source_url or "",
                            )
                    else:
                        normalized = live_feed_normalize.normalize_live_json(
                            resolved.content,
                            source_key=row.key,
                            content_type=resolved.content_type,
                        )
                except ValueError as exc:
                    _set_pipeline(
                        row,
                        {
                            "stage": "error",
                            "outcome": "parse_failed",
                            "parse_error": str(exc)[:500],
                        },
                    )
                    row.last_error = f"parse_failed:{exc}"[:2000]
                    session.flush()
                    raise AppError(
                        code="SOURCE_LIVE_PARSE_FAILED",
                        message=f"Official/live document parse failed: {exc}",
                        status_code=422,
                    ) from exc

                json_name = f"{row.key}_{checksum[:12]}.json"
                json_path = archive_dir / json_name
                live_feed_normalize.write_normalized_archive(json_path, normalized.envelope)
                ingest_path = str(json_path.relative_to(ROOT)).replace("\\", "/")

                published_fp = _pipeline(row).get("last_published_fingerprint")
                last_pub = session.scalars(
                    select(DataVersion)
                    .where(DataVersion.label == f"ingest:{row.key}")
                    .order_by(DataVersion.published_at.desc())
                ).first()
                if last_pub and isinstance(last_pub.record_counts, dict):
                    published_fp = (
                        last_pub.record_counts.get("semantic_fingerprint") or published_fp
                    )

                evidence = {
                    "final_url": resolved.final_url or row.source_url,
                    "retrieved_at": now.isoformat(),
                    "checksum": checksum,
                    "archive_path": rel_archive,
                    "content_type": resolved.content_type,
                    "parser_version": normalized.parser_version,
                }
                if isinstance(normalized, official_doc_normalize.OfficialNormalizeResult):
                    evidence["excerpt"] = normalized.evidence_excerpt
                    evidence["notice_id"] = (normalized.envelope.get("notice_id"))

                _set_pipeline(
                    row,
                    {
                        "stage": "parsed",
                        "semantic_fingerprint": normalized.semantic_fingerprint,
                        "parser_version": normalized.parser_version,
                        "document_type": normalized.document_type,
                        "warnings": normalized.warnings,
                        "evidence": evidence,
                    },
                )

                # Reuse pending batch with same semantic fingerprint (idempotent).
                pending_same = session.scalars(
                    select(IngestionBatch)
                    .where(
                        IngestionBatch.source_key == row.key,
                        IngestionBatch.status == "pending_review",
                    )
                    .order_by(IngestionBatch.created_at.desc())
                ).first()
                if (
                    pending_same
                    and isinstance(pending_same.validation_summary, dict)
                    and pending_same.validation_summary.get("semantic_fingerprint")
                    == normalized.semantic_fingerprint
                ):
                    _set_pipeline(
                        row,
                        {
                            "stage": "pending_review",
                            "outcome": "unchanged",
                            "ingest_batch_id": pending_same.id,
                        },
                    )
                    session.flush()
                    return SourceFetchResult(
                        connection=_connection_out(row),
                        checksum=checksum,
                        archive_path=rel_archive,
                        source_document_id=source_id,
                        resolved_from=resolved.resolved_from,
                        ingest_batch_id=pending_same.id,
                        message="Fetch succeeded; pending batch already covers these rates.",
                        outcome="unchanged",
                        semantic_fingerprint=normalized.semantic_fingerprint,
                    )

                if published_fp and published_fp == normalized.semantic_fingerprint:
                    _set_pipeline(
                        row,
                        {
                            "stage": "unchanged",
                            "outcome": "unchanged",
                            "semantic_fingerprint": normalized.semantic_fingerprint,
                        },
                    )
                    session.flush()
                    return SourceFetchResult(
                        connection=_connection_out(row),
                        checksum=checksum,
                        archive_path=rel_archive,
                        source_document_id=source_id,
                        resolved_from=resolved.resolved_from,
                        ingest_batch_id=None,
                        message="Fetch succeeded; normalized rates unchanged — no new proposals.",
                        outcome="unchanged",
                        semantic_fingerprint=normalized.semantic_fingerprint,
                    )

                # Unsupported document with zero rates: archive only, do not invent rates.
                if not (normalized.envelope.get("rates") or []):
                    _set_pipeline(
                        row,
                        {
                            "stage": "quarantined",
                            "outcome": "unsupported_document",
                            "semantic_fingerprint": normalized.semantic_fingerprint,
                            "warnings": normalized.warnings,
                        },
                    )
                    session.flush()
                    return SourceFetchResult(
                        connection=_connection_out(row),
                        checksum=checksum,
                        archive_path=rel_archive,
                        source_document_id=source_id,
                        resolved_from=resolved.resolved_from,
                        ingest_batch_id=None,
                        message=(
                            "Document archived as evidence; no extractable rates — "
                            "nothing to propose for review."
                        ),
                        outcome="unsupported_document",
                        semantic_fingerprint=normalized.semantic_fingerprint,
                    )

                from backend.app.domain.trade import IngestRunRequest

                batch = ingestion_service.run_ingest(
                    session,
                    IngestRunRequest(
                        source_key=row.key,
                        archive_path=ingest_path,
                        force=False,
                    ),
                )
                ingest_batch_id = batch.id
                stage = "validated" if batch.validation_summary.get("publishable") else "quarantined"
                if batch.status == "pending_review":
                    stage = "pending_review" if batch.validation_summary.get("ok", 0) else "quarantined"
                if batch.status == "approved":
                    stage = "published"
                _set_pipeline(
                    row,
                    {
                        "stage": stage,
                        "ingest_batch_id": batch.id,
                        "semantic_fingerprint": normalized.semantic_fingerprint,
                        "parser_version": normalized.parser_version,
                        "outcome": stage,
                        "validation_summary": batch.validation_summary,
                        "evidence": evidence,
                    },
                )
                message = (
                    f"Official/live fetch archived and ingested batch {batch.id} "
                    f"(status={batch.status}). Human approval required to publish."
                )
            else:
                from backend.app.domain.trade import IngestRunRequest

                # Prefer freshly archived bytes so stale DB local_path cannot break ingest.
                ingest_path = rel_archive
                batch = ingestion_service.run_ingest(
                    session,
                    IngestRunRequest(
                        source_key=row.key,
                        archive_path=ingest_path,
                        force=False,
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
            message=message,
            outcome=_pipeline(row).get("outcome"),
            semantic_fingerprint=_pipeline(row).get("semantic_fingerprint"),
        )
    except Exception as exc:
        row.last_error = str(exc)[:2000]
        _set_pipeline(
            row,
            {
                "stage": "error",
                "outcome": "error",
                "error": str(exc)[:500],
            },
        )
        # Persist failure metadata even though the request session will rollback
        # the raised exception path (get_session rolls back on error).
        session.commit()
        raise


def fetch_all_enabled(
    session: Session,
    *,
    run_ingest: bool | None = None,
    settings: Settings | None = None,
) -> list[SourceFetchResult]:
    settings = settings or get_settings()
    ensure_default_connections(session, settings)
    rows = session.scalars(
        select(SourceConnection).where(SourceConnection.enabled.is_(True))
    ).all()
    results: list[SourceFetchResult] = []
    for row in rows:
        results.append(
            fetch_connection(session, row.key, run_ingest=run_ingest, settings=settings)
        )
    return results


def record_publication(session: Session, source_key: str, version_id: str, fingerprint: str | None) -> None:
    """Called after approve_batch to update live pipeline publication markers."""
    row = session.scalar(select(SourceConnection).where(SourceConnection.key == source_key))
    if row is None:
        return
    updates: dict[str, Any] = {
        "stage": "published",
        "published_version_id": version_id,
        "published_at": _now().isoformat(),
        "outcome": "published",
    }
    if fingerprint:
        updates["last_published_fingerprint"] = fingerprint
    _set_pipeline(row, updates)
