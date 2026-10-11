"""Scenario financial impact when tariffs change (IF-11e + IF-12c)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.data.models import CalculationSnapshot, ScenarioImpact, Shipment, TariffRate
from backend.app.domain.trade import LandedCostInput, ScenarioImpactOut
from backend.app.services import cost_service


def _now() -> datetime:
    return datetime.now(UTC)


def _component_deltas(old_comps: dict | None, new_comps: dict | None) -> dict[str, object]:
    from backend.app.services.component_provenance import COMPONENT_KEYS, flatten_rates

    old_flat = flatten_rates(old_comps)
    new_flat = flatten_rates(new_comps)
    deltas: dict[str, object] = {}
    for key in COMPONENT_KEYS:
        o = old_flat.get(key)
        n = new_flat.get(key)
        if o != n:
            deltas[key] = {"old": o, "new": n}
    return deltas


def _impact_out(session: Session, row: ScenarioImpact) -> ScenarioImpactOut:
    from backend.app.services.component_provenance import applicable_stack_signature

    ship = session.get(Shipment, row.shipment_id)
    old_tariff = (
        session.get(TariffRate, row.old_tariff_rate_id) if row.old_tariff_rate_id else None
    )
    new_tariff = (
        session.get(TariffRate, row.new_tariff_rate_id) if row.new_tariff_rate_id else None
    )
    old_sig = (
        applicable_stack_signature(old_tariff.duty_components) if old_tariff else None
    )
    new_sig = (
        applicable_stack_signature(new_tariff.duty_components) if new_tariff else None
    )
    deltas = (
        _component_deltas(
            old_tariff.duty_components if old_tariff else None,
            new_tariff.duty_components if new_tariff else None,
        )
        if old_tariff or new_tariff
        else {}
    )
    return ScenarioImpactOut(
        id=row.id,
        shipment_id=row.shipment_id,
        shipment_title=ship.title if ship else None,
        organization_id=row.organization_id,
        hs_code=row.hs_code,
        origin=row.origin,
        destination=row.destination,
        old_rate=row.old_rate,
        new_rate=row.new_rate,
        old_landed_cost=row.old_landed_cost,
        new_landed_cost=row.new_landed_cost,
        duty_delta=row.duty_delta,
        landed_delta=row.landed_delta,
        currency=row.currency,
        old_tariff_rate_id=row.old_tariff_rate_id,
        new_tariff_rate_id=row.new_tariff_rate_id,
        old_snapshot_id=row.old_snapshot_id,
        new_snapshot_id=row.new_snapshot_id,
        recommended_action=row.recommended_action,
        summary=row.summary,
        created_at=row.created_at,
        source_document_id=row.source_document_id,
        effective_from=row.effective_from,
        acknowledged_at=row.acknowledged_at,
        acknowledged_by=row.acknowledged_by,
        dedupe_key=row.dedupe_key,
        old_stack_signature=old_sig,
        new_stack_signature=new_sig,
        component_deltas=deltas,
    )


def list_impacts(
    session: Session,
    *,
    limit: int = 50,
    include_acknowledged: bool = False,
) -> list[ScenarioImpactOut]:
    stmt = select(ScenarioImpact).order_by(ScenarioImpact.created_at.desc()).limit(limit * 3)
    rows = session.scalars(stmt).all()
    out: list[ScenarioImpactOut] = []
    for r in rows:
        if not include_acknowledged and r.acknowledged_at is not None:
            continue
        out.append(_impact_out(session, r))
        if len(out) >= limit:
            break
    return out


def acknowledge_impact(
    session: Session,
    impact_id: str,
    *,
    actor: str = "operator",
    organization_id: str | None = None,
) -> ScenarioImpactOut:
    row = session.get(ScenarioImpact, impact_id)
    if row is None:
        raise AppError(code="IMPACT_NOT_FOUND", message="Impact not found", status_code=404)
    if (
        organization_id
        and row.organization_id
        and row.organization_id != organization_id
    ):
        raise AppError(
            code="ORG_FORBIDDEN",
            message="Impact not in your organization",
            status_code=403,
        )
    row.acknowledged_at = _now()
    row.acknowledged_by = actor
    session.flush()
    return _impact_out(session, row)


def matching_scenarios(
    session: Session,
    *,
    hs_code: str,
    origin: str,
    destination: str,
    organization_id: str | None = None,
) -> list[Shipment]:
    stmt = select(Shipment).where(
        Shipment.hs_code_working == hs_code,
        Shipment.origin == origin.upper(),
        Shipment.destination == destination.upper(),
    )
    if organization_id:
        stmt = stmt.where(Shipment.organization_id == organization_id)
    return list(session.scalars(stmt).all())


def _recommended_action(*, rate_up: bool) -> str:
    if rate_up:
        return (
            "Review the purchase-order margin and verify whether preferential "
            "treatment is available; re-check certificate of origin readiness."
        )
    return (
        "Confirm preferential eligibility and document readiness; "
        "consider updating landed-cost quotes for customers."
    )


def _dedupe_key(
    *,
    shipment_id: str,
    hs_code: str,
    new_tariff_id: str,
    effective_from: object,
) -> str:
    return f"{new_tariff_id}|{shipment_id}|{hs_code}|bcd|{effective_from}"


def record_impacts_for_new_tariff(
    session: Session,
    *,
    new_tariff: TariffRate,
    old_tariff: TariffRate | None,
) -> list[ScenarioImpactOut]:
    """Recalculate matching scenarios and persist impact rows."""
    if old_tariff is None:
        return []
    from backend.app.services.component_provenance import applicable_stack_signature

    # Alert only when applicable merged component rates change (ignore provenance-only churn).
    old_sig = applicable_stack_signature(old_tariff.duty_components)
    new_sig = applicable_stack_signature(new_tariff.duty_components)
    same_rate = old_tariff.rate == new_tariff.rate
    if same_rate and old_sig == new_sig:
        return []

    ships = matching_scenarios(
        session,
        hs_code=new_tariff.hs_code,
        origin=new_tariff.origin,
        destination=new_tariff.destination,
    )
    out: list[ScenarioImpactOut] = []
    for ship in ships:
        if not ship.hs_code_working:
            continue
        key = _dedupe_key(
            shipment_id=ship.id,
            hs_code=new_tariff.hs_code,
            new_tariff_id=new_tariff.id,
            effective_from=new_tariff.effective_from,
        )
        existing = session.scalars(
            select(ScenarioImpact).where(ScenarioImpact.dedupe_key == key)
        ).first()
        if existing is not None:
            continue

        uncertain = (
            ship.hs_confirmed_at is None
            or ship.freight is None
            or ship.insurance is None
        )

        old_snap = session.scalars(
            select(CalculationSnapshot)
            .where(CalculationSnapshot.shipment_id == ship.id)
            .order_by(CalculationSnapshot.created_at.desc())
        ).first()
        old_landed = None
        old_duties = None
        if old_snap is not None:
            outputs = old_snap.outputs_json or {}
            if outputs.get("landed_cost") is not None:
                old_landed = Decimal(str(outputs.get("landed_cost")))
            if outputs.get("total_duties_taxes") is not None:
                old_duties = Decimal(str(outputs.get("total_duties_taxes")))

        mode = "estimate"
        avail = cost_service.customs_mode_availability(
            session,
            freight=ship.freight,
            insurance=ship.insurance,
            tariff=new_tariff,
            require_scenario_inputs=True,
        )
        if avail.customs_mode_available:
            mode = "customs"

        new_landed = None
        new_duties = None
        new_snap = None
        duty_delta = None
        landed_delta = None
        if uncertain:
            summary = (
                f"Tariff update · HS {new_tariff.hs_code} · BCD {old_tariff.rate}% → "
                f"{new_tariff.rate}% · Case “{ship.title}” needs review "
                f"(incomplete freight/insurance or unconfirmed HS) before asserting duty change."
            )
            action = (
                "Review case inputs (confirm HS, freight, insurance) before treating "
                "this tariff update as a definitive duty change."
            )
        else:
            try:
                breakdown = cost_service.calculate(
                    session,
                    LandedCostInput(
                        hs_code=ship.hs_code_working,
                        origin=ship.origin,
                        destination=ship.destination,
                        as_of=ship.as_of_date,
                        invoice_value=ship.invoice_value,
                        currency=ship.currency,
                        incoterm=ship.incoterm,
                        freight=ship.freight,
                        insurance=ship.insurance,
                        requested_mode=mode,  # type: ignore[arg-type]
                        shipment_id=ship.id,
                        persist_snapshot=True,
                    ),
                )
            except AppError:
                summary = (
                    f"Tariff update · HS {new_tariff.hs_code} · BCD {old_tariff.rate}% → "
                    f"{new_tariff.rate}% · Case “{ship.title}” could not be recalculated; "
                    f"review manually."
                )
                action = "Review case — recalculation blocked; do not assert a duty delta."
                uncertain = True
            else:
                new_snap = session.scalars(
                    select(CalculationSnapshot)
                    .where(CalculationSnapshot.shipment_id == ship.id)
                    .order_by(CalculationSnapshot.created_at.desc())
                ).first()
                new_landed = breakdown.landed_cost
                new_duties = breakdown.total_duties_taxes
                duty_delta = (new_duties - old_duties) if old_duties is not None else None
                landed_delta = (new_landed - old_landed) if old_landed is not None else None
                rate_up = new_tariff.rate > old_tariff.rate
                delta_txt = (
                    f"duty {duty_delta:+} {ship.currency}"
                    if duty_delta is not None
                    else f"landed now {new_landed} {ship.currency}"
                )
                summary = (
                    f"Tariff update · HS {new_tariff.hs_code} · BCD {old_tariff.rate}% → "
                    f"{new_tariff.rate}% · Impact on “{ship.title}”: {delta_txt}"
                )
                action = _recommended_action(rate_up=rate_up)

        row = ScenarioImpact(
            shipment_id=ship.id,
            organization_id=ship.organization_id,
            hs_code=new_tariff.hs_code,
            origin=new_tariff.origin,
            destination=new_tariff.destination,
            old_rate=old_tariff.rate,
            new_rate=new_tariff.rate,
            old_landed_cost=old_landed,
            new_landed_cost=new_landed,
            duty_delta=duty_delta,
            landed_delta=landed_delta,
            currency=ship.currency,
            old_tariff_rate_id=old_tariff.id,
            new_tariff_rate_id=new_tariff.id,
            old_snapshot_id=old_snap.id if old_snap else None,
            new_snapshot_id=new_snap.id if new_snap else None,
            recommended_action=action,
            summary=summary,
            created_at=_now(),
            dedupe_key=key,
            source_document_id=new_tariff.source_document_id,
            effective_from=new_tariff.effective_from,
        )
        session.add(row)
        session.flush()
        out.append(_impact_out(session, row))

        from backend.app.services import timeline_service

        timeline_service.record_event(
            session,
            scenario_id=ship.id,
            organization_id=ship.organization_id,
            event_type="tariff_change" if not uncertain else "tariff_review_needed",
            summary=summary,
            payload={
                "old_rate": float(old_tariff.rate),
                "new_rate": float(new_tariff.rate),
                "duty_delta": float(duty_delta) if duty_delta is not None else None,
                "uncertain": uncertain,
            },
            impact_id=row.id,
            tariff_rate_id=new_tariff.id,
        )
    return out


def record_impacts_after_approve(session: Session, published_rate_ids: list[str]) -> int:
    """Called after ingest approve; published_rate_ids are newly active verified rates."""
    count = 0
    for rate_id in published_rate_ids:
        new_row = session.get(TariffRate, rate_id)
        if new_row is None:
            continue
        old_row = None
        if new_row.version and new_row.version > 1:
            candidates = session.scalars(
                select(TariffRate).where(
                    TariffRate.hs_code == new_row.hs_code,
                    TariffRate.origin == new_row.origin,
                    TariffRate.destination == new_row.destination,
                    TariffRate.status == "superseded",
                    TariffRate.superseded_by == new_row.id,
                )
            ).all()
            old_row = candidates[0] if candidates else None
        if old_row is None:
            prior = session.scalars(
                select(TariffRate)
                .where(
                    TariffRate.hs_code == new_row.hs_code,
                    TariffRate.origin == new_row.origin,
                    TariffRate.destination == new_row.destination,
                    TariffRate.id != new_row.id,
                )
                .order_by(TariffRate.version.desc())
            ).first()
            old_row = prior
        impacts = record_impacts_for_new_tariff(
            session, new_tariff=new_row, old_tariff=old_row
        )
        count += len(impacts)
    return count
