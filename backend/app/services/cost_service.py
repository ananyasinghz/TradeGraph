"""Deterministic landed-cost calculator (never LLM)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.data.models import CalculationSnapshot, TariffRate
from backend.app.domain.trade import (
    CalculationSnapshotOut,
    ComponentProvenanceOut,
    CustomsModeAvailability,
    DutyStackLine,
    DutyStructureOut,
    LandedCostBreakdown,
    LandedCostInput,
)
from backend.app.services.data_quality import is_verified_quality
from backend.app.services.tariff_service import resolve_applicable_tariff

DISCLAIMER = (
    "Illustrative calculation for the TradeGraph prototype only. "
    "Not a legal customs determination. Verify against official sources."
)

TWOPLACES = Decimal("0.01")
CUSTOMS_HINT_NO_RULES = (
    "Customs mode unavailable because no approved tariff rules are published. "
    "Use Estimate mode or approve a source batch first."
)
CUSTOMS_HINT_INCOMPLETE = (
    "Customs mode requires complete freight/insurance inputs and a "
    "verified (demo_verified/source_verified) tariff rule. "
    "Use estimate mode or complete inputs."
)


def _money(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def _component(components: dict[str, object], key: str, default: Decimal) -> Decimal:
    raw = components.get(key, default)
    return Decimal(str(raw))


def approved_tariff_rule_count(session: Session) -> int:
    return int(
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


def illustrative_tariff_rule_count(session: Session) -> int:
    return int(
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


def customs_mode_availability(
    session: Session,
    *,
    freight: Decimal | None = None,
    insurance: Decimal | None = None,
    tariff: TariffRate | None = None,
    require_scenario_inputs: bool = False,
) -> CustomsModeAvailability:
    """Structured customs-mode preflight (IF-11a)."""
    approved = approved_tariff_rule_count(session)

    # Global status: only whether verified rules exist.
    if not require_scenario_inputs and tariff is None and freight is None and insurance is None:
        if approved <= 0:
            return CustomsModeAvailability(
                customs_mode_available=False,
                customs_mode_blockers=["No approved tariff rules are published."],
                customs_mode_hint=CUSTOMS_HINT_NO_RULES,
                approved_tariff_rule_count=approved,
            )
        return CustomsModeAvailability(
            customs_mode_available=True,
            customs_mode_blockers=[],
            customs_mode_hint=(
                "Approved tariff rules are published. Set freight and insurance "
                "on a scenario to run Customs mode."
            ),
            approved_tariff_rule_count=approved,
        )

    blockers: list[str] = []
    if approved <= 0:
        blockers.append("No approved tariff rules are published.")
    if freight is None:
        blockers.append("Freight is missing on this scenario.")
    if insurance is None:
        blockers.append("Insurance is missing on this scenario.")
    if tariff is not None and not is_verified_quality(tariff.data_quality):
        blockers.append("Matched tariff rule is illustrative, not verified.")
    if tariff is not None:
        from backend.app.services.source_selection_service import SourceSelectionService

        if SourceSelectionService().is_source_stale(tariff.source_document):
            blockers.append("Matched tariff source is stale — refresh or re-approve.")

    if approved <= 0:
        hint = CUSTOMS_HINT_NO_RULES
    elif blockers:
        hint = CUSTOMS_HINT_INCOMPLETE
    else:
        hint = "Customs mode available for this scenario."

    return CustomsModeAvailability(
        customs_mode_available=len(blockers) == 0,
        customs_mode_blockers=blockers,
        customs_mode_hint=hint,
        approved_tariff_rule_count=approved,
    )


def _warnings_for_input(payload: LandedCostInput | None, incoterm: str) -> list[str]:
    warnings: list[str] = []
    freight = payload.freight if payload else None
    insurance = payload.insurance if payload else None
    term = incoterm.upper()
    if freight is None or insurance is None:
        if term in {"FOB", "EXW", "FCA", "FAS"}:
            warnings.append(
                "Freight and/or insurance were omitted. Assessable value may be understated "
                f"for {term} shipments — add those costs before relying on this estimate."
            )
        else:
            warnings.append(
                "Freight and insurance were not entered separately. This estimate treats the "
                f"invoice/{term} value as the full assessable base."
            )
    return warnings


def _formula_steps(
    *,
    assessable: Decimal,
    currency: str,
    bcd_pct: Decimal,
    bcd: Decimal,
    aidc_pct: Decimal,
    aidc: Decimal,
    health_pct: Decimal,
    health: Decimal,
    sws_pct: Decimal,
    sws: Decimal,
    igst_pct: Decimal,
    igst: Decimal,
    cc_pct: Decimal,
    cc: Decimal,
    total_duties: Decimal,
    landed: Decimal,
) -> list[str]:
    return [
        f"1. Assessable value (AV) = {assessable} {currency}",
        f"2. BCD = AV x {bcd_pct}% = {bcd} {currency}",
        f"3. Customs AIDC = AV x {aidc_pct}% = {aidc} {currency}",
        f"4. Health CESS = AV x {health_pct}% = {health} {currency}",
        f"5. SWS/SWC = BCD x {sws_pct}% = {sws} {currency}",
        f"6. IGST = (AV + BCD + AIDC + Health + SWS) x {igst_pct}% = {igst} {currency}",
        f"7. Compensation Cess = (AV + BCD + AIDC + Health + SWS) x {cc_pct}% = {cc} {currency}",
        f"8. Total duties/taxes = {total_duties} {currency}",
        f"9. Landed cost = AV + total duties = {landed} {currency}",
    ]


ENGINE_VERSION = "in_duty.v2"


def _inputs_dict(
    payload: LandedCostInput,
    *,
    regime: str | None = None,
    agreement_code: str | None = None,
    tariff: TariffRate | None = None,
    source_checksum: str | None = None,
) -> dict[str, Any]:
    return {
        "hs_code": payload.hs_code,
        "origin": payload.origin,
        "destination": payload.destination,
        "as_of": payload.as_of.isoformat(),
        "invoice_value": str(payload.invoice_value),
        "currency": payload.currency,
        "incoterm": payload.incoterm,
        "freight": str(payload.freight) if payload.freight is not None else None,
        "insurance": str(payload.insurance) if payload.insurance is not None else None,
        "requested_mode": payload.requested_mode,
        "regime": regime,
        "agreement_code": agreement_code,
        "tariff_rule_ids": [tariff.id] if tariff is not None else [],
        "source_document_id": tariff.source_document_id if tariff else None,
        "source_checksum": source_checksum,
        "tariff_version": tariff.version if tariff else None,
        "data_quality": tariff.data_quality if tariff else None,
        "calculation_engine_version": ENGINE_VERSION,
        "selected_exemption_id": payload.selected_exemption_id,
    }


def snapshot_to_out(row: CalculationSnapshot) -> CalculationSnapshotOut:
    return CalculationSnapshotOut(
        id=row.id,
        shipment_id=row.shipment_id,
        calculation_mode=row.calculation_mode,  # type: ignore[arg-type]
        requested_mode=row.requested_mode,  # type: ignore[arg-type]
        title=row.title,
        inputs=dict(row.inputs_json or {}),
        outputs=LandedCostBreakdown.model_validate(row.outputs_json),
        tariff_rate_id=row.tariff_rate_id,
        source_document_id=row.source_document_id,
        calculation_engine_version=getattr(row, "calculation_engine_version", None)
        or ENGINE_VERSION,
        source_checksum=getattr(row, "source_checksum", None),
        tariff_version=getattr(row, "tariff_version", None),
        data_quality=getattr(row, "data_quality", None),
        created_at=row.created_at,
    )


def persist_snapshot(
    session: Session,
    *,
    payload: LandedCostInput,
    breakdown: LandedCostBreakdown,
    tariff: TariffRate | None = None,
) -> CalculationSnapshot:
    from backend.app.data.models import Shipment, SourceDocument

    regime = None
    agreement_code = None
    if payload.shipment_id:
        ship = session.get(Shipment, payload.shipment_id)
        if ship is not None:
            regime = getattr(ship, "regime", None) or "mfn"
            agreement_code = getattr(ship, "agreement_code", None)

    checksum = None
    if tariff is not None:
        doc = session.get(SourceDocument, tariff.source_document_id)
        checksum = doc.checksum if doc else None

    row = CalculationSnapshot(
        shipment_id=payload.shipment_id,
        calculation_mode=breakdown.calculation_mode,
        requested_mode=payload.requested_mode,
        title=breakdown.title,
        inputs_json=_inputs_dict(
            payload,
            regime=regime,
            agreement_code=agreement_code,
            tariff=tariff,
            source_checksum=checksum,
        ),
        outputs_json=breakdown.model_dump(mode="json"),
        tariff_rate_id=breakdown.tariff_rate_id,
        source_document_id=breakdown.source_document_id,
        calculation_engine_version=ENGINE_VERSION,
        source_checksum=checksum,
        tariff_version=tariff.version if tariff else None,
        data_quality=breakdown.data_quality,
        created_at=datetime.now(UTC),
    )
    session.add(row)
    session.flush()
    return row


def get_snapshot(session: Session, snapshot_id: str) -> CalculationSnapshotOut:
    row = session.get(CalculationSnapshot, snapshot_id)
    if row is None:
        raise AppError(
            code="SNAPSHOT_NOT_FOUND",
            message="Calculation snapshot not found",
            status_code=404,
        )
    return snapshot_to_out(row)


def list_snapshots_for_scenario(
    session: Session, scenario_id: str
) -> list[CalculationSnapshotOut]:
    snaps = session.scalars(
        select(CalculationSnapshot)
        .where(CalculationSnapshot.shipment_id == scenario_id)
        .order_by(CalculationSnapshot.created_at.desc())
    ).all()
    return [snapshot_to_out(s) for s in snaps]


def diff_snapshots(
    session: Session, left_id: str, right_id: str
) -> Any:
    from backend.app.domain.trade import SnapshotDiffOut

    left = get_snapshot(session, left_id)
    right = get_snapshot(session, right_id)
    fields: dict[str, dict[str, Any]] = {}
    compare = {
        "landed_cost": (left.outputs.landed_cost, right.outputs.landed_cost),
        "total_duties_taxes": (
            left.outputs.total_duties_taxes,
            right.outputs.total_duties_taxes,
        ),
        "bcd_rate_pct": (left.outputs.bcd_rate_pct, right.outputs.bcd_rate_pct),
        "assessable_value": (left.outputs.assessable_value, right.outputs.assessable_value),
        "data_quality": (left.data_quality, right.data_quality),
        "tariff_rate_id": (left.tariff_rate_id, right.tariff_rate_id),
        "freight": (left.inputs.get("freight"), right.inputs.get("freight")),
        "insurance": (left.inputs.get("insurance"), right.inputs.get("insurance")),
        "calculation_mode": (left.calculation_mode, right.calculation_mode),
        "engine": (
            left.calculation_engine_version,
            right.calculation_engine_version,
        ),
    }
    for key, (a, b) in compare.items():
        if str(a) != str(b):
            fields[key] = {"left": a, "right": b}
    summary = (
        f"{len(fields)} field(s) differ between {left_id[:8]}… and {right_id[:8]}…"
        if fields
        else "Snapshots are identical on compared fields."
    )
    return SnapshotDiffOut(
        left_id=left_id, right_id=right_id, fields=fields, summary=summary
    )


def _mfn_rates_from_tariff(tariff: TariffRate) -> dict[str, Decimal]:
    from backend.app.services.component_provenance import flatten_rates

    flat = flatten_rates(
        dict(tariff.duty_components or {}),
        fallback_bcd=float(tariff.rate),
    )
    return {k: Decimal(str(v)) for k, v in flat.items()}


def _stack_lines(
    results: list[Any],
    *,
    mfn_rates: dict[str, Decimal],
    notification_labels: dict[str, str] | None = None,
    components: dict[str, Any] | None = None,
) -> list[DutyStackLine]:
    from backend.app.services.component_provenance import extract_provenance

    labels = notification_labels or {}
    rate_key = {
        "BCD": "bcd_pct",
        "AIDC": "aidc_pct",
        "CHCESS": "health_cess_pct",
        "SWS": "sws_pct_of_bcd",
        "IGST": "igst_pct",
        "CC": "compensation_cess_pct",
    }
    prov = extract_provenance(components)
    lines: list[DutyStackLine] = []
    for r in results:
        key = rate_key.get(r.code, "")
        tariff_pct = mfn_rates.get(key, r.rate)
        block = prov.get(key) or {}
        lines.append(
            DutyStackLine(
                code=r.code,
                display_name=r.display_name,
                tariff_rate_pct=Decimal(str(tariff_pct)),
                effective_rate_pct=Decimal(str(r.rate)),
                amount=r.amount,
                notification_sl=labels.get(r.code) or r.notification_sl,
                component_key=key or None,
                data_quality=str(block.get("data_quality") or None),
                source_key=block.get("source_key"),
                source_document_id=block.get("source_document_id"),
                provenance_notes=block.get("notes"),
            )
        )
    return lines


def calculate_from_tariff(
    invoice_value: Decimal,
    currency: str,
    tariff: TariffRate,
    *,
    incoterm: str = "CIF",
    payload: LandedCostInput | None = None,
    session: Session | None = None,
) -> LandedCostBreakdown:
    from backend.app.calculation.duty_components import calculate_india_import
    from backend.app.services import exemption_service

    mfn_rates = _mfn_rates_from_tariff(tariff)
    effective_rates = dict(mfn_rates)
    exemption_rule_id: str | None = None
    exemption_label: str | None = None
    notification_labels: dict[str, str] = {}

    selected_id = payload.selected_exemption_id if payload else None
    if selected_id and session is not None:
        rule = exemption_service.get_exemption_rule(session, selected_id)
        effective_rates = exemption_service.apply_effect_to_rates(
            mfn_rates, dict(rule.effect_json or {})
        )
        exemption_rule_id = rule.id
        exemption_label = exemption_service.notification_label(rule)
        notification_labels["BCD"] = exemption_label

    bcd_pct = effective_rates["bcd_pct"]
    sws_pct = effective_rates["sws_pct_of_bcd"]
    igst_pct = effective_rates["igst_pct"]
    aidc_pct = effective_rates["aidc_pct"]
    health_pct = effective_rates["health_cess_pct"]
    cc_pct = effective_rates["compensation_cess_pct"]

    freight = payload.freight if payload and payload.freight is not None else Decimal("0")
    insurance = payload.insurance if payload and payload.insurance is not None else Decimal("0")
    assessable = _money(invoice_value + freight + insurance)

    duty_stack: list[DutyStackLine] = []
    if tariff.destination.upper() == "IN":
        results, total_duties, landed = calculate_india_import(
            assessable_value=assessable,
            currency=currency.upper(),
            bcd_pct=bcd_pct,
            sws_pct_of_bcd=sws_pct,
            igst_pct=igst_pct,
            aidc_pct=aidc_pct,
            health_cess_pct=health_pct,
            compensation_cess_pct=cc_pct,
            notification_labels=notification_labels or None,
        )
        by_code = {r.code: r for r in results}
        bcd = by_code["BCD"].amount
        sws = by_code["SWS"].amount
        igst = by_code["IGST"].amount
        aidc = by_code["AIDC"].amount
        health = by_code["CHCESS"].amount
        cc = by_code["CC"].amount
        duty_stack = _stack_lines(
            results,
            mfn_rates=mfn_rates,
            notification_labels=notification_labels,
            components=dict(tariff.duty_components or {}),
        )
        mfn_results, mfn_total, _ = calculate_india_import(
            assessable_value=assessable,
            currency=currency.upper(),
            bcd_pct=mfn_rates["bcd_pct"],
            sws_pct_of_bcd=mfn_rates["sws_pct_of_bcd"],
            igst_pct=mfn_rates["igst_pct"],
            aidc_pct=mfn_rates["aidc_pct"],
            health_cess_pct=mfn_rates["health_cess_pct"],
            compensation_cess_pct=mfn_rates["compensation_cess_pct"],
        )
        del mfn_results
        mfn_total_duties = mfn_total
        duty_savings = _money(mfn_total_duties - total_duties)
    else:
        bcd = _money(assessable * bcd_pct / Decimal("100"))
        aidc = _money(assessable * aidc_pct / Decimal("100"))
        health = _money(assessable * health_pct / Decimal("100"))
        sws = _money(bcd * sws_pct / Decimal("100"))
        igst = _money((assessable + bcd + aidc + health + sws) * igst_pct / Decimal("100"))
        cc = _money((assessable + bcd + aidc + health + sws) * cc_pct / Decimal("100"))
        total_duties = _money(bcd + aidc + health + sws + igst + cc)
        landed = _money(assessable + total_duties)
        mfn_total_duties = total_duties
        duty_savings = Decimal("0.00")

    warnings = _warnings_for_input(payload, incoterm)
    incomplete = bool(warnings) or not is_verified_quality(tariff.data_quality)
    assumptions: list[str] = []
    if payload is None or payload.freight is None:
        assumptions.append("Freight not entered separately (treated as 0 add-on).")
    if payload is None or payload.insurance is None:
        assumptions.append("Insurance not entered separately (treated as 0 add-on).")
    assumptions.append(f"Incoterm treated as {incoterm.upper()} for assessable base.")
    if tariff.destination.upper() == "IN":
        assumptions.append(
            "Duty components via IN engine (BCD / AIDC / Health CESS / SWS / IGST / CC)."
        )
    if exemption_label:
        assumptions.append(f"Exemption applied: {exemption_label}.")
    if tariff.data_quality == "illustrative":
        assumptions.append("Tariff rule is illustrative / demonstration data.")

    avail: CustomsModeAvailability | None = None
    if session is not None:
        avail = customs_mode_availability(
            session,
            freight=payload.freight if payload else None,
            insurance=payload.insurance if payload else None,
            tariff=tariff,
            require_scenario_inputs=True,
        )

    requested = payload.requested_mode if payload else None
    if requested == "customs" and incomplete:
        blockers = list(avail.customs_mode_blockers) if avail else []
        if not blockers:
            if not is_verified_quality(tariff.data_quality):
                blockers.append("Matched tariff rule is illustrative, not verified.")
            if payload is None or payload.freight is None:
                blockers.append("Freight is missing on this scenario.")
            if payload is None or payload.insurance is None:
                blockers.append("Insurance is missing on this scenario.")
        raise AppError(
            code="CUSTOMS_MODE_UNAVAILABLE",
            message=(
                avail.customs_mode_hint
                if avail and avail.customs_mode_hint
                else CUSTOMS_HINT_INCOMPLETE
            ),
            status_code=400,
            details={
                "customs_mode_available": False,
                "customs_mode_blockers": blockers,
                "data_quality": tariff.data_quality,
                "warnings": warnings,
                "requested_mode": requested,
            },
        )
    if requested == "estimate" or incomplete:
        title = "Estimated landed cost"
        mode = "estimate"
    else:
        title = "Landed cost (curated inputs)"
        mode = "customs"
    if requested == "customs":
        assumptions.append("Requested calculation mode: customs (curated inputs).")
    elif requested == "estimate":
        assumptions.append("Requested calculation mode: estimate.")

    return LandedCostBreakdown(
        assessable_value=assessable,
        bcd=bcd,
        sws=sws,
        igst=igst,
        aidc=aidc,
        health_cess=health,
        compensation_cess=cc,
        total_duties_taxes=total_duties,
        landed_cost=landed,
        currency=currency.upper(),
        bcd_rate_pct=bcd_pct,
        sws_pct_of_bcd=sws_pct,
        igst_rate_pct=igst_pct,
        aidc_rate_pct=aidc_pct,
        health_cess_rate_pct=health_pct,
        compensation_cess_rate_pct=cc_pct,
        tariff_rate_id=tariff.id,
        data_quality=tariff.data_quality,
        source_document_id=tariff.source_document_id,
        effective_from=tariff.effective_from,
        effective_to=tariff.effective_to,
        disclaimer=DISCLAIMER,
        formula_steps=_formula_steps(
            assessable=assessable,
            currency=currency.upper(),
            bcd_pct=bcd_pct,
            bcd=bcd,
            aidc_pct=aidc_pct,
            aidc=aidc,
            health_pct=health_pct,
            health=health,
            sws_pct=sws_pct,
            sws=sws,
            igst_pct=igst_pct,
            igst=igst,
            cc_pct=cc_pct,
            cc=cc,
            total_duties=total_duties,
            landed=landed,
        ),
        warnings=warnings,
        calculation_mode=mode,  # type: ignore[arg-type]
        title=title,
        assumptions=assumptions,
        customs_mode_available=avail.customs_mode_available if avail else None,
        customs_mode_blockers=list(avail.customs_mode_blockers) if avail else [],
        duty_stack=duty_stack,
        exemption_rule_id=exemption_rule_id,
        exemption_label=exemption_label,
        mfn_total_duties=mfn_total_duties,
        duty_savings=duty_savings,
    )


def build_duty_structure(
    session: Session,
    *,
    hs_code: str,
    origin: str,
    destination: str,
    as_of: Any,
    assessable_value: Decimal,
    currency: str = "INR",
    selected_exemption_id: str | None = None,
    shipment_id: str | None = None,
) -> DutyStructureOut:
    """ICEGATE-style duty stack + ranked exemption Sl. Nos. for a confirmed HS."""
    from backend.app.services import exemption_service

    tariff = resolve_applicable_tariff(
        session,
        hs_code=hs_code,
        origin=origin,
        destination=destination,
        as_of=as_of,
    )
    payload = LandedCostInput(
        hs_code=hs_code,
        origin=origin,
        destination=destination,
        as_of=as_of,
        invoice_value=assessable_value,
        currency=currency,
        incoterm="CIF",
        freight=Decimal("0"),
        insurance=Decimal("0"),
        requested_mode="estimate",
        shipment_id=shipment_id,
        persist_snapshot=False,
        selected_exemption_id=selected_exemption_id,
    )
    breakdown = calculate_from_tariff(
        assessable_value,
        currency,
        tariff,
        incoterm="CIF",
        payload=payload,
        session=session,
    )
    exemptions = exemption_service.list_applicable_exemptions(
        session,
        hs_code=hs_code,
        origin=origin,
        destination=destination,
        as_of=as_of,
        shipment_id=shipment_id,
    )
    from backend.app.services.component_provenance import (
        COMPONENT_KEYS,
        coverage_flags,
        extract_provenance,
    )

    components = dict(tariff.duty_components or {})
    prov = extract_provenance(components)
    component_sources = [
        ComponentProvenanceOut(
            component_key=key,
            value=(
                Decimal(str(block["value"]))
                if block.get("value") is not None
                else None
            ),
            data_quality=str(block.get("data_quality") or "missing"),
            source_key=block.get("source_key"),
            source_document_id=block.get("source_document_id"),
            effective_from=(
                date.fromisoformat(str(block["effective_from"]))
                if block.get("effective_from")
                else None
            ),
            notes=block.get("notes"),
        )
        for key in COMPONENT_KEYS
        for block in [prov.get(key) or {}]
    ]
    preferential_status = None
    preferential_blocked_reason = None
    if shipment_id:
        from backend.app.services import fta_service

        fta = fta_service.check_fta(
            session,
            hs_code=hs_code,
            origin=origin,
            destination=destination,
            as_of=as_of,
            shipment_id=shipment_id,
        )
        preferential_status = fta.status
        if fta.status != "eligible":
            preferential_blocked_reason = (
                "MFN only — preference not claimed/proven "
                f"(FTA status={fta.status})."
            )
    return DutyStructureOut(
        hs_code=hs_code,
        origin=origin.upper(),
        destination=destination.upper(),
        as_of=as_of,
        assessable_value=breakdown.assessable_value,
        currency=breakdown.currency,
        tariff_rate_id=breakdown.tariff_rate_id,
        data_quality=breakdown.data_quality,
        stack=list(breakdown.duty_stack),
        component_sources=component_sources,
        coverage=coverage_flags(components),
        total_duties=breakdown.total_duties_taxes,
        landed_cost=breakdown.landed_cost,
        mfn_total_duties=breakdown.mfn_total_duties or breakdown.total_duties_taxes,
        duty_savings=breakdown.duty_savings or Decimal("0"),
        selected_exemption_id=breakdown.exemption_rule_id,
        selected_exemption_label=breakdown.exemption_label,
        exemptions=exemptions,
        preferential_status=preferential_status,
        preferential_blocked_reason=preferential_blocked_reason,
    )


def calculate(session: Session, payload: LandedCostInput) -> LandedCostBreakdown:
    tariff = resolve_applicable_tariff(
        session,
        hs_code=payload.hs_code,
        origin=payload.origin,
        destination=payload.destination,
        as_of=payload.as_of,
    )
    breakdown = calculate_from_tariff(
        payload.invoice_value,
        payload.currency,
        tariff,
        incoterm=payload.incoterm,
        payload=payload,
        session=session,
    )
    if payload.persist_snapshot:
        snap = persist_snapshot(
            session, payload=payload, breakdown=breakdown, tariff=tariff
        )
        # Attach for Ask / callers without changing response schema
        breakdown_dict = breakdown.model_dump()
        breakdown_dict["calculation_snapshot_id"] = snap.id
        # Keep typed model; stash id on assumptions for discoverability
        if f"calculation_snapshot_id={snap.id}" not in breakdown.assumptions:
            breakdown.assumptions = [
                *breakdown.assumptions,
                f"calculation_snapshot_id={snap.id}",
            ]
    return breakdown
