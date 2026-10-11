"""Org-scoped search across cases, HS codes, and documents (R11)."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.app.data.models import DocumentUpload, HsCode, Shipment
from backend.app.domain.trade import SearchHitOut, SearchOut


def search(
    session: Session,
    q: str,
    *,
    organization_id: str | None = None,
    limit: int = 25,
) -> SearchOut:
    query = (q or "").strip()
    if not query:
        return SearchOut(query=query, results=[])
    like = f"%{query}%"
    results: list[SearchHitOut] = []

    ship_stmt = select(Shipment).where(
        or_(
            Shipment.title.ilike(like),
            Shipment.product_text.ilike(like),
            Shipment.hs_code_working.ilike(like),
        )
    )
    if organization_id:
        ship_stmt = ship_stmt.where(Shipment.organization_id == organization_id)
    for row in session.scalars(ship_stmt.order_by(Shipment.updated_at.desc()).limit(limit)).all():
        if (row.status or "").lower() in {"discarded", "deleted"}:
            continue
        results.append(
            SearchHitOut(
                kind="shipment",
                id=row.id,
                title=row.title,
                snippet=(row.product_text or "")[:160],
                shipment_id=row.id,
                hs_code=row.hs_code_working,
            )
        )

    for hs in session.scalars(
        select(HsCode)
        .where(or_(HsCode.code.ilike(like), HsCode.description.ilike(like)))
        .limit(limit)
    ).all():
        results.append(
            SearchHitOut(
                kind="hs",
                id=hs.code,
                title=hs.code,
                snippet=(hs.description or "")[:160],
                hs_code=hs.code,
            )
        )

    doc_stmt = (
        select(DocumentUpload, Shipment)
        .join(Shipment, Shipment.id == DocumentUpload.shipment_id)
        .where(
            or_(
                DocumentUpload.filename.ilike(like),
                DocumentUpload.doc_code.ilike(like),
            )
        )
    )
    if organization_id:
        doc_stmt = doc_stmt.where(Shipment.organization_id == organization_id)
    for upload, ship in session.execute(doc_stmt.limit(limit)).all():
        results.append(
            SearchHitOut(
                kind="document",
                id=upload.id,
                title=upload.filename,
                snippet=f"{upload.doc_code} · {ship.title}",
                shipment_id=ship.id,
            )
        )

    return SearchOut(query=query, results=results[:limit])
