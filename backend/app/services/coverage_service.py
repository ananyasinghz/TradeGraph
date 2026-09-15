"""Dataset coverage miss helpers (PRODUCT_USABILITY_PLAN S2)."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, get_settings
from backend.app.core.errors import AppError
from backend.app.data.models import DataVersion, HsCode, TariffRate
from backend.app.domain.trade import CoverageMissOut


from backend.app.services.data_quality import is_verified_quality


def dataset_coverage_snapshot(session: Session, settings: Settings | None = None) -> dict[str, Any]:
    cfg = settings or get_settings()
    latest = session.scalars(select(DataVersion).order_by(DataVersion.published_at.desc())).first()
    approved = int(
        session.scalar(
            select(func.count())
            .select_from(TariffRate)
            .where(
                TariffRate.status == "active",
                TariffRate.data_quality.in_(("demo_verified", "source_verified")),
            )
        )
        or 0
    )
    active = int(
        session.scalar(
            select(func.count()).select_from(TariffRate).where(TariffRate.status == "active")
        )
        or 0
    )
    chapters = sorted({c for c in session.scalars(select(HsCode.chapter).distinct()).all() if c})
    return {
        "corridor": f"{cfg.default_origin}->{cfg.default_destination}",
        "hs_chapters": chapters or [cfg.prototype_hs_chapter],
        "approved_tariff_rules": approved,
        "active_tariff_rules": active,
        "last_published_update": latest.published_at.isoformat() if latest else None,
        "last_published_label": latest.label if latest else None,
        "official_source_connection": "Not configured",
        "live_government_feed": False,
    }


def build_coverage_miss(
    session: Session,
    *,
    origin: str,
    destination: str,
    hs_code: str | None = None,
    as_of: date | None = None,
    context: str = "tariff",
    settings: Settings | None = None,
) -> CoverageMissOut:
    cfg = settings or get_settings()
    origin_u = origin.upper()
    dest_u = destination.upper()
    reasons: list[str] = []
    actions: list[str] = [
        "Confirm the HS code and as-of date",
        "Search Classify suggestions or Tariff Finder for nearby HS codes",
        "Ingest and approve a BD→IN rate pack for this HS if missing",
        "Stay in Demonstration mode until an approved source is published",
    ]

    if origin_u != cfg.default_origin.upper() or dest_u != cfg.default_destination.upper():
        from backend.app.services.corridor_service import get_corridor, list_corridors

        corridor = get_corridor(session, origin_u, dest_u)
        if corridor is None:
            available = list_corridors(session)
            labels = [
                f"{c.origin_country}->{c.destination_country}" for c in available
            ] or [f"{cfg.default_origin}->{cfg.default_destination}"]
            reasons.append(
                f"Corridor {origin_u}->{dest_u} is not operational yet. "
                f"Available coverage: {', '.join(labels)}."
            )
            actions.insert(0, "Select a supported corridor from GET /api/v1/corridors")
        elif corridor.status not in {"operational", "demonstration"}:
            reasons.append(
                f"Corridor {origin_u}->{dest_u} status is {corridor.status}."
            )
        else:
            reasons.append(
                f"Corridor {origin_u}->{dest_u} is registered ({corridor.status}) "
                f"but this lookup is outside current published coverage."
            )
            actions.insert(0, "Confirm HS chapter and published tariff sources for the corridor")

    if hs_code:
        hs_row = session.get(HsCode, hs_code)
        if hs_row is None:
            reasons.append(f"HS code {hs_code} is not in the current HS catalog.")
            actions.insert(0, "Load HS nomenclature or pick a suggested code from Classify")
        else:
            # Rate coverage still focuses on BD→IN; classification may be any chapter.
            rate_exists = session.scalars(
                select(TariffRate).where(
                    TariffRate.hs_code == hs_code,
                    TariffRate.origin == origin_u,
                    TariffRate.destination == dest_u,
                    TariffRate.status == "active",
                )
            ).first()
            if rate_exists is None and hs_row.chapter != cfg.prototype_hs_chapter:
                reasons.append(
                    f"HS {hs_code} (chapter {hs_row.chapter}) is in the nomenclature "
                    f"catalog, but no active BD→IN duty rate is published yet "
                    f"(prototype rate focus remains chapter {cfg.prototype_hs_chapter})."
                )
                actions.insert(
                    0,
                    "Ingest/approve a tariff rate for this HS (BD→IN) or use a covered code",
                )

    if as_of is not None and hs_code:
        any_rate = session.scalars(
            select(TariffRate).where(
                TariffRate.hs_code == hs_code,
                TariffRate.origin == origin_u,
                TariffRate.destination == dest_u,
            )
        ).first()
        if any_rate is None:
            reasons.append("No tariff rule has been imported for this HS/corridor.")
        else:
            reasons.append(
                "A rule may exist for this HS, but not for the selected as-of date "
                "(outside validity / not yet published)."
            )
            actions.insert(0, "Try another as-of date within the rule validity window")

    if not reasons:
        reasons.append("No approved tariff rule matches this query in the current dataset.")

    if context == "fta":
        actions.append("Request FTA / RoO source review for this product")
    elif context == "ask":
        actions.append("Rephrase with an explicit HS code and BD->IN corridor")

    message = (
        f"No approved tariff coverage for {origin_u}->{dest_u}"
        + (f" HS {hs_code}" if hs_code else "")
        + (f" as of {as_of.isoformat()}" if as_of else "")
        + "."
    )
    return CoverageMissOut(
        message=message,
        origin=origin_u,
        destination=dest_u,
        hs_code=hs_code,
        as_of=as_of,
        possible_reasons=reasons,
        next_actions=actions,
        dataset_coverage=dataset_coverage_snapshot(session, cfg),
    )


def raise_coverage_miss(
    session: Session,
    *,
    origin: str,
    destination: str,
    hs_code: str | None = None,
    as_of: date | None = None,
    context: str = "tariff",
    settings: Settings | None = None,
) -> None:
    miss = build_coverage_miss(
        session,
        origin=origin,
        destination=destination,
        hs_code=hs_code,
        as_of=as_of,
        context=context,
        settings=settings,
    )
    raise AppError(
        code="COVERAGE_MISS",
        message=miss.message,
        status_code=404,
        details=miss.model_dump(mode="json"),
    )
