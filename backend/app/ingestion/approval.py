"""Approval stage — enforces publish gate then delegates to legacy publish."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.data.models import IngestionBatch
from backend.app.domain.trade import IngestionBatchDetail
from backend.app.ingestion.validation import evaluate_publish_gate
from backend.app.services import ingestion_service


def approve(
    session: Session,
    batch_id: str,
    notes: str | None = None,
) -> IngestionBatchDetail:
    row = session.get(IngestionBatch, batch_id)
    if row is None:
        raise AppError(code="INGEST_BATCH_NOT_FOUND", message="Batch not found", status_code=404)
    if row.status != "pending_review":
        raise AppError(
            code="INGEST_INVALID_STATE",
            message=f"Cannot approve batch in status={row.status}",
            status_code=409,
        )

    # Ensure proposals are loaded for gate evaluation
    _ = row.proposals
    gate = evaluate_publish_gate(session, row)
    if not gate["passed"]:
        raise AppError(
            code="INGEST_PUBLISH_GATE_FAILED",
            message="Publish gate failed: " + ", ".join(gate["failed"]),
            status_code=400,
            details={"publish_gate": gate},
        )
    return ingestion_service.approve_batch(session, batch_id, notes=notes)
