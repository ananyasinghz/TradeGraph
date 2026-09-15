"""Document checklist builder from structured requirements."""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.app.data.models import DocumentRequirement
from backend.app.domain.trade import ChecklistItemOut, ChecklistOut, DocumentRequirementOut
from backend.app.services.document_service import normalize_checklist_item


def _progress(items: list[ChecklistItemOut]) -> str:
    ready = sum(1 for i in items if i.status == "ready" or i.done)
    return f"{ready}/{len(items)}"


def build_checklist(
    session: Session,
    *,
    origin: str,
    destination: str,
    hs_code: str | None = None,
    prior_items: list[dict[str, Any]] | None = None,
) -> ChecklistOut:
    filters = [
        DocumentRequirement.origin == origin.upper(),
        DocumentRequirement.destination == destination.upper(),
    ]
    if hs_code:
        filters.append(
            or_(DocumentRequirement.hs_code.is_(None), DocumentRequirement.hs_code == hs_code)
        )
    else:
        filters.append(DocumentRequirement.hs_code.is_(None))

    rows = session.scalars(
        select(DocumentRequirement).where(*filters).order_by(DocumentRequirement.doc_code)
    ).all()
    prior = {
        normalize_checklist_item(i).doc_code: normalize_checklist_item(i)
        for i in (prior_items or [])
    }
    items: list[ChecklistItemOut] = []
    for r in rows:
        prev = prior.get(r.doc_code)
        items.append(
            ChecklistItemOut(
                doc_code=r.doc_code,
                doc_label=r.doc_label,
                required=bool(r.required),
                notes=r.notes,
                status=prev.status if prev else "not_started",
                done=(prev.status == "ready") if prev else False,
            )
        )
    return ChecklistOut(
        origin=origin.upper(),
        destination=destination.upper(),
        hs_code=hs_code,
        items=items,
        progress=_progress(items),
    )


def list_document_requirements(
    session: Session,
    *,
    origin: str | None = None,
    destination: str | None = None,
    hs_code: str | None = None,
) -> list[DocumentRequirementOut]:
    stmt = select(DocumentRequirement).order_by(
        DocumentRequirement.origin,
        DocumentRequirement.destination,
        DocumentRequirement.doc_code,
    )
    if origin:
        stmt = stmt.where(DocumentRequirement.origin == origin.upper())
    if destination:
        stmt = stmt.where(DocumentRequirement.destination == destination.upper())
    if hs_code:
        stmt = stmt.where(
            or_(DocumentRequirement.hs_code.is_(None), DocumentRequirement.hs_code == hs_code)
        )
    rows = session.scalars(stmt).all()
    return [
        DocumentRequirementOut(
            id=r.id,
            origin=r.origin,
            destination=r.destination,
            hs_code=r.hs_code,
            doc_code=r.doc_code,
            doc_label=r.doc_label,
            required=bool(r.required),
            notes=r.notes,
        )
        for r in rows
    ]
