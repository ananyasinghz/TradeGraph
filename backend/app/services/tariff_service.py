"""Tariff and HS lookup services."""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from backend.app.core.errors import AppError
from backend.app.data.models import HsCode, SourceDocument, TariffRate
from backend.app.domain.trade import HsCodeOut, SourceDocumentOut, TariffLookupOut, TariffRateOut
from backend.app.services import coverage_service
from backend.app.services.source_selection_service import SourceSelectionService


def _source_out(doc: SourceDocument) -> SourceDocumentOut:
    from backend.app.services.source_service import source_to_out

    return source_to_out(doc)


def _evidence(row: TariffRate) -> dict:
    doc = row.source_document
    if doc is None:
        return {
            "document_id": row.source_document_id,
            "title": None,
            "verified": False,
            "message": "Source not verified",
        }
    return {
        "document_id": doc.id,
        "title": doc.title,
        "publisher": doc.publisher,
        "archive_path": doc.archive_path or doc.file_path,
        "checksum": doc.checksum,
        "retrieved_at": (doc.fetched_at or doc.retrieved_at).isoformat()
        if (doc.fetched_at or doc.retrieved_at)
        else None,
        "published_at": doc.published_at.isoformat() if doc.published_at else None,
        "status": doc.status,
        "verified": doc.status in {"published", "approved"} and bool(doc.checksum),
    }


def tariff_to_out(
    row: TariffRate,
    *,
    lookup_status: str | None = None,
    source_stale: bool = False,
    selection_warnings: list[str] | None = None,
) -> TariffRateOut:
    quality = (
        row.data_quality
        if row.data_quality in {"illustrative", "demo_verified", "source_verified"}
        else "illustrative"
    )
    regime = row.regime or ("preferential" if row.agreement_id else "mfn")
    confidence = (
        "approved_source"
        if quality in {"demo_verified", "source_verified"} and not source_stale
        else "illustrative_or_stale"
        if source_stale
        else "illustrative"
    )
    return TariffRateOut(
        id=row.id,
        hs_code=row.hs_code,
        origin=row.origin,
        destination=row.destination,
        rate=row.rate,
        rate_type=row.rate_type,
        duty_components=dict(row.duty_components or {}),
        agreement_id=row.agreement_id,
        effective_from=row.effective_from,
        effective_to=row.effective_to,
        source_document_id=row.source_document_id,
        version=row.version,
        status=row.status,
        data_quality=quality,  # type: ignore[arg-type]
        superseded_by=row.superseded_by,
        regime=regime,
        rule_label=row.rule_label,
        notes=row.notes,
        source=_source_out(row.source_document) if row.source_document else None,
        hs_description=row.hs.description if row.hs else None,
        lookup_status=lookup_status,  # type: ignore[arg-type]
        confidence=confidence,
        source_stale=source_stale,
        selection_warnings=list(selection_warnings or []),
        evidence=_evidence(row),
    )


def search_hs_codes(
    session: Session, *, q: str | None = None, chapter: str | None = None
) -> list[HsCodeOut]:
    stmt = select(HsCode)
    if chapter:
        stmt = stmt.where(HsCode.chapter == chapter)
    if q:
        needle = q.strip().lower()
        like = f"%{needle}%"
        stmt = stmt.where(
            or_(
                func.lower(HsCode.code).like(like),
                func.lower(HsCode.description).like(like),
            )
        )
    stmt = stmt.order_by(HsCode.code)
    rows = session.scalars(stmt).all()
    return [
        HsCodeOut(
            code=r.code,
            description=r.description,
            chapter=r.chapter,
            parent_code=r.parent_code,
        )
        for r in rows
    ]


def list_tariffs(
    session: Session,
    *,
    hs_code: str | None = None,
    origin: str | None = None,
    destination: str | None = None,
    as_of: date | None = None,
    include_history: bool = False,
    agreement_id: str | None = None,
) -> list[TariffRateOut]:
    stmt = (
        select(TariffRate)
        .options(joinedload(TariffRate.source_document), joinedload(TariffRate.hs))
        .order_by(TariffRate.hs_code, TariffRate.version.desc())
    )
    if hs_code:
        stmt = stmt.where(TariffRate.hs_code == hs_code)
    if origin:
        stmt = stmt.where(TariffRate.origin == origin.upper())
    if destination:
        stmt = stmt.where(TariffRate.destination == destination.upper())
    if agreement_id:
        stmt = stmt.where(TariffRate.agreement_id == agreement_id)
    if as_of is not None:
        stmt = stmt.where(
            TariffRate.effective_from <= as_of,
            or_(TariffRate.effective_to.is_(None), TariffRate.effective_to >= as_of),
        )
    elif not include_history:
        stmt = stmt.where(TariffRate.status == "active")

    selector = SourceSelectionService()
    rows = session.scalars(stmt).unique().all()
    out: list[TariffRateOut] = []
    for r in rows:
        stale = selector.is_source_stale(r.source_document)
        out.append(
            tariff_to_out(
                r,
                lookup_status="stale" if stale else "found",
                source_stale=stale,
            )
        )
    return out


def get_tariff(session: Session, tariff_id: str) -> TariffRateOut:
    row = session.scalars(
        select(TariffRate)
        .options(joinedload(TariffRate.source_document), joinedload(TariffRate.hs))
        .where(TariffRate.id == tariff_id)
    ).first()
    if row is None:
        raise AppError(code="TARIFF_NOT_FOUND", message="Tariff rate not found", status_code=404)
    selector = SourceSelectionService()
    stale = selector.is_source_stale(row.source_document)
    return tariff_to_out(
        row,
        lookup_status="stale" if stale else "found",
        source_stale=stale,
    )


def get_tariff_history(session: Session, tariff_id: str) -> list[TariffRateOut]:
    current = session.get(TariffRate, tariff_id)
    if current is None:
        raise AppError(code="TARIFF_NOT_FOUND", message="Tariff rate not found", status_code=404)
    return list_tariffs(
        session,
        hs_code=current.hs_code,
        origin=current.origin,
        destination=current.destination,
        include_history=True,
    )


def lookup_tariff(
    session: Session,
    *,
    hs_code: str,
    origin: str,
    destination: str,
    as_of: date,
    regime: str | None = None,
) -> TariffLookupOut:
    selector = SourceSelectionService()
    preferred = selector.preferred_source_codes(session, origin, destination)
    best, warnings = selector.select_best_tariff(
        session,
        origin=origin,
        destination=destination,
        hs_code=hs_code,
        as_of=as_of,
        regime=regime,
    )
    if best is None:
        coverage_service.raise_coverage_miss(
            session,
            origin=origin,
            destination=destination,
            hs_code=hs_code,
            as_of=as_of,
            context="tariff",
        )
        raise AssertionError("unreachable")

    stale = selector.is_source_stale(best.source_document)
    status = "stale" if stale else "found"
    message = None
    if stale:
        message = (
            "The published rule exists, but the source has not been refreshed within "
            "the configured freshness window."
        )
    doc = best.source_document
    last_verified = (doc.fetched_at or doc.retrieved_at) if doc else None
    return TariffLookupOut(
        status=status,  # type: ignore[arg-type]
        tariff=tariff_to_out(
            best,
            lookup_status=status,
            source_stale=stale,
            selection_warnings=warnings,
        ),
        message=message,
        last_verified_at=last_verified,
        selection_warnings=warnings,
        preferred_source_codes=preferred,
    )


def resolve_applicable_tariff(
    session: Session,
    *,
    hs_code: str,
    origin: str,
    destination: str,
    as_of: date,
) -> TariffRate:
    selector = SourceSelectionService()
    best, _warnings = selector.select_best_tariff(
        session,
        origin=origin,
        destination=destination,
        hs_code=hs_code,
        as_of=as_of,
    )
    if best is None:
        coverage_service.raise_coverage_miss(
            session,
            origin=origin,
            destination=destination,
            hs_code=hs_code,
            as_of=as_of,
            context="tariff",
        )
        raise AssertionError("unreachable")
    return best
