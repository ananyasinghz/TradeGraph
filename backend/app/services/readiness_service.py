"""Readiness score + explainable evidence statuses (S11 + IF-11f)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.data.models import CalculationSnapshot, DocumentUpload, Shipment
from backend.app.domain.trade import (
    ReadinessEvidenceItem,
    ReadinessFactor,
    ReadinessOut,
    ReadinessStatusChip,
)
from backend.app.services.data_quality import is_verified_quality
from backend.app.services import classification_service, cost_service, fta_service, shipment_service
from backend.app.services.source_selection_service import SourceSelectionService
from backend.app.services.tariff_service import resolve_applicable_tariff


def score_shipment(session: Session, shipment_id: str) -> ReadinessOut:
    row = session.get(Shipment, shipment_id)
    if row is None:
        raise AppError(code="SHIPMENT_NOT_FOUND", message="Shipment not found", status_code=404)
    detail = shipment_service.get_shipment(session, shipment_id)
    factors: list[ReadinessFactor] = []
    missing: list[str] = []

    hs_confirmed = bool(detail.hs_code_working and detail.hs_confirmed_at)
    hs_ok = bool(detail.hs_code_working)
    factors.append(
        ReadinessFactor(
            code="hs",
            label="Working HS confirmed",
            weight=25,
            score=25 if hs_confirmed else (10 if hs_ok else 0),
            detail=detail.hs_code_working or "missing",
        )
    )
    if not hs_ok:
        missing.append("Confirm working HS classification")
    elif not hs_confirmed:
        missing.append("Confirm HS (set hs_confirmed_at)")

    snap = session.scalars(
        select(CalculationSnapshot)
        .where(CalculationSnapshot.shipment_id == shipment_id)
        .order_by(CalculationSnapshot.created_at.desc())
    ).first()
    calc_complete = (
        snap is not None
        and (snap.inputs_json or {}).get("freight") is not None
        and (snap.inputs_json or {}).get("insurance") is not None
    )
    calc_ok = snap is not None or detail.latest_calculation is not None
    factors.append(
        ReadinessFactor(
            code="calculation",
            label="Landed cost calculated",
            weight=20,
            score=20 if calc_complete else (10 if calc_ok else 0),
            detail="complete inputs" if calc_complete else ("present" if calc_ok else "missing"),
        )
    )
    if not calc_ok:
        missing.append("Run estimate or customs calculation")
    elif not calc_complete:
        missing.append("Add freight/insurance and recalculate")

    checklist = detail.checklist
    if checklist is None or not checklist.items:
        factors.append(
            ReadinessFactor(
                code="documents",
                label="Required documents ready",
                weight=30,
                score=0,
                detail="checklist not built",
            )
        )
        missing.append("Build document checklist")
        docs_incomplete = True
        required_ready = []
        required = []
    else:
        required = [i for i in checklist.items if i.required]
        required_ready = [i for i in required if i.status == "ready" or i.done]
        ratio = (len(required_ready) / len(required)) if required else 1.0
        score = round(30 * ratio)
        factors.append(
            ReadinessFactor(
                code="documents",
                label="Required documents ready",
                weight=30,
                score=score,
                detail=f"{len(required_ready)}/{len(required)} required ready",
            )
        )
        docs_incomplete = len(required_ready) < len(required)
        if docs_incomplete:
            missing.append("Complete required document statuses / uploads")

    fta_score = 0
    fta_detail = "not checked"
    fta_needs = False
    fta = None
    if detail.hs_code_working:
        fta = fta_service.check_fta(
            session,
            hs_code=detail.hs_code_working,
            origin=detail.origin,
            destination=detail.destination,
            as_of=detail.as_of_date,
            shipment_id=shipment_id,
        )
        if fta.status == "eligible":
            fta_score = 15
            fta_detail = "eligible (conditions passed)"
        elif fta.status == "needs_evidence":
            fta_score = 5
            fta_detail = "needs_evidence"
            fta_needs = True
            missing.append("Satisfy FTA evidence conditions (e.g. CoO)")
        elif fta.status == "potentially_eligible":
            fta_score = 8
            fta_detail = fta.status
        else:
            fta_detail = fta.status
    factors.append(
        ReadinessFactor(
            code="fta",
            label="FTA condition posture",
            weight=15,
            score=fta_score,
            detail=fta_detail,
        )
    )

    upload_count = (
        session.scalar(
            select(func.count())
            .select_from(DocumentUpload)
            .where(DocumentUpload.shipment_id == shipment_id)
        )
        or 0
    )
    factors.append(
        ReadinessFactor(
            code="uploads",
            label="At least one document uploaded",
            weight=10,
            score=10 if upload_count else 0,
            detail=f"{upload_count} file(s)",
        )
    )
    if not upload_count:
        missing.append("Upload supporting documents")

    # Classification uncertainty
    classification_uncertain = False
    if detail.product_text:
        try:
            cands = classification_service.suggest_candidates(
                session, product_text=detail.product_text, chapter="61", limit=5
            ).candidates
            if len(cands) >= 2 and (cands[0].score - cands[1].score) < 0.05:
                classification_uncertain = True
            if not hs_confirmed:
                classification_uncertain = True
        except AppError:
            classification_uncertain = not hs_confirmed
    else:
        classification_uncertain = True

    source_stale = False
    tariff_illustrative = False
    if detail.hs_code_working:
        try:
            tariff = resolve_applicable_tariff(
                session,
                hs_code=detail.hs_code_working,
                origin=detail.origin,
                destination=detail.destination,
                as_of=detail.as_of_date,
            )
            source_stale = SourceSelectionService().is_source_stale(tariff.source_document)
            tariff_illustrative = not is_verified_quality(tariff.data_quality)
        except AppError:
            tariff_illustrative = True

    customs = cost_service.customs_mode_availability(
        session,
        freight=detail.freight,
        insurance=detail.insurance,
        require_scenario_inputs=True,
    )
    human_review = (
        not customs.customs_mode_available
        or classification_uncertain
        or tariff_illustrative
        or source_stale
    )

    statuses = [
        ReadinessStatusChip(
            code="calculation_ready",
            label="Calculation ready",
            active=calc_complete,
            detail="Snapshot with freight/insurance" if calc_complete else "Incomplete",
        ),
        ReadinessStatusChip(
            code="classification_uncertain",
            label="Classification uncertain",
            active=classification_uncertain,
            detail="Confirm HS or resolve close candidates",
        ),
        ReadinessStatusChip(
            code="fta_unverified",
            label="FTA eligibility unverified",
            active=fta_needs or (fta is not None and fta.status != "eligible"),
            detail=fta_detail,
        ),
        ReadinessStatusChip(
            code="documents_incomplete",
            label="Documents incomplete",
            active=docs_incomplete,
            detail="Checklist gaps",
        ),
        ReadinessStatusChip(
            code="source_stale",
            label="Source stale",
            active=source_stale,
            detail="Refresh / re-approve source",
        ),
        ReadinessStatusChip(
            code="human_review_required",
            label="Needs broker review",
            active=human_review,
            detail="Filing preparation blocked, uncertain HS, or sample tariff",
        ),
    ]

    evidence_checks = [
        ("product_description", "Product description", bool(detail.product_text)),
        ("hs_code_selected", "HS code selected", hs_ok),
        ("verified_hs_classification", "Verified classification", hs_confirmed),
        ("customs_value", "Customs value", detail.invoice_value is not None),
        ("origin_country", "Origin country", bool(detail.origin)),
        (
            "commercial_invoice",
            "Invoice",
            any(
                (i.doc_code == "commercial_invoice" and (i.status == "ready" or i.done))
                for i in (checklist.items if checklist else [])
            )
            or upload_count > 0,
        ),
        (
            "certificate_of_origin",
            "Certificate of origin",
            any(
                (
                    i.doc_code == "certificate_of_origin"
                    and (i.status == "ready" or i.done)
                )
                for i in (checklist.items if checklist else [])
            ),
        ),
        (
            "product_composition",
            "Product composition",
            any(
                (
                    i.doc_code in {"fibre_composition", "composition"}
                    and (i.status == "ready" or i.done)
                )
                for i in (checklist.items if checklist else [])
            ),
        ),
        (
            "manufacturing_process",
            "Manufacturing-process evidence",
            any(
                (
                    "manufactur" in (i.doc_code or "").lower()
                    or "process" in (i.doc_code or "").lower()
                )
                and (i.status == "ready" or i.done)
                for i in (checklist.items if checklist else [])
            ),
        ),
    ]
    complete_items = [
        ReadinessEvidenceItem(code=code, label=label, complete=True)
        for code, label, ok in evidence_checks
        if ok
    ]
    missing_items = [
        ReadinessEvidenceItem(code=code, label=label, complete=False)
        for code, label, ok in evidence_checks
        if not ok
    ]

    total = sum(f.score for f in factors)
    if total < 40 or any(f.code == "hs" and f.score == 0 for f in factors):
        band: str = "blocked"
    elif total < 80:
        band = "partial"
    else:
        band = "ready"

    if band == "blocked":
        overall = "blocked"
    elif human_review or classification_uncertain:
        overall = "review_required"
    elif band == "ready":
        overall = "ready"
    else:
        overall = "partial"

    blocked_reasons: list[str] = []
    if not hs_ok:
        blocked_reasons.append("missing_hs")
    elif not hs_confirmed:
        blocked_reasons.append("hs_unconfirmed")
    if not calc_ok:
        blocked_reasons.append("missing_calculation")
    elif not calc_complete:
        blocked_reasons.append("incomplete_freight_insurance")
    if docs_incomplete:
        blocked_reasons.append("documents_incomplete")
    if not upload_count:
        blocked_reasons.append("missing_uploads")
    if fta_needs:
        blocked_reasons.append("fta_needs_evidence")
    if classification_uncertain:
        blocked_reasons.append("classification_uncertain")
    if source_stale:
        blocked_reasons.append("source_stale")
    if human_review:
        blocked_reasons.append("human_review_required")

    return ReadinessOut(
        score=total,
        band=band,  # type: ignore[arg-type]
        overall_status=overall,  # type: ignore[arg-type]
        calculation_ready=calc_complete,
        classification_uncertain=classification_uncertain,
        fta_unverified=fta_needs or (fta is not None and fta.status != "eligible"),
        documents_incomplete=docs_incomplete,
        source_stale=source_stale,
        human_review_required=human_review,
        factors=factors,
        missing=missing,
        blocked_reasons=blocked_reasons,
        statuses=statuses,
        complete_items=complete_items,
        missing_items=missing_items,
        complete_evidence=[i.code for i in complete_items],
        missing_evidence=[i.code for i in missing_items],
    )
