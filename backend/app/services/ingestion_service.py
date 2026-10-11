"""Regulatory archive ingestion: extract → validate → approve → publish."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from backend.app.core.errors import AppError
from backend.app.data.models import (
    DataVersion,
    HsCode,
    IngestionBatch,
    IngestionProposal,
    RegulatoryChunk,
    SourceDocument,
    TariffRate,
)
from backend.app.domain.trade import (
    DataVersionOut,
    IngestBatchDiffOut,
    IngestionBatchDetail,
    IngestionBatchOut,
    IngestionProposalOut,
    IngestRunRequest,
)
from backend.app.services import live_feed_normalize

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ARCHIVE = (
    ROOT / "config" / "trade" / "fixtures" / "cbic" / "cbic_notification_2026_q3.json"
)
ALLOWED_ORIGIN = "BD"
ALLOWED_DESTINATION = "IN"
# Chapter lock removed for full HS catalog; rates still BD→IN only.
ALLOWED_CHAPTER: str | None = None


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _resolve_archive(source_key: str | None, archive_path: str | None) -> Path:
    if archive_path:
        path = Path(archive_path)
        if not path.is_absolute():
            path = ROOT / path
    elif source_key:
        path = ROOT / "config" / "trade" / "fixtures" / "cbic" / f"{source_key}.json"
        if not path.exists():
            # Legacy fallback only — prefer fixtures path above.
            legacy = ROOT / "config" / "trade" / "sources" / f"{source_key}.json"
            if legacy.exists():
                path = legacy
    else:
        path = DEFAULT_ARCHIVE
    if not path.exists():
        raise AppError(
            code="INGEST_ARCHIVE_NOT_FOUND",
            message=f"Archive not found: {path}",
            status_code=404,
        )
    return path


def _proposal_out(row: IngestionProposal) -> IngestionProposalOut:
    return IngestionProposalOut(
        id=row.id,
        kind=row.kind,
        payload=dict(row.payload_json or {}),
        validation_status=row.validation_status,
        validation_errors=list(row.validation_errors or []),
        publish_status=row.publish_status,
    )


def _batch_out(row: IngestionBatch) -> IngestionBatchOut:
    return IngestionBatchOut(
        id=row.id,
        source_key=row.source_key,
        archive_path=row.archive_path,
        checksum=row.checksum,
        title=row.title,
        publisher=row.publisher,
        status=row.status,
        effective_from=row.effective_from,
        validation_summary=dict(row.validation_summary or {}),
        created_at=row.created_at,
        reviewed_at=row.reviewed_at,
        review_notes=row.review_notes,
        published_source_id=row.published_source_id,
        data_version_id=row.data_version_id,
    )


def _batch_detail(row: IngestionBatch) -> IngestionBatchDetail:
    return IngestionBatchDetail(
        **_batch_out(row).model_dump(),
        proposals=[_proposal_out(p) for p in row.proposals],
    )


def _validate_rate(session: Session, item: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    hs = str(item.get("hs_code") or "").strip()
    origin = str(item.get("origin") or "").upper()
    destination = str(item.get("destination") or "").upper()
    rate = item.get("rate")

    if not hs:
        errors.append("missing_hs_code")
    else:
        hs_row = session.get(HsCode, hs)
        if hs_row is None:
            errors.append("unknown_hs_code")
        elif ALLOWED_CHAPTER is not None and hs_row.chapter != ALLOWED_CHAPTER:
            errors.append(f"hs_outside_chapter_{ALLOWED_CHAPTER}")
    if origin != ALLOWED_ORIGIN:
        errors.append("origin_not_bd")
    if destination != ALLOWED_DESTINATION:
        errors.append("destination_not_in")
    try:
        rate_dec = Decimal(str(rate))
        if rate_dec < 0 or rate_dec > 100:
            errors.append("rate_out_of_range")
    except Exception:
        errors.append("invalid_rate")
    if not isinstance(item.get("duty_components"), dict):
        errors.append("missing_duty_components")
    return errors


def _validate_chunk(session: Session, item: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    text = str(item.get("text") or "").strip()
    if len(text) < 20:
        errors.append("chunk_text_too_short")
    hs = item.get("hs_code")
    if hs:
        hs_row = session.get(HsCode, str(hs))
        if hs_row is None:
            errors.append("unknown_hs_code")
        elif ALLOWED_CHAPTER is not None and hs_row.chapter != ALLOWED_CHAPTER:
            errors.append(f"hs_outside_chapter_{ALLOWED_CHAPTER}")
    return errors


def run_ingest(
    session: Session,
    payload: IngestRunRequest | None = None,
) -> IngestionBatchDetail:
    req = payload or IngestRunRequest()
    path = _resolve_archive(req.source_key, req.archive_path)
    checksum = _sha256(path)

    if not req.force:
        existing = session.scalars(
            select(IngestionBatch)
            .options(joinedload(IngestionBatch.proposals))
            .where(
                IngestionBatch.checksum == checksum,
                IngestionBatch.status.in_(("pending_review", "approved")),
            )
            .order_by(IngestionBatch.created_at.desc())
        ).unique().first()
        if existing is not None:
            return _batch_detail(existing)

    raw = json.loads(path.read_text(encoding="utf-8"))
    source_key = str(raw.get("source_key") or path.stem)
    effective_raw = raw.get("effective_from")
    effective_from = date.fromisoformat(str(effective_raw)) if effective_raw else None

    batch = IngestionBatch(
        id=str(uuid4()),
        source_key=source_key,
        archive_path=str(path.relative_to(ROOT)).replace("\\", "/"),
        checksum=checksum,
        title=str(raw.get("title") or source_key),
        publisher=str(raw.get("publisher") or "unknown"),
        status="pending_review",
        effective_from=effective_from,
        validation_summary={},
        created_at=_utcnow(),
    )
    session.add(batch)

    ok_count = 0
    err_count = 0
    for rate in raw.get("rates") or []:
        errors = _validate_rate(session, rate)
        status = "ok" if not errors else "error"
        ok_count += status == "ok"
        err_count += status == "error"
        session.add(
            IngestionProposal(
                id=str(uuid4()),
                batch_id=batch.id,
                kind="tariff_rate",
                payload_json=dict(rate),
                validation_status=status,
                validation_errors=errors,
                publish_status="pending",
            )
        )
    for chunk in raw.get("chunks") or []:
        errors = _validate_chunk(session, chunk)
        status = "ok" if not errors else "error"
        ok_count += status == "ok"
        err_count += status == "error"
        session.add(
            IngestionProposal(
                id=str(uuid4()),
                batch_id=batch.id,
                kind="regulatory_chunk",
                payload_json=dict(chunk),
                validation_status=status,
                validation_errors=errors,
                publish_status="pending",
            )
        )

    fingerprint = None
    try:
        fingerprint = live_feed_normalize.semantic_fingerprint(raw)
    except Exception:
        fingerprint = None
    live_meta = raw.get("_live_meta") if isinstance(raw.get("_live_meta"), dict) else {}
    batch.validation_summary = {
        "ok": ok_count,
        "error": err_count,
        "publishable": ok_count > 0,
        "corridor_lock": f"{ALLOWED_ORIGIN}->{ALLOWED_DESTINATION}",
        "chapter_lock": ALLOWED_CHAPTER or "all",
        "notice_id": raw.get("notice_id"),
        "semantic_fingerprint": fingerprint,
        "parser_version": live_meta.get("parser_version"),
        "document_type": live_meta.get("document_type") or raw.get("document_type"),
        "warnings": list(live_meta.get("warnings") or []),
    }
    session.flush()
    session.refresh(batch)
    batch = session.scalars(
        select(IngestionBatch)
        .options(joinedload(IngestionBatch.proposals))
        .where(IngestionBatch.id == batch.id)
    ).unique().one()
    return _batch_detail(batch)


def list_batches(session: Session) -> list[IngestionBatchOut]:
    rows = session.scalars(
        select(IngestionBatch).order_by(IngestionBatch.created_at.desc())
    ).all()
    return [_batch_out(r) for r in rows]


def get_batch(session: Session, batch_id: str) -> IngestionBatchDetail:
    row = session.scalars(
        select(IngestionBatch)
        .options(joinedload(IngestionBatch.proposals))
        .where(IngestionBatch.id == batch_id)
    ).unique().first()
    if row is None:
        raise AppError(code="INGEST_BATCH_NOT_FOUND", message="Batch not found", status_code=404)
    return _batch_detail(row)


def reject_batch(session: Session, batch_id: str, notes: str | None = None) -> IngestionBatchDetail:
    row = session.get(IngestionBatch, batch_id)
    if row is None:
        raise AppError(code="INGEST_BATCH_NOT_FOUND", message="Batch not found", status_code=404)
    if row.status != "pending_review":
        raise AppError(
            code="INGEST_INVALID_STATE",
            message=f"Cannot reject batch in status={row.status}",
            status_code=409,
        )
    row.status = "rejected"
    row.reviewed_at = _utcnow()
    row.review_notes = notes or "Rejected by reviewer"
    for proposal in session.scalars(
        select(IngestionProposal).where(IngestionProposal.batch_id == batch_id)
    ).all():
        proposal.publish_status = "skipped"
    session.flush()
    return get_batch(session, batch_id)


def approve_batch(
    session: Session,
    batch_id: str,
    notes: str | None = None,
) -> IngestionBatchDetail:
    row = session.scalars(
        select(IngestionBatch)
        .options(joinedload(IngestionBatch.proposals))
        .where(IngestionBatch.id == batch_id)
    ).unique().first()
    if row is None:
        raise AppError(code="INGEST_BATCH_NOT_FOUND", message="Batch not found", status_code=404)
    if row.status != "pending_review":
        raise AppError(
            code="INGEST_INVALID_STATE",
            message=f"Cannot approve batch in status={row.status}",
            status_code=409,
        )

    publishable = [p for p in row.proposals if p.validation_status == "ok"]
    if not publishable:
        raise AppError(
            code="INGEST_NOTHING_TO_PUBLISH",
            message="No validated proposals to publish",
            status_code=400,
        )

    source_id = f"src_{row.source_key}"
    existing_source = session.get(SourceDocument, source_id)
    if existing_source is None:
        now = _utcnow()
        session.add(
            SourceDocument(
                id=source_id,
                title=row.title,
                publisher=row.publisher,
                url=None,
                retrieved_at=now,
                effective_from=row.effective_from,
                file_path=row.archive_path,
                archive_path=row.archive_path,
                checksum=row.checksum,
                status="published",
                notes=f"Published via ingestion batch {row.id}; checksum {row.checksum[:12]}",
                source_kind="manual_archive",
                live_claim=False,
                fetched_at=now,
                reviewed_at=now,
                published_at=now,
            )
        )
    else:
        now = _utcnow()
        existing_source.checksum = row.checksum
        existing_source.file_path = row.archive_path
        existing_source.archive_path = row.archive_path
        existing_source.notes = f"Re-published via batch {row.id}"
        existing_source.status = "published"
        existing_source.live_claim = False
        existing_source.published_at = now
        existing_source.reviewed_at = now

    rates_published = 0
    chunks_published = 0
    effective_from = row.effective_from or date.today()
    published_rate_ids: list[str] = []

    for proposal in row.proposals:
        if proposal.validation_status != "ok":
            proposal.publish_status = "skipped"
            continue
        payload = dict(proposal.payload_json or {})
        if proposal.kind == "tariff_rate":
            from backend.app.services import component_provenance as comp_prov

            hs_code = str(payload["hs_code"])
            origin = str(payload["origin"]).upper()
            destination = str(payload["destination"]).upper()
            proposed_rate = Decimal(str(payload["rate"]))
            proposed_components = dict(payload.get("duty_components") or {})
            # Stamp IGST provenance source doc when missing
            prov = proposed_components.get("_provenance")
            if isinstance(prov, dict) and "igst_pct" in prov and isinstance(prov["igst_pct"], dict):
                if not prov["igst_pct"].get("source_document_id"):
                    prov["igst_pct"]["source_document_id"] = source_id
            active_rows = session.scalars(
                select(TariffRate).where(
                    TariffRate.hs_code == hs_code,
                    TariffRate.origin == origin,
                    TariffRate.destination == destination,
                    TariffRate.status == "active",
                    TariffRate.regime == "mfn",
                )
            ).all()
            existing_components = (
                dict(active_rows[0].duty_components or {}) if active_rows else {}
            )
            merged_components = comp_prov.merge_duty_components(
                existing_components,
                proposed_components,
                incoming_source_document_id=source_id,
            )
            partial = comp_prov.partial_keys(proposed_components)
            # Keep primary BCD rate when ingest is IGST-only partial update.
            if partial == {"igst_pct"} and active_rows:
                published_rate = Decimal(str(active_rows[0].rate))
            else:
                published_rate = comp_prov.primary_bcd_rate(
                    merged_components, fallback=float(proposed_rate)
                )
            data_quality = "source_verified"
            if partial and existing_components:
                # Mixed stack: verified IGST + curated BCD
                data_quality = "source_verified"
            if (
                len(active_rows) == 1
                and active_rows[0].rate == published_rate
                and comp_prov.applicable_stack_signature(active_rows[0].duty_components)
                == comp_prov.applicable_stack_signature(merged_components)
            ):
                proposal.publish_status = "skipped"
                continue
            max_version = session.scalar(
                select(func.max(TariffRate.version)).where(
                    TariffRate.hs_code == hs_code,
                    TariffRate.origin == origin,
                    TariffRate.destination == destination,
                )
            ) or 0
            new_id = str(uuid4())
            for old in active_rows:
                old.status = "superseded"
                old.superseded_by = new_id
                if old.effective_to is None:
                    old.effective_to = effective_from - timedelta(days=1)
            session.add(
                TariffRate(
                    id=new_id,
                    hs_code=hs_code,
                    origin=origin,
                    destination=destination,
                    rate=published_rate,
                    rate_type=str(payload.get("rate_type") or "ad_valorem_pct"),
                    duty_components=merged_components,
                    agreement_id=None,
                    effective_from=effective_from,
                    effective_to=None,
                    source_document_id=source_id,
                    version=int(max_version) + 1,
                    status="active",
                    data_quality=data_quality,
                    superseded_by=None,
                    regime="mfn",
                    rule_label=f"{hs_code} MFN BD→IN",
                )
            )
            proposal.publish_status = "published"
            rates_published += 1
            published_rate_ids.append(new_id)
        elif proposal.kind == "regulatory_chunk":
            chunk_id = str(payload.get("id") or f"chunk_{uuid4().hex[:12]}")
            existing_chunk = session.get(RegulatoryChunk, chunk_id)
            if existing_chunk is None:
                session.add(
                    RegulatoryChunk(
                        id=chunk_id,
                        source_document_id=source_id,
                        text=str(payload["text"]),
                        hs_code=payload.get("hs_code"),
                        tags=list(payload.get("tags") or []),
                    )
                )
            else:
                existing_chunk.text = str(payload["text"])
                existing_chunk.source_document_id = source_id
                existing_chunk.hs_code = payload.get("hs_code")
                existing_chunk.tags = list(payload.get("tags") or [])
            proposal.publish_status = "published"
            chunks_published += 1
        else:
            proposal.publish_status = "skipped"

    semantic_fp = None
    if isinstance(row.validation_summary, dict):
        semantic_fp = row.validation_summary.get("semantic_fingerprint")
    version = DataVersion(
        id=str(uuid4()),
        label=f"ingest:{row.source_key}",
        fingerprint=f"ingest.{row.source_key}.{row.checksum[:16]}",
        notes=notes or f"Approved batch {row.id}",
        published_at=_utcnow(),
        batch_id=row.id,
        record_counts={
            "tariff_rates": rates_published,
            "regulatory_chunks": chunks_published,
            "semantic_fingerprint": semantic_fp,
        },
    )
    session.add(version)
    row.status = "approved"
    row.reviewed_at = _utcnow()
    row.review_notes = notes or "Approved by reviewer"
    row.published_source_id = source_id
    row.data_version_id = version.id
    session.flush()

    from backend.app.services import source_connection_service

    source_connection_service.record_publication(
        session, row.source_key, version.id, semantic_fp if isinstance(semantic_fp, str) else None
    )

    # Publication is durable even if impact processing fails — retryable separately.
    impact_error = None
    try:
        from backend.app.services import impact_service

        impact_service.record_impacts_after_approve(session, published_rate_ids)
    except Exception as exc:  # noqa: BLE001 — must not roll back publication
        impact_error = str(exc)[:500]
        summary = dict(row.validation_summary or {})
        summary["impact_error"] = impact_error
        summary["impact_pending_retry"] = True
        row.validation_summary = summary
    session.flush()
    return get_batch(session, batch_id)


def batch_diff(session: Session, batch_id: str) -> IngestBatchDiffOut:
    """Compare pending tariff proposals against currently active published rates."""
    row = session.scalars(
        select(IngestionBatch)
        .options(joinedload(IngestionBatch.proposals))
        .where(IngestionBatch.id == batch_id)
    ).unique().first()
    if row is None:
        raise AppError(code="INGEST_BATCH_NOT_FOUND", message="Batch not found", status_code=404)

    changes: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    affected: list[str] = []

    for proposal in row.proposals:
        payload = dict(proposal.payload_json or {})
        if proposal.kind != "tariff_rate":
            continue
        hs = str(payload.get("hs_code") or "")
        if proposal.validation_status != "ok":
            quarantined.append(
                {
                    "proposal_id": proposal.id,
                    "hs_code": hs,
                    "errors": list(proposal.validation_errors or []),
                    "payload": payload,
                }
            )
            continue
        origin = str(payload.get("origin") or "").upper()
        destination = str(payload.get("destination") or "").upper()
        active = session.scalars(
            select(TariffRate).where(
                TariffRate.hs_code == hs,
                TariffRate.origin == origin,
                TariffRate.destination == destination,
                TariffRate.status == "active",
            )
        ).first()
        proposed_rate = payload.get("rate")
        proposed_components = dict(payload.get("duty_components") or {})
        change_type = "added"
        previous = None
        if active is not None:
            previous = {
                "rate": float(active.rate),
                "rate_type": active.rate_type,
                "duty_components": dict(active.duty_components or {}),
                "effective_from": active.effective_from.isoformat()
                if active.effective_from
                else None,
                "tariff_rate_id": active.id,
            }
            same_rate = Decimal(str(active.rate)) == Decimal(str(proposed_rate))
            same_comp = dict(active.duty_components or {}) == proposed_components
            change_type = "unchanged" if same_rate and same_comp else "changed"
        if change_type != "unchanged":
            affected.append(hs)
        changes.append(
            {
                "proposal_id": proposal.id,
                "hs_code": hs,
                "origin": origin,
                "destination": destination,
                "change_type": change_type,
                "previous": previous,
                "proposed": {
                    "rate": proposed_rate,
                    "rate_type": payload.get("rate_type"),
                    "duty_components": proposed_components,
                    "notes": payload.get("notes"),
                },
                "effective_from": row.effective_from.isoformat() if row.effective_from else None,
                "source_title": row.title,
                "checksum": row.checksum,
                "archive_path": row.archive_path,
            }
        )

    return IngestBatchDiffOut(
        batch_id=row.id,
        source_key=row.source_key,
        effective_from=row.effective_from,
        checksum=row.checksum,
        archive_path=row.archive_path,
        changes=changes,
        quarantined=quarantined,
        affected_hs_codes=sorted(set(affected)),
    )


def list_data_versions(session: Session) -> list[DataVersionOut]:
    rows = session.scalars(select(DataVersion).order_by(DataVersion.published_at.desc())).all()
    return [
        DataVersionOut(
            id=r.id,
            label=r.label,
            fingerprint=r.fingerprint,
            notes=r.notes,
            published_at=r.published_at,
            batch_id=r.batch_id,
            record_counts=dict(r.record_counts or {}),
        )
        for r in rows
    ]
