"""Global product mode and dataset coverage (S1 + IF-11a + IF-12a)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.data.models import DataVersion, HsCode, IngestionBatch, TariffRate
from backend.app.domain.trade import (
    ActiveRulesOut,
    CoverageOut,
    DataStatusOut,
    LatestSourceBatchOut,
    SystemStatusOut,
)
from backend.app.services import cost_service, source_connection_service

DISCLAIMER = (
    "Not an official customs determination. TradeGraph does not treat curated "
    "mirrors as a live government API. Verified source means a reviewer approved "
    "a published batch in this prototype — still verify against official sources "
    "before filing."
)


def _effective_product_status(approved: int, illustrative: int) -> str:
    if approved > 0 and illustrative == 0:
        return "verified"
    if approved > 0 and illustrative > 0:
        return "mixed"
    return "illustrative"


def _dataset_type_for_status(effective: str) -> str:
    if effective == "verified":
        return "Checked duty rates (all active)"
    if effective == "mixed":
        return "Mixed sample and checked rates"
    return "Sample rates only"


def _has_operational_corpus(session: Session) -> tuple[bool, int, str | None]:
    """Operational requires a published data version and at least one approved-quality rate."""
    latest = session.scalars(select(DataVersion).order_by(DataVersion.published_at.desc())).first()
    approved_count = session.scalar(
        select(func.count())
        .select_from(TariffRate)
        .where(
            TariffRate.status == "active",
            TariffRate.data_quality.in_(("demo_verified", "source_verified")),
        )
    )
    count = int(approved_count or 0)
    if latest is None:
        return False, count, "No published data version is available."
    if count <= 0:
        return (
            False,
            count,
            "No approved (demo_verified/source_verified) active tariff rules are published yet.",
        )
    return True, count, None


def _latest_source_batch(session: Session) -> LatestSourceBatchOut | None:
    latest_version = session.scalars(
        select(DataVersion).order_by(DataVersion.published_at.desc())
    ).first()
    if latest_version is None:
        latest_batch = session.scalars(
            select(IngestionBatch).order_by(IngestionBatch.created_at.desc())
        ).first()
        if latest_batch is None:
            return None
        return LatestSourceBatchOut(
            id=latest_batch.id,
            label=f"ingest:{latest_batch.source_key}",
            status=latest_batch.status,
            published_at=None,
        )
    batch_status = "approved"
    if latest_version.batch_id:
        batch = session.get(IngestionBatch, latest_version.batch_id)
        if batch is not None:
            batch_status = batch.status
    return LatestSourceBatchOut(
        id=latest_version.batch_id or latest_version.id,
        label=latest_version.label,
        status=batch_status,
        published_at=latest_version.published_at,
    )


def _trust_notice(
    effective: str,
    batch: LatestSourceBatchOut | None,
    approved: int,
) -> str | None:
    if batch is None:
        return None
    batch_ok = (batch.status or "").lower() in {"approved", "published", "ok"}
    if batch_ok and approved == 0:
        return (
            "An approved source batch exists, but active duty rates are still sample "
            "(illustrative). Calculator trust follows active rules, not batch existence."
        )
    if effective == "mixed":
        return (
            f"{approved} checked active duty rate(s) are in use; remaining active rates "
            "are still sample. Do not treat the full catalog as verified."
        )
    return None


def build_system_status(session: Session, settings: Settings) -> SystemStatusOut:
    requested = settings.product_mode
    can_operate, approved_count, block_reason = _has_operational_corpus(session)

    mode_forced = False
    mode_lock_reason: str | None = None
    effective = requested
    if requested == "operational" and not can_operate:
        effective = "demonstration"
        mode_forced = True
        mode_lock_reason = (
            f"Operational mode requested but unavailable: {block_reason} "
            "Showing Demonstration until an approved published corpus exists."
        )

    illustrative_count = int(
        session.scalar(
            select(func.count())
            .select_from(TariffRate)
            .where(
                TariffRate.status == "active",
                TariffRate.data_quality == "illustrative",
            )
        )
        or 0
    )
    active_count = int(
        session.scalar(
            select(func.count()).select_from(TariffRate).where(TariffRate.status == "active")
        )
        or 0
    )

    chapters = sorted(
        {
            c
            for c in session.scalars(select(HsCode.chapter).distinct()).all()
            if c
        }
    )
    if settings.prototype_hs_chapter and settings.prototype_hs_chapter not in chapters:
        chapters = [settings.prototype_hs_chapter, *chapters]

    product_status = _effective_product_status(approved_count, illustrative_count)
    batch = _latest_source_batch(session)
    trust = _trust_notice(product_status, batch, approved_count)

    # last_approved_* = last time verified active rates were published (not mere DataVersion)
    last_approved_at = None
    last_approved_label = None
    if approved_count > 0 and batch and batch.published_at:
        last_approved_at = batch.published_at
        last_approved_label = batch.label

    feed = source_connection_service.feed_status(session, settings)
    customs = cost_service.customs_mode_availability(session)

    notices: list[str] = []
    if trust:
        notices.append(trust)
    if effective == "demonstration":
        notices.extend(
            [
                "Demo data",
                "Sample rates in use" if illustrative_count > 0 else "Checked rates published",
                "Not an official customs determination",
                feed.source_connection_label,
            ]
        )
    else:
        notices.extend(
            [
                "Operational mode — curated approved sources only for compliance lookups",
                "Not a substitute for licensed customs advice",
                feed.source_connection_label,
            ]
        )

    origin = settings.default_origin.upper()
    destination = settings.default_destination.upper()
    corridor = (
        "Bangladesh -> India"
        if origin == "BD" and destination == "IN"
        else f"{origin} -> {destination}"
    )
    chapters_final = chapters or [settings.prototype_hs_chapter]
    active_rules = ActiveRulesOut(
        total=active_count,
        approved=approved_count,
        illustrative=illustrative_count,
    )

    return SystemStatusOut(
        product_mode=effective,
        requested_product_mode=requested,
        mode_forced=mode_forced,
        mode_lock_reason=mode_lock_reason,
        corridor=corridor,
        origin=origin,
        destination=destination,
        hs_chapter=settings.prototype_hs_chapter,
        hs_chapters=chapters_final,
        coverage=CoverageOut(
            origin=origin,
            destination=destination,
            hs_chapters=chapters_final,
        ),
        active_rules=active_rules,
        latest_source_batch=batch,
        effective_product_status=product_status,  # type: ignore[arg-type]
        trust_notice=trust,
        approved_tariff_rule_count=approved_count,
        illustrative_tariff_rule_count=illustrative_count,
        active_tariff_rule_count=active_count,
        last_approved_at=last_approved_at,
        last_approved_label=last_approved_label,
        official_source_connection=feed.official_source_connection,
        source_connection_kind=feed.source_connection_kind,
        source_connection_label=feed.source_connection_label,
        live_government_feed=feed.live_government_feed,
        live_feed_reason=feed.live_feed_reason,
        enabled_source_connection_count=feed.enabled_connection_count,
        last_source_fetch_at=feed.last_successful_fetch_at,
        source_fetch_interval_minutes=feed.scheduler_interval_minutes,
        customs_mode_available=customs.customs_mode_available,
        customs_mode_blockers=list(customs.customs_mode_blockers),
        customs_mode_hint=customs.customs_mode_hint,
        notices=notices,
        disclaimer=DISCLAIMER,
    )


def data_status_from_system(status: SystemStatusOut) -> DataStatusOut:
    """IF-12a: Home and banner share one authoritative status derivation."""
    return DataStatusOut(
        corridor=status.corridor.replace("->", "→"),
        hs_chapter=status.hs_chapter,
        dataset_type=_dataset_type_for_status(status.effective_product_status),
        last_approved_at=status.last_approved_at,
        last_approved_label=status.last_approved_label,
        note=status.trust_notice or (
            "Not a live customs determination. Verify against official sources."
        ),
        effective_product_status=status.effective_product_status,
        active_rules=status.active_rules,
        latest_source_batch=status.latest_source_batch,
        trust_notice=status.trust_notice,
    )
