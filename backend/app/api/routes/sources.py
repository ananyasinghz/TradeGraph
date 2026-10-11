"""Source document listing, archive registration, and status machine."""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.app.api.auth_deps import ReviewerDep, ViewerDep
from backend.app.api.dependencies import SessionDep
from backend.app.domain.trade import (
    SourceArchiveRequest,
    SourceDocumentOut,
    SourceStatusTransition,
)
from backend.app.services import source_service
from backend.app.services.auth_service import audit_from_request

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=list[SourceDocumentOut])
def list_sources(session: SessionDep, _principal: ViewerDep) -> list[SourceDocumentOut]:
    return source_service.list_sources(session)


@router.get("/{source_id}", response_model=SourceDocumentOut)
def get_source(
    source_id: str, session: SessionDep, _principal: ViewerDep
) -> SourceDocumentOut:
    return source_service.get_source(session, source_id)


@router.post("/archive", response_model=SourceDocumentOut)
def archive_source(
    payload: SourceArchiveRequest,
    session: SessionDep,
    request: Request,
    principal: ReviewerDep,
) -> SourceDocumentOut:
    out = source_service.archive_source(session, payload)
    audit_from_request(
        session,
        request,
        principal,
        action="source.archive",
        resource_type="source",
        resource_id=out.id,
    )
    return out


@router.post("/{source_id}/transition", response_model=SourceDocumentOut)
def transition_source(
    source_id: str,
    payload: SourceStatusTransition,
    session: SessionDep,
    request: Request,
    principal: ReviewerDep,
) -> SourceDocumentOut:
    out = source_service.transition_status(session, source_id, payload)
    audit_from_request(
        session,
        request,
        principal,
        action="source.transition",
        resource_type="source",
        resource_id=source_id,
        detail={"status": payload.status},
    )
    return out
