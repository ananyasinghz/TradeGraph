"""Publish-gate checks before approving an ingest batch."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.app.data.models import IngestionBatch, IngestionProposal

ROOT = Path(__file__).resolve().parents[3]


def evaluate_publish_gate(
    session: Session,
    batch: IngestionBatch,
    proposals: list[IngestionProposal] | None = None,
) -> dict[str, Any]:
    """
    Return a checklist dict. `passed` is True only when all required checks succeed.

    Operational rules must not publish without archive, checksum, authority,
    effective date, and at least one validated proposal.
    """
    del session  # reserved for overlap / duplicate DB checks in later slices
    props = proposals if proposals is not None else list(batch.proposals or [])
    archive_path = batch.archive_path or ""
    path = Path(archive_path)
    if not path.is_absolute():
        path = ROOT / path

    checks: dict[str, bool] = {
        "source_key_present": bool(batch.source_key),
        "original_archived": path.is_file(),
        "checksum_recorded": bool(batch.checksum) and len(batch.checksum) >= 32,
        "issuing_authority_known": bool(batch.publisher) and batch.publisher != "unknown",
        "effective_date_found": batch.effective_from is not None,
        "has_validated_proposals": any(p.validation_status == "ok" for p in props),
        "no_batch_level_blockers": batch.status == "pending_review",
    }

    # Soft evidence checks (recorded but not all hard-required yet)
    soft = {
        "source_page_captured": any(
            isinstance(p.payload_json, dict) and p.payload_json.get("source_page") is not None
            for p in props
            if p.kind == "tariff_rate" and p.validation_status == "ok"
        ),
    }

    failed = [name for name, ok in checks.items() if not ok]
    return {
        "passed": len(failed) == 0,
        "checks": checks,
        "soft_checks": soft,
        "failed": failed,
    }
