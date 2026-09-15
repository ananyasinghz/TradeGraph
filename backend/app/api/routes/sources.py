"""Source document listing, archive registration, and status machine."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.dependencies import SessionDep
from backend.app.domain.trade import (
    SourceArchiveRequest,
    SourceDocumentOut,
    SourceStatusTransition,
)
from backend.app.services import source_service

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=list[SourceDocumentOut])
def list_sources(session: SessionDep) -> list[SourceDocumentOut]:
    return source_service.list_sources(session)


@router.get("/{source_id}", response_model=SourceDocumentOut)
def get_source(source_id: str, session: SessionDep) -> SourceDocumentOut:
    return source_service.get_source(session, source_id)


@router.post("/archive", response_model=SourceDocumentOut)
def archive_source(payload: SourceArchiveRequest, session: SessionDep) -> SourceDocumentOut:
    return source_service.archive_source(session, payload)


@router.post("/{source_id}/transition", response_model=SourceDocumentOut)
def transition_source(
    source_id: str, payload: SourceStatusTransition, session: SessionDep
) -> SourceDocumentOut:
    return source_service.transition_status(session, source_id, payload)
