"""Country-agnostic ingestion pipeline facade (IF-2)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.data.models import IngestionBatch, IngestionProposal
from backend.app.domain.trade import IngestionBatchDetail, IngestRunRequest
from backend.app.ingestion import (
    discovery,
    downloading,
    impact_analysis,
    parsing,
)
from backend.app.ingestion.normalization import (
    normalize_tariff_record,
    normalized_rule_to_proposal_payload,
)
from backend.app.integrations.core.errors import IntegrationError, ProviderNotFoundError
from backend.app.integrations.core.registry import get_registry
from backend.app.services import ingestion_service

ROOT = Path(__file__).resolve().parents[3]


@dataclass
class PipelineResult:
    source_code: str
    checksum: str
    archive_path: str | None
    batch: IngestionBatchDetail | None
    records_found: int
    records_ok: int
    records_error: int
    warnings: list[str] = field(default_factory=list)
    impact: dict[str, Any] = field(default_factory=dict)
    source_result_meta: dict[str, Any] = field(default_factory=dict)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _validate_normalized_rate(session: Session, payload: dict[str, Any]) -> list[str]:
    """Reuse legacy corridor/chapter checks on normalized payloads."""
    return ingestion_service._validate_rate(session, payload)


def _validate_chunk(session: Session, item: dict[str, Any]) -> list[str]:
    return ingestion_service._validate_chunk(session, item)


class IngestionPipeline:
    """
    discover → fetch → archive → parse → normalize → validate → review batch.

    No country if/elif branches — providers + config own source differences.
    """

    def run(
        self,
        session: Session,
        source_code: str,
        *,
        force: bool = False,
        query: dict[str, Any] | None = None,
    ) -> PipelineResult:
        try:
            provider = get_registry().get(source_code)
        except ProviderNotFoundError as exc:
            # Fall back to legacy JSON ingest path for unknown codes
            batch = ingestion_service.run_ingest(
                session,
                IngestRunRequest(source_key=source_code.lower(), force=force),
            )
            return PipelineResult(
                source_code=source_code,
                checksum=batch.checksum,
                archive_path=batch.archive_path,
                batch=batch,
                records_found=sum(batch.validation_summary.get(k, 0) for k in ("ok", "error")),
                records_ok=int(batch.validation_summary.get("ok") or 0),
                records_error=int(batch.validation_summary.get("error") or 0),
                warnings=[f"legacy_ingest_fallback:{exc.code}"],
            )

        items = discovery.discover(source_code, query)
        if not items:
            raise AppError(
                code="INGEST_NOTHING_DISCOVERED",
                message=f"No discoverable items for {source_code}",
                status_code=404,
            )

        try:
            source_result = downloading.download(source_code, items[0])
        except IntegrationError as exc:
            raise AppError(code=exc.code, message=exc.message, status_code=502) from exc

        raw_bytes = provider.fetch(items[0])
        checksum = source_result.checksum or hashlib.sha256(raw_bytes).hexdigest()

        if not force:
            from sqlalchemy import select
            from sqlalchemy.orm import joinedload

            existing = (
                session.scalars(
                    select(IngestionBatch)
                    .options(joinedload(IngestionBatch.proposals))
                    .where(
                        IngestionBatch.checksum == checksum,
                        IngestionBatch.status.in_(("pending_review", "approved")),
                    )
                    .order_by(IngestionBatch.created_at.desc())
                )
                .unique()
                .first()
            )
            if existing is not None:
                detail = ingestion_service._batch_detail(existing)
                return PipelineResult(
                    source_code=source_code,
                    checksum=existing.checksum,
                    archive_path=existing.archive_path,
                    batch=detail,
                    records_found=int(existing.validation_summary.get("ok") or 0)
                    + int(existing.validation_summary.get("error") or 0),
                    records_ok=int(existing.validation_summary.get("ok") or 0),
                    records_error=int(existing.validation_summary.get("error") or 0),
                    warnings=["deduped_existing_batch"],
                    source_result_meta=dict(source_result.raw_metadata),
                )

        # Archive bytes under data/archives/<source_code>/
        archive_dir = Path(ROOT) / "data" / "archives" / source_code.lower()
        archive_dir.mkdir(parents=True, exist_ok=True)
        stamp = _utcnow().strftime("%Y%m%dT%H%M%SZ")
        archive_file = archive_dir / f"{stamp}_{checksum[:12]}.json"
        archive_file.write_bytes(raw_bytes)
        rel_archive = str(archive_file.relative_to(ROOT)).replace("\\", "/")

        records = parsing.parse(source_result)
        meta = source_result.raw_metadata or {}
        effective_from = None
        if meta.get("effective_from"):
            try:
                effective_from = date.fromisoformat(str(meta["effective_from"])[:10])
            except ValueError:
                effective_from = None

        batch = IngestionBatch(
            id=str(uuid4()),
            source_key=source_code.lower(),
            archive_path=rel_archive,
            checksum=checksum,
            title=str(meta.get("title") or provider.definition.code),
            publisher=str(meta.get("publisher") or provider.definition.provider),
            status="pending_review",
            effective_from=effective_from,
            validation_summary={},
            created_at=_utcnow(),
        )
        session.add(batch)

        ok_count = 0
        err_count = 0
        chunk_ok = 0
        for record in records:
            kind = str(record.get("_kind") or "tariff_rate")
            if kind == "regulatory_chunk":
                payload = {k: v for k, v in record.items() if k != "_kind"}
                errors = _validate_chunk(session, payload)
                status = "ok" if not errors else "error"
                ok_count += status == "ok"
                err_count += status == "error"
                chunk_ok += status == "ok"
                session.add(
                    IngestionProposal(
                        id=str(uuid4()),
                        batch_id=batch.id,
                        kind="regulatory_chunk",
                        payload_json=payload,
                        validation_status=status,
                        validation_errors=errors,
                        publish_status="pending",
                    )
                )
                continue

            rule, norm_errors = normalize_tariff_record(
                {k: v for k, v in record.items() if k != "_kind"},
                source_document_id=source_result.document_id,
                default_effective_from=effective_from,
            )
            if rule is None:
                ok_count += 0
                err_count += 1
                session.add(
                    IngestionProposal(
                        id=str(uuid4()),
                        batch_id=batch.id,
                        kind="tariff_rate",
                        payload_json={k: v for k, v in record.items() if k != "_kind"},
                        validation_status="error",
                        validation_errors=norm_errors,
                        publish_status="pending",
                    )
                )
                continue

            payload = normalized_rule_to_proposal_payload(rule)
            # Preserve original duty_components when present
            raw_components = record.get("duty_components")
            if isinstance(raw_components, dict) and raw_components:
                payload["duty_components"] = dict(raw_components)
            errors = list(norm_errors) + _validate_normalized_rate(session, payload)
            status = "ok" if not errors else "error"
            ok_count += status == "ok"
            err_count += status == "error"
            session.add(
                IngestionProposal(
                    id=str(uuid4()),
                    batch_id=batch.id,
                    kind="tariff_rate",
                    payload_json=payload,
                    validation_status=status,
                    validation_errors=errors,
                    publish_status="pending",
                )
            )

        impact = impact_analysis.summarize_batch_impact(
            rates_ok=ok_count - chunk_ok,
            rates_error=err_count,
            chunks_ok=chunk_ok,
        )
        batch.validation_summary = {
            "ok": ok_count,
            "error": err_count,
            "publishable": ok_count > 0,
            "pipeline": "integrations.v1",
            "source_code": source_code,
            "provider": provider.definition.provider,
            "impact": impact,
            "notice_id": meta.get("notice_id"),
        }
        session.flush()
        detail = ingestion_service.get_batch(session, batch.id)
        return PipelineResult(
            source_code=source_code,
            checksum=batch.checksum,
            archive_path=rel_archive,
            batch=detail,
            records_found=len(records),
            records_ok=ok_count,
            records_error=err_count,
            warnings=list(source_result.warnings),
            impact=impact,
            source_result_meta=dict(meta),
        )


def run(
    session: Session,
    source_code: str,
    *,
    force: bool = False,
) -> PipelineResult:
    return IngestionPipeline().run(session, source_code, force=force)
