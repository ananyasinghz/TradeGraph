"""FTA / preferential eligibility with a deterministic condition engine."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal, cast

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from backend.app.core.config import get_settings
from backend.app.core.errors import AppError
from backend.app.data.models import (
    AgreementEligibility,
    DocumentUpload,
    HsCode,
    Shipment,
    ShipmentChecklist,
    TradeAgreement,
)
from backend.app.domain.trade import (
    FtaCheckResult,
    FtaConditionEvaluation,
    FtaConditionInput,
    TradeAgreementOut,
)
from backend.app.services import coverage_service, graph_service, tariff_service
from backend.app.services.document_service import normalize_checklist_item

StatusLiteral = Literal[
    "eligible",
    "potentially_eligible",
    "ineligible",
    "needs_evidence",
    "not_covered",
    "rule_not_available",
    "unknown",
]

DEFAULT_CONDITIONS: list[dict[str, Any]] = [
    {
        "id": "certificate_of_origin",
        "type": "certificate",
        "doc_code": "certificate_of_origin",
        "label": "Certificate of origin on file",
    },
    {
        "id": "origin_criteria",
        "type": "boolean_claim",
        "field": "origin_criteria_met",
        "label": "Wholly obtained or CTSH claim asserted",
    },
    {
        "id": "min_rvc",
        "type": "min_rvc_pct",
        "threshold": 40,
        "label": "Regional value content meets threshold",
    },
]


def list_agreements(session: Session) -> list[TradeAgreementOut]:
    rows = session.scalars(select(TradeAgreement).order_by(TradeAgreement.id)).all()
    return [
        TradeAgreementOut(
            id=r.id,
            name=r.name,
            status=r.status,
            effective_from=r.effective_from,
            notes=r.notes,
        )
        for r in rows
    ]


def _map_status(raw: str, *, certificate_required: bool) -> StatusLiteral:
    """Honesty mapping: do not claim bare eligible without evidence."""
    if raw == "not_eligible":
        return "ineligible"
    if raw in {"conditional", "eligible"}:
        if certificate_required:
            return "needs_evidence" if raw == "conditional" else "potentially_eligible"
        return "potentially_eligible"
    if raw in {
        "eligible",
        "potentially_eligible",
        "ineligible",
        "needs_evidence",
        "not_covered",
        "rule_not_available",
        "unknown",
    }:
        return cast(StatusLiteral, raw)
    return "unknown"


def _certificate_ready(
    session: Session, *, shipment_id: str | None, doc_code: str | None
) -> bool:
    if not shipment_id or not doc_code:
        return False
    upload = session.scalars(
        select(DocumentUpload).where(
            DocumentUpload.shipment_id == shipment_id,
            DocumentUpload.doc_code == doc_code,
        )
    ).first()
    if upload is not None:
        return True
    checklist = session.scalars(
        select(ShipmentChecklist)
        .where(ShipmentChecklist.shipment_id == shipment_id)
        .order_by(ShipmentChecklist.updated_at.desc())
    ).first()
    if checklist is None:
        return False
    for raw in checklist.items_json or []:
        item = normalize_checklist_item(raw)
        if item.doc_code == doc_code and item.status == "ready":
            return True
    return False


def evaluate_conditions(
    session: Session,
    *,
    rule: AgreementEligibility,
    conditions_input: FtaConditionInput | None,
    shipment_id: str | None,
) -> list[FtaConditionEvaluation]:
    specs = list(rule.conditions_json or []) or [dict(c) for c in DEFAULT_CONDITIONS]
    for i, spec in enumerate(specs):
        if spec.get("type") == "certificate" and rule.certificate_doc_code:
            specs[i] = {**spec, "doc_code": rule.certificate_doc_code}
    results: list[FtaConditionEvaluation] = []
    claimed = conditions_input or FtaConditionInput()
    for spec in specs:
        ctype = str(spec.get("type") or "")
        cid = str(spec.get("id") or ctype)
        label = str(spec.get("label") or cid)
        if ctype == "certificate":
            doc_code = str(spec.get("doc_code") or rule.certificate_doc_code or "")
            ok = _certificate_ready(session, shipment_id=shipment_id, doc_code=doc_code)
            results.append(
                FtaConditionEvaluation(
                    id=cid,
                    type=ctype,
                    label=label,
                    status="passed" if ok else "needs_evidence",
                    detail=(
                        f"{doc_code} upload or checklist ready"
                        if ok
                        else f"Missing verified {doc_code or 'certificate'}"
                    ),
                )
            )
        elif ctype == "boolean_claim":
            field = str(spec.get("field") or "origin_criteria_met")
            value = bool(getattr(claimed, field, False))
            results.append(
                FtaConditionEvaluation(
                    id=cid,
                    type=ctype,
                    label=label,
                    status="passed" if value else "needs_evidence",
                    detail="Claim asserted" if value else "Origin criteria not asserted",
                )
            )
        elif ctype == "min_rvc_pct":
            threshold = Decimal(str(spec.get("threshold") or 40))
            rvc = claimed.rvc_pct
            if rvc is None:
                results.append(
                    FtaConditionEvaluation(
                        id=cid,
                        type=ctype,
                        label=label,
                        status="needs_evidence",
                        detail=f"RVC % not provided (threshold {threshold})",
                    )
                )
            elif Decimal(rvc) >= threshold:
                results.append(
                    FtaConditionEvaluation(
                        id=cid,
                        type=ctype,
                        label=label,
                        status="passed",
                        detail=f"RVC {rvc}% >= {threshold}%",
                    )
                )
            else:
                results.append(
                    FtaConditionEvaluation(
                        id=cid,
                        type=ctype,
                        label=label,
                        status="failed",
                        detail=f"RVC {rvc}% below threshold {threshold}%",
                    )
                )
        else:
            results.append(
                FtaConditionEvaluation(
                    id=cid,
                    type=ctype or "unknown",
                    label=label,
                    status="needs_evidence",
                    detail="Unrecognized condition type",
                )
            )
    return results


def _resolve_status_from_conditions(
    base: StatusLiteral,
    evaluations: list[FtaConditionEvaluation],
) -> StatusLiteral:
    if base == "ineligible":
        return "ineligible"
    if any(e.status == "failed" for e in evaluations):
        return "ineligible"
    if evaluations and all(e.status == "passed" for e in evaluations):
        return "eligible"
    if any(e.status == "needs_evidence" for e in evaluations):
        return "needs_evidence"
    return base


def check_fta(
    session: Session,
    *,
    hs_code: str,
    origin: str,
    destination: str,
    as_of: date,
    agreement_id: str | None = None,
    shipment_id: str | None = None,
    conditions: FtaConditionInput | None = None,
) -> FtaCheckResult:
    settings = get_settings()
    origin_u = origin.upper()
    dest_u = destination.upper()

    if shipment_id:
        shipment = session.get(Shipment, shipment_id)
        if shipment is None:
            raise AppError(
                code="SHIPMENT_NOT_FOUND", message="Shipment not found", status_code=404
            )

    if (
        origin_u != settings.default_origin.upper()
        or dest_u != settings.default_destination.upper()
    ):
        coverage_service.raise_coverage_miss(
            session,
            origin=origin_u,
            destination=dest_u,
            hs_code=hs_code,
            as_of=as_of,
            context="fta",
            settings=settings,
        )

    mfn: Decimal | None = None
    mfn_source: str | None = None
    mfn_tariff_id: str | None = None
    try:
        mfn_row = tariff_service.resolve_applicable_tariff(
            session,
            hs_code=hs_code,
            origin=origin_u,
            destination=dest_u,
            as_of=as_of,
        )
        mfn = Decimal(mfn_row.rate)
        mfn_source = mfn_row.source_document_id
        mfn_tariff_id = mfn_row.id
    except AppError as exc:
        if exc.code == "COVERAGE_MISS" and session.get(HsCode, hs_code) is None:
            raise

    stmt = (
        select(AgreementEligibility)
        .options(joinedload(AgreementEligibility.agreement))
        .where(
            AgreementEligibility.hs_code == hs_code,
            AgreementEligibility.origin == origin_u,
            AgreementEligibility.destination == dest_u,
        )
    )
    if agreement_id:
        stmt = stmt.where(AgreementEligibility.agreement_id == agreement_id)
    rules = session.scalars(stmt).all()

    graph = graph_service.build_trade_graph(session)
    paths = graph_service.fta_path_for_hs(graph, hs_code=hs_code, agreement_id=agreement_id)

    if not rules:
        hs_known = session.get(HsCode, hs_code) is not None
        status: StatusLiteral = "not_covered" if hs_known else "rule_not_available"
        reasons = [
            f"{origin_u} and {dest_u} are in the supported corridor.",
            (
                f"No preferential eligibility rule is available for HS {hs_code}."
                if hs_known
                else f"HS {hs_code} is outside the current HS catalog."
            ),
        ]
        if not hs_known:
            coverage_service.raise_coverage_miss(
                session,
                origin=origin_u,
                destination=dest_u,
                hs_code=hs_code,
                as_of=as_of,
                context="fta",
                settings=settings,
            )
        return FtaCheckResult(
            hs_code=hs_code,
            origin=origin_u,
            destination=dest_u,
            as_of=as_of,
            status=status,
            mfn_rate_pct=mfn,
            preferential_rate_pct=None,
            agreement_id=None,
            agreement_name=None,
            certificate_doc_code=None,
            roo_summary=None,
            graph_path=paths,
            evidence=[
                {
                    "kind": "mfn_tariff",
                    "tariff_rate_id": mfn_tariff_id,
                    "source_document_id": mfn_source,
                }
            ],
            reasons=reasons,
            conditions=[],
            data_quality="illustrative",
            disclaimer=(
                "No preferential eligibility rule found for this HS/corridor in the "
                "current dataset. This is not a legal determination."
            ),
        )

    rule = rules[0]
    cert_required = bool(rule.certificate_doc_code)
    base_status = _map_status(rule.status, certificate_required=cert_required)
    evaluations = evaluate_conditions(
        session, rule=rule, conditions_input=conditions, shipment_id=shipment_id
    )
    status = _resolve_status_from_conditions(base_status, evaluations)

    reasons = [
        f"{origin_u} and {dest_u} are covered by the selected agreement scope in this dataset.",
        f"HS {hs_code} appears in the preferential product list (illustrative).",
    ]
    for evaluation in evaluations:
        reasons.append(f"{evaluation.label}: {evaluation.status} — {evaluation.detail}")
    if status == "eligible":
        reasons.append(
            "All configured FTA conditions passed for this workspace evaluation "
            "(still illustrative / not a licensed determination)."
        )
    elif status == "needs_evidence":
        reasons.append(
            "Preferential treatment remains needs_evidence until required "
            "conditions and documents are complete."
        )

    evidence: list[dict[str, Any]] = [
        {
            "kind": "fta_eligibility",
            "eligibility_id": rule.id,
            "source_document_id": rule.source_document_id,
            "data_quality": rule.data_quality,
        },
        {
            "kind": "mfn_tariff",
            "tariff_rate_id": mfn_tariff_id,
            "source_document_id": mfn_source,
        },
    ]
    return FtaCheckResult(
        hs_code=hs_code,
        origin=origin_u,
        destination=dest_u,
        as_of=as_of,
        status=status,
        mfn_rate_pct=mfn,
        preferential_rate_pct=Decimal(rule.preferential_rate_pct),
        agreement_id=rule.agreement_id,
        agreement_name=rule.agreement.name if rule.agreement else None,
        certificate_doc_code=rule.certificate_doc_code,
        roo_summary=rule.roo_summary,
        graph_path=paths,
        evidence=evidence,
        reasons=reasons,
        conditions=evaluations,
        data_quality=rule.data_quality,
        disclaimer=(
            "Illustrative FTA result for TradeGraph. Preferential claims require verified "
            "rules of origin, documentary evidence, and a licensed determination."
        ),
    )
