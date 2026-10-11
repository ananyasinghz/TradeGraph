"""Corridor / country coverage service (IF-3)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.data.models import Corridor, Country, SourceCoverage
from backend.app.domain.trade import (
    CorridorOut,
    CountryOut,
    SourceCoverageOut,
)


def list_countries(session: Session, *, active_only: bool = True) -> list[CountryOut]:
    stmt = select(Country).order_by(Country.code)
    if active_only:
        stmt = stmt.where(Country.active.is_(True))
    return [
        CountryOut(code=r.code, name=r.name, active=r.active)
        for r in session.scalars(stmt).all()
    ]


def list_corridors(session: Session) -> list[CorridorOut]:
    rows = session.scalars(select(Corridor).order_by(Corridor.origin_country)).all()
    return [
        CorridorOut(
            id=r.id,
            origin_country=r.origin_country,
            destination_country=r.destination_country,
            status=r.status,
            operational=bool(
                getattr(r, "operational", False)
                or (
                    r.origin_country == "BD"
                    and r.destination_country == "IN"
                )
            ),
            supported_hs_chapters=list(r.supported_hs_chapters or []),
            supported_regimes=list(r.supported_regimes or []),
            tariff_source_codes=list(r.tariff_source_codes or []),
            agreement_source_codes=list(r.agreement_source_codes or []),
            regulation_source_codes=list(r.regulation_source_codes or []),
            last_verified_at=r.last_verified_at,
            notes=r.notes,
        )
        for r in rows
    ]


def get_corridor(
    session: Session, origin: str, destination: str
) -> Corridor | None:
    return session.scalar(
        select(Corridor).where(
            Corridor.origin_country == origin.upper(),
            Corridor.destination_country == destination.upper(),
        )
    )


def list_coverage(
    session: Session,
    *,
    corridor_id: str | None = None,
    capability: str | None = None,
) -> list[SourceCoverageOut]:
    stmt = select(SourceCoverage)
    if corridor_id:
        stmt = stmt.where(SourceCoverage.corridor_id == corridor_id)
    if capability:
        stmt = stmt.where(SourceCoverage.capability == capability)
    rows = session.scalars(stmt.order_by(SourceCoverage.source_code)).all()
    return [
        SourceCoverageOut(
            id=r.id,
            source_code=r.source_code,
            corridor_id=r.corridor_id,
            hs_chapter=r.hs_chapter,
            capability=r.capability,
            last_verified_at=r.last_verified_at,
        )
        for r in rows
    ]


def ensure_default_corridors(session: Session) -> None:
    """Idempotent seed for in-memory / create_all test DBs without Alembic data."""
    if session.get(Country, "BD") is None:
        session.add(Country(code="BD", name="Bangladesh", active=True))
    if session.get(Country, "IN") is None:
        session.add(Country(code="IN", name="India", active=True))
    existing = get_corridor(session, "BD", "IN")
    if existing is None:
        corridor = Corridor(
            id="corr_bd_in",
            origin_country="BD",
            destination_country="IN",
            status="demonstration",
            operational=True,
            supported_hs_chapters=["61"],
            supported_regimes=["MFN", "SAFTA"],
            tariff_source_codes=["CBIC_NOTIFICATION_2026_Q3", "CURATED_MIRROR_CBIC_Q3", "IN_CBIC"],
            agreement_source_codes=["SAFTA_ILLUSTRATIVE"],
            regulation_source_codes=["CBIC_NOTIFICATION_2026_Q3", "BD_CUSTOMS"],
            notes="Prototype BD→IN chapter 61 corridor",
        )
        session.add(corridor)
        session.flush()
        for cap in ("tariff_lookup", "tariff_documents", "regulations"):
            session.add(
                SourceCoverage(
                    id=f"cov_cbic_{cap}",
                    source_code="CBIC_NOTIFICATION_2026_Q3",
                    corridor_id="corr_bd_in",
                    hs_chapter="61",
                    capability=cap,
                )
            )
    else:
        existing.operational = True
    # Only BD→IN is operational; clear the flag on any other corridors.
    for other in session.scalars(select(Corridor)).all():
        is_bd_in = other.origin_country == "BD" and other.destination_country == "IN"
        other.operational = bool(is_bd_in)
    session.flush()
