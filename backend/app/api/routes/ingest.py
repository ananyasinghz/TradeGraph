"""Ingestion / data-version admin APIs (Phase 4 + IF-2/IF-4 + IF-11b)."""

from __future__ import annotations

from fastapi import APIRouter

from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.api.dependencies import SessionDep
from backend.app.domain.trade import (
    DataVersionOut,
    IngestionBatchDetail,
    IngestionBatchOut,
    IngestReviewRequest,
    IngestRunRequest,
    PromoteCbicResult,
)
from backend.app.ingestion import approval, pipeline
from backend.app.integrations.core.registry import get_registry
from backend.app.services import ingestion_service, promote_service
from backend.app.services.auth_service import Principal, require_role

router = APIRouter(tags=["ingestion"])

ReviewerDep = Annotated[Principal, Depends(require_role("reviewer"))]


@router.post("/ingest/run", response_model=IngestionBatchDetail)
def ingest_run(
    session: SessionDep,
    payload: IngestRunRequest | None = None,
) -> IngestionBatchDetail:
    req = payload or IngestRunRequest()
    source_key = req.source_key or "cbic_notification_2026_q3"
    registry = get_registry()
    if registry.has(source_key):
        result = pipeline.run(session, source_key, force=req.force)
        assert result.batch is not None
        return result.batch
    # Prefer pipeline alias when only lowercase key provided
    if registry.has(source_key.upper()):
        result = pipeline.run(session, source_key.upper(), force=req.force)
        assert result.batch is not None
        return result.batch
    return ingestion_service.run_ingest(session, req)


@router.get("/ingest/batches", response_model=list[IngestionBatchOut])
def ingest_list(session: SessionDep) -> list[IngestionBatchOut]:
    return ingestion_service.list_batches(session)


@router.get("/ingest/batches/{batch_id}", response_model=IngestionBatchDetail)
def ingest_get(batch_id: str, session: SessionDep) -> IngestionBatchDetail:
    return ingestion_service.get_batch(session, batch_id)


@router.post("/ingest/batches/{batch_id}/approve", response_model=IngestionBatchDetail)
def ingest_approve(
    batch_id: str,
    session: SessionDep,
    _principal: ReviewerDep,
    payload: IngestReviewRequest | None = None,
) -> IngestionBatchDetail:
    notes = payload.notes if payload else None
    return approval.approve(session, batch_id, notes=notes)


@router.post("/ingest/batches/{batch_id}/reject", response_model=IngestionBatchDetail)
def ingest_reject(
    batch_id: str,
    session: SessionDep,
    _principal: ReviewerDep,
    payload: IngestReviewRequest | None = None,
) -> IngestionBatchDetail:
    notes = payload.notes if payload else None
    return ingestion_service.reject_batch(session, batch_id, notes=notes)


@router.post("/ingest/promote-cbic", response_model=PromoteCbicResult)
def promote_cbic(
    session: SessionDep,
    _principal: ReviewerDep,
    payload: IngestReviewRequest | None = None,
) -> PromoteCbicResult:
    """One-button IF-11b path: fixture → ingest → approve → publish verified rates."""
    notes = payload.notes if payload else None
    return promote_service.promote_cbic_fixture(session, notes=notes)


@router.get("/data-versions", response_model=list[DataVersionOut])
def data_versions(session: SessionDep) -> list[DataVersionOut]:
    return ingestion_service.list_data_versions(session)
