"""Aggregated shipment workspace for V1.1b."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.data.models import Shipment
from backend.app.domain.trade import ScenarioOverviewOut, ShipmentWorkspaceOut, WorkspaceRiskFlag
from backend.app.services.data_quality import is_verified_quality
from backend.app.services import (
    classification_service,
    fta_service,
    shipment_service,
    tariff_service,
)


def get_workspace(session: Session, shipment_id: str) -> ShipmentWorkspaceOut:
    shipment = shipment_service.get_shipment(session, shipment_id)
    row = session.get(Shipment, shipment_id)
    if row is None:
        raise AppError(code="SHIPMENT_NOT_FOUND", message="Shipment not found", status_code=404)

    tariff = None
    fta = None
    risks: list[WorkspaceRiskFlag] = []
    next_actions: list[str] = []

    classification_candidates = []
    try:
        classification_candidates = classification_service.candidates_for_shipment(
            session, shipment_id, limit=5
        ).candidates
    except AppError:
        classification_candidates = []

    if not shipment.hs_code_working:
        risks.append(
            WorkspaceRiskFlag(
                code="hs_missing",
                severity="blocker",
                message="Working HS code is not set — classify the product before duty math.",
            )
        )
        next_actions.append("Review classification candidates and confirm a working HS code.")
    else:
        try:
            tariff = tariff_service.tariff_to_out(
                tariff_service.resolve_applicable_tariff(
                    session,
                    hs_code=shipment.hs_code_working,
                    origin=shipment.origin,
                    destination=shipment.destination,
                    as_of=shipment.as_of_date,
                )
            )
        except AppError:
            risks.append(
                WorkspaceRiskFlag(
                    code="tariff_missing",
                    severity="blocker",
                    message="No tariff rate found for this HS / corridor / as-of date.",
                )
            )
            next_actions.append("Check Tariff Finder for a valid HS and date.")

        try:
            fta = fta_service.check_fta(
                session,
                hs_code=shipment.hs_code_working,
                origin=shipment.origin,
                destination=shipment.destination,
                as_of=shipment.as_of_date,
                shipment_id=shipment_id,
            )
        except AppError:
            fta = None

    calculation = shipment.latest_calculation
    checklist = shipment.checklist

    from backend.app.services import document_service, readiness_service

    uploads = document_service.list_uploads(session, shipment_id)
    readiness = readiness_service.score_shipment(session, shipment_id)

    if calculation is None and shipment.hs_code_working:
        next_actions.append("Run landed-cost calculation for this shipment.")
        risks.append(
            WorkspaceRiskFlag(
                code="calc_missing",
                severity="warn",
                message="Landed cost has not been calculated yet.",
            )
        )

    if checklist is None:
        next_actions.append("Build the document checklist.")
        risks.append(
            WorkspaceRiskFlag(
                code="checklist_missing",
                severity="warn",
                message="Document checklist has not been built yet.",
            )
        )
    else:
        incomplete = [i for i in checklist.items if i.required]
        if incomplete:
            next_actions.append(
                f"Review {len(incomplete)} required document(s) on the checklist."
            )

    if (
        fta is not None
        and fta.status in {"conditional", "eligible", "potentially_eligible", "needs_evidence"}
        and fta.certificate_doc_code
    ):
        risks.append(
            WorkspaceRiskFlag(
                code="coo_needed",
                severity="warn",
                message=(
                    f"Preferential path may need {fta.certificate_doc_code} "
                    f"(status: {fta.status})."
                ),
            )
        )

    if tariff is not None and tariff.data_quality == "illustrative":
        risks.append(
            WorkspaceRiskFlag(
                code="demo_data",
                severity="info",
                message="Tariff is demonstration data — not a live customs determination.",
            )
        )

    if not risks:
        risks.append(
            WorkspaceRiskFlag(
                code="ok",
                severity="info",
                message="No blockers detected. Review sources before relying on results.",
            )
        )

    if not next_actions:
        next_actions.append("Review the shipment summary and export checklist items as needed.")

    summary_parts = [
        f"{shipment.title}: {shipment.origin}→{shipment.destination}",
        f"product “{shipment.product_text}”",
        f"HS {shipment.hs_code_working or 'pending'}",
        f"as of {shipment.as_of_date.isoformat()}",
    ]
    if tariff is not None:
        summary_parts.append(f"MFN-style rate {tariff.rate}% ({tariff.data_quality})")
    if fta is not None and fta.preferential_rate_pct is not None:
        summary_parts.append(
            f"FTA {fta.status} preferential {fta.preferential_rate_pct}%"
        )
    if calculation is not None:
        summary_parts.append(
            f"landed cost {calculation.landed_cost} {calculation.currency}"
        )
    if checklist is not None:
        summary_parts.append(f"checklist {checklist.progress}")

    if readiness.band == "blocked":
        risks.append(
            WorkspaceRiskFlag(
                code="readiness_blocked",
                severity="blocker",
                message=f"Readiness {readiness.score}/100 (blocked).",
            )
        )
    elif readiness.band == "partial":
        risks.append(
            WorkspaceRiskFlag(
                code="readiness_partial",
                severity="warn",
                message=f"Readiness {readiness.score}/100 (partial).",
            )
        )

    from backend.app.services import cost_service

    tariff_row = None
    if shipment.hs_code_working and tariff is not None:
        try:
            tariff_row = tariff_service.resolve_applicable_tariff(
                session,
                hs_code=shipment.hs_code_working,
                origin=shipment.origin,
                destination=shipment.destination,
                as_of=shipment.as_of_date,
            )
        except AppError:
            tariff_row = None
    customs = cost_service.customs_mode_availability(
        session,
        freight=shipment.freight,
        insurance=shipment.insurance,
        tariff=tariff_row,
        require_scenario_inputs=True,
    )
    if not customs.customs_mode_available:
        risks.append(
            WorkspaceRiskFlag(
                code="customs_unavailable",
                severity="info",
                message=customs.customs_mode_hint,
            )
        )

    why: list[str] = []
    if shipment.hs_code_working:
        why.append(
            f"Working HS {shipment.hs_code_working}"
            + (" (confirmed)" if shipment.hs_confirmed_at else " (not yet confirmed)")
        )
    if tariff is not None:
        why.append(
            f"BCD/listed rate {tariff.rate}% from {tariff.source_document_id} "
            f"({tariff.data_quality})"
        )
    if calculation is not None:
        for step in (calculation.formula_steps or [])[:6]:
            why.append(step)
        for assumption in (calculation.assumptions or [])[:4]:
            why.append(f"Assumption: {assumption}")

    status_chips: list[str] = []
    if readiness.calculation_ready:
        status_chips.append("Estimate ready")
    elif calculation is not None:
        status_chips.append("Estimate partial")
    else:
        status_chips.append("Estimate pending")
    if readiness.fta_unverified:
        status_chips.append("FTA unverified")
    elif fta is not None and fta.status == "eligible":
        status_chips.append("FTA eligible")
    if readiness.documents_incomplete:
        status_chips.append("Documents incomplete")
    else:
        status_chips.append("Documents ready")
    if readiness.human_review_required:
        status_chips.append("Needs broker review")
    if readiness.classification_uncertain:
        status_chips.append("Classification uncertain")

    latest_snap = shipment.calculation_snapshots[0] if shipment.calculation_snapshots else None
    decision = {
        "estimated_duty": (
            str(calculation.total_duties_taxes) if calculation else None
        ),
        "landed_cost": str(calculation.landed_cost) if calculation else None,
        "currency": calculation.currency if calculation else shipment.currency,
        "calculation_mode": calculation.calculation_mode if calculation else None,
        "tariff_source": tariff.source_document_id if tariff else None,
        "tariff_rate_pct": float(tariff.rate) if tariff else None,
        "source_date": (
            str(tariff.effective_from) if tariff and tariff.effective_from else None
        ),
        "data_quality": tariff.data_quality if tariff else None,
        "calculation_snapshot_id": latest_snap.id if latest_snap else None,
    }

    from backend.app.services import impact_service

    recent = []
    for impact in impact_service.list_impacts(session, limit=5):
        if impact.shipment_id != shipment_id:
            continue
        recent.append(
            {
                "kind": "tariff_impact",
                "summary": impact.summary,
                "duty_delta": str(impact.duty_delta) if impact.duty_delta is not None else None,
                "created_at": impact.created_at.isoformat(),
                "impact_id": impact.id,
            }
        )

    buttons: list[dict[str, str]] = []
    if not shipment.hs_confirmed_at:
        buttons.append({"id": "verify_hs", "label": "Verify HS", "tab": "classify"})
    if readiness.documents_incomplete or any(
        i.code == "certificate_of_origin" for i in (readiness.missing_items or [])
    ):
        buttons.append({"id": "upload_coo", "label": "Upload CoO", "tab": "docs"})
    buttons.append({"id": "recalculate", "label": "Recalculate", "tab": "cost"})
    if tariff is None or not is_verified_quality(tariff.data_quality):
        buttons.append({"id": "review_source", "label": "Review source", "tab": "tariff"})

    overview = ScenarioOverviewOut(
        status_chips=status_chips,
        trade_summary={
            "origin": shipment.origin,
            "destination": shipment.destination,
            "working_hs": shipment.hs_code_working,
            "regime": "MFN",
            "customs_value": str(shipment.invoice_value),
            "currency": shipment.currency,
            "freight": str(shipment.freight) if shipment.freight is not None else None,
            "insurance": str(shipment.insurance) if shipment.insurance is not None else None,
            "product": shipment.product_text,
            "as_of": shipment.as_of_date.isoformat(),
        },
        decision_result=decision,
        why_this_result=why,
        missing_evidence=[i.label for i in (readiness.missing_items or [])],
        complete_evidence=[i.label for i in (readiness.complete_items or [])],
        recent_changes=recent[:5],
        next_action_buttons=buttons,
    )

    return ShipmentWorkspaceOut(
        shipment=shipment,
        tariff=tariff,
        fta=fta,
        calculation=calculation,
        checklist=checklist,
        classification_candidates=classification_candidates,
        calculation_snapshots=list(shipment.calculation_snapshots),
        readiness=readiness,
        overview=overview,
        uploads=uploads,
        risks=risks,
        next_actions=next_actions,
        summary="; ".join(summary_parts) + ".",
        customs_mode_available=customs.customs_mode_available,
        customs_mode_blockers=list(customs.customs_mode_blockers),
        customs_mode_hint=customs.customs_mode_hint,
        approved_tariff_rule_count=cost_service.approved_tariff_rule_count(session),
        illustrative_tariff_rule_count=cost_service.illustrative_tariff_rule_count(session),
    )
