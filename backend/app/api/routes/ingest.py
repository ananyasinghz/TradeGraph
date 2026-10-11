"""Ingestion / data-version admin APIs (Phase 4 + IF-2/IF-4 + IF-11b)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.app.api.auth_deps import OperatorDep, PublisherDep, ViewerDep
from backend.app.api.dependencies import SessionDep
from backend.app.domain.trade import (
    DataVersionOut,
    IngestBatchDiffOut,
    IngestionBatchDetail,
    IngestionBatchOut,
    IngestReviewRequest,
    IngestRunRequest,
    PromoteCbicResult,
)
from backend.app.ingestion import approval, pipeline
from backend.app.integrations.core.registry import get_registry
from backend.app.services import ingestion_service, promote_service
from backend.app.services.auth_service import audit_from_request

router = APIRouter(tags=["ingestion"])


@router.post("/ingest/run", response_model=IngestionBatchDetail)
def ingest_run(
    session: SessionDep,
    request: Request,
    principal: PublisherDep,
    payload: IngestRunRequest | None = None,
) -> IngestionBatchDetail:
    req = payload or IngestRunRequest()
    source_key = req.source_key or "cbic_notification_2026_q3"
    registry = get_registry()
    if registry.has(source_key):
        result = pipeline.run(session, source_key, force=req.force)
        assert result.batch is not None
        batch = result.batch
    elif registry.has(source_key.upper()):
        result = pipeline.run(session, source_key.upper(), force=req.force)
        assert result.batch is not None
        batch = result.batch
    else:
        batch = ingestion_service.run_ingest(session, req)
    audit_from_request(
        session,
        request,
        principal,
        action="ingest.run",
        resource_type="ingestion_batch",
        resource_id=getattr(batch, "id", None),
        detail={"source_key": source_key},
    )
    return batch


@router.get("/ingest/batches", response_model=list[IngestionBatchOut])
def ingest_list(session: SessionDep, _principal: OperatorDep) -> list[IngestionBatchOut]:
    return ingestion_service.list_batches(session)


@router.get("/ingest/batches/{batch_id}", response_model=IngestionBatchDetail)
def ingest_get(
    batch_id: str, session: SessionDep, _principal: OperatorDep
) -> IngestionBatchDetail:
    return ingestion_service.get_batch(session, batch_id)


@router.get("/ingest/batches/{batch_id}/diff", response_model=IngestBatchDiffOut)
def ingest_diff(
    batch_id: str, session: SessionDep, _principal: OperatorDep
) -> IngestBatchDiffOut:
    return ingestion_service.batch_diff(session, batch_id)


@router.post("/ingest/batches/{batch_id}/approve", response_model=IngestionBatchDetail)
def ingest_approve(
    batch_id: str,
    session: SessionDep,
    request: Request,
    principal: PublisherDep,
    payload: IngestReviewRequest | None = None,
) -> IngestionBatchDetail:
    notes = payload.notes if payload else None
    out = approval.approve(session, batch_id, notes=notes)
    audit_from_request(
        session,
        request,
        principal,
        action="ingest.approve",
        resource_type="ingestion_batch",
        resource_id=batch_id,
    )
    return out


@router.post("/ingest/batches/{batch_id}/reject", response_model=IngestionBatchDetail)
def ingest_reject(
    batch_id: str,
    session: SessionDep,
    request: Request,
    principal: PublisherDep,
    payload: IngestReviewRequest | None = None,
) -> IngestionBatchDetail:
    notes = payload.notes if payload else None
    out = ingestion_service.reject_batch(session, batch_id, notes=notes)
    audit_from_request(
        session,
        request,
        principal,
        action="ingest.reject",
        resource_type="ingestion_batch",
        resource_id=batch_id,
    )
    return out


@router.post("/ingest/promote-cbic", response_model=PromoteCbicResult)
def promote_cbic(
    session: SessionDep,
    request: Request,
    principal: PublisherDep,
    payload: IngestReviewRequest | None = None,
) -> PromoteCbicResult:
    """One-button IF-11b path: fixture → ingest → approve → publish verified rates."""
    notes = payload.notes if payload else None
    out = promote_service.promote_cbic_fixture(session, notes=notes)
    audit_from_request(
        session,
        request,
        principal,
        action="ingest.promote_cbic",
        resource_type="ingestion",
    )
    return out


@router.get("/data-versions", response_model=list[DataVersionOut])
def data_versions(session: SessionDep, _principal: ViewerDep) -> list[DataVersionOut]:
    return ingestion_service.list_data_versions(session)
