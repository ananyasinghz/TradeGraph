"""Document requirement catalog API."""

from __future__ import annotations

from fastapi import APIRouter, Query

from backend.app.api.dependencies import SessionDep
from backend.app.domain.trade import DocumentRequirementOut, DocWhyRequiredOut
from backend.app.services import checklist_service, document_service

router = APIRouter(prefix="/document-requirements", tags=["documents"])


@router.get("/why", response_model=DocWhyRequiredOut)
def document_why_required(
    session: SessionDep,
    doc_code: str = Query(...),
    origin: str = Query(default="BD"),
    destination: str = Query(default="IN"),
    hs: str | None = Query(default=None),
) -> DocWhyRequiredOut:
    return document_service.why_required(
        session,
        doc_code=doc_code,
        origin=origin,
        destination=destination,
        hs_code=hs,
    )


@router.get("", response_model=list[DocumentRequirementOut])
def list_requirements(
    session: SessionDep,
    origin: str | None = Query(default="BD"),
    destination: str | None = Query(default="IN"),
    hs: str | None = Query(default=None),
) -> list[DocumentRequirementOut]:
    return checklist_service.list_document_requirements(
        session,
        origin=origin,
        destination=destination,
        hs_code=hs,
    )
