"""Deterministic exemption / notification Sl. No. eligibility (never LLM)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.data.models import DocumentUpload, ExemptionRule, ShipmentChecklist
from backend.app.domain.trade import ExemptionRuleOut


def _hs_digits(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def _hs_matches(rule_hs: str, query_hs: str) -> bool:
    rd = _hs_digits(rule_hs)
    qd = _hs_digits(query_hs)
    if not rd or not qd:
        return False
    # Exact, or heading / chapter prefix match (e.g. 6109 matches 6109.10).
    return qd.startswith(rd) or rd.startswith(qd)


def _coo_on_file(session: Session, shipment_id: str | None) -> bool:
    if not shipment_id:
        return False
    upload = session.scalar(
        select(DocumentUpload.id)
        .where(
            DocumentUpload.shipment_id == shipment_id,
            DocumentUpload.doc_code == "certificate_of_origin",
        )
        .limit(1)
    )
    if upload:
        return True
    checklist = session.scalar(
        select(ShipmentChecklist).where(ShipmentChecklist.shipment_id == shipment_id)
    )
    if checklist is None:
        return False
    items = list(getattr(checklist, "items_json", None) or [])
    for item in items:
        if not isinstance(item, dict):
            continue
        code = str(item.get("doc_code") or "")
        if code != "certificate_of_origin":
            continue
        if item.get("done") or item.get("status") in {"ready", "draft", "needs_review"}:
            return True
    return False


def _eligibility_for_rule(
    rule: ExemptionRule,
    *,
    origin: str,
    coo_present: bool,
    case_facts: dict[str, Any] | None = None,
) -> tuple[str, str]:
    facts = case_facts or {}
    origin_u = origin.upper()
    rule_origin = (rule.origin or "").upper()
    if rule_origin not in {"ALL", "*", ""} and rule_origin != origin_u:
        return "not_eligible", f"Origin {origin_u} not covered (rule origin={rule_origin})."

    code = (rule.condition_code or "none").lower()
    if code in {"none", "unconditional", ""}:
        return "eligible_now", "No additional condition beyond HS/origin/as-of match."
    if code in {"fta_coo", "coo", "certificate_of_origin"}:
        if coo_present or bool(facts.get("coo_on_file")):
            return "eligible_now", "Certificate of origin is on file for this case."
        return (
            "eligible_if_coo",
            "Eligible once a Certificate of Origin is uploaded / marked ready.",
        )
    if code in {"end_use", "enduse"}:
        if facts.get("end_use_declared"):
            return "eligible_now", "End-use condition marked as declared on the case."
        return "not_eligible", "End-use condition not declared on this case."
    return "not_eligible", f"Unsupported condition_code={code}."


def rule_to_out(
    rule: ExemptionRule,
    *,
    eligibility: str,
    eligibility_reason: str,
) -> ExemptionRuleOut:
    return ExemptionRuleOut(
        id=rule.id,
        notification_id=rule.notification_id,
        notification_year=rule.notification_year,
        serial_no=rule.serial_no,
        label=rule.label,
        hs_match=rule.hs_match,
        origin=rule.origin,
        destination=rule.destination,
        condition_code=rule.condition_code,
        condition_detail=rule.condition_detail or "",
        effect=dict(rule.effect_json or {}),
        source_document_id=rule.source_document_id,
        eligibility=eligibility,  # type: ignore[arg-type]
        eligibility_reason=eligibility_reason,
    )


def list_applicable_exemptions(
    session: Session,
    *,
    hs_code: str,
    origin: str,
    destination: str,
    as_of: date,
    shipment_id: str | None = None,
    case_facts: dict[str, Any] | None = None,
) -> list[ExemptionRuleOut]:
    dest = destination.upper()
    origin_u = origin.upper()
    try:
        rows = session.scalars(
            select(ExemptionRule)
            .where(
                ExemptionRule.status == "active",
                ExemptionRule.destination == dest,
                ExemptionRule.effective_from <= as_of,
                or_(ExemptionRule.effective_to.is_(None), ExemptionRule.effective_to >= as_of),
                or_(
                    ExemptionRule.origin == origin_u,
                    ExemptionRule.origin.in_(("ALL", "*")),
                ),
            )
            .order_by(ExemptionRule.notification_id, ExemptionRule.serial_no)
        ).all()
    except Exception:
        # Live DBs that have not migrated/reseeded yet — keep Duty tab usable.
        session.rollback()
        return _demo_exemptions_for_hs(hs_code, origin=origin_u, destination=dest)

    coo = _coo_on_file(session, shipment_id)
    out: list[ExemptionRuleOut] = []
    for rule in rows:
        if not _hs_matches(rule.hs_match, hs_code):
            continue
        eligibility, reason = _eligibility_for_rule(
            rule, origin=origin_u, coo_present=coo, case_facts=case_facts
        )
        out.append(rule_to_out(rule, eligibility=eligibility, eligibility_reason=reason))

    if not out:
        out = _demo_exemptions_for_hs(hs_code, origin=origin_u, destination=dest)

    rank = {"eligible_now": 0, "eligible_if_coo": 1, "not_eligible": 2}
    out.sort(key=lambda r: (rank.get(r.eligibility, 9), r.notification_id, r.serial_no))
    return out


def _demo_exemptions_for_hs(
    hs_code: str, *, origin: str, destination: str
) -> list[ExemptionRuleOut]:
    """Temporary in-memory Sl. Nos. for cotton knit tees until reseed."""
    if destination != "IN":
        return []
    digits = _hs_digits(hs_code)
    if not digits.startswith("6109"):
        return []
    if origin not in {"BD", "ALL"}:
        return []
    return [
        ExemptionRuleOut(
            id="ex_demo_50_2017_sl282_610910",
            notification_id="50/2017-Customs",
            notification_year=2017,
            serial_no="282",
            label="Concessional BCD for knitted cotton T-shirts (illustrative Sl. 282)",
            hs_match="6109.10",
            origin="BD",
            destination="IN",
            condition_code="fta_coo",
            condition_detail="Valid Certificate of Origin required; reduces BCD to 5% and zeroes AIDC.",
            effect={"bcd_pct": 5.0, "aidc_pct": 0.0},
            source_document_id=None,
            eligibility="eligible_if_coo",
            eligibility_reason="Eligible once a Certificate of Origin is uploaded / marked ready.",
        ),
        ExemptionRuleOut(
            id="ex_demo_50_2017_sl280_6109",
            notification_id="50/2017-Customs",
            notification_year=2017,
            serial_no="280",
            label="Heading 6109 concessional BCD with CoO (illustrative Sl. 280)",
            hs_match="6109",
            origin="BD",
            destination="IN",
            condition_code="fta_coo",
            condition_detail="Applies to heading 6109 when CoO is on file; BCD 10%.",
            effect={"bcd_pct": 10.0, "aidc_pct": 0.0},
            source_document_id=None,
            eligibility="eligible_if_coo",
            eligibility_reason="Eligible once a Certificate of Origin is uploaded / marked ready.",
        ),
    ]

def get_exemption_rule(session: Session, rule_id: str) -> ExemptionRule:
    try:
        row = session.get(ExemptionRule, rule_id)
    except Exception:
        session.rollback()
        row = None
    if row is not None and row.status == "active":
        return row
    # Temporary in-memory demo rows for cotton knit tees (6109.x) before reseed.
    demo = next((r for r in _demo_exemptions_for_hs("6109.10", origin="BD", destination="IN") if r.id == rule_id), None)
    if demo is not None:
        return _demo_rule_as_orm(demo)
    raise AppError(
        code="EXEMPTION_NOT_FOUND",
        message="Exemption / notification Sl. No. not found",
        status_code=404,
    )


def _demo_rule_as_orm(demo: ExemptionRuleOut) -> ExemptionRule:
    return ExemptionRule(
        id=demo.id,
        notification_id=demo.notification_id,
        notification_year=demo.notification_year,
        serial_no=demo.serial_no,
        label=demo.label,
        hs_match=demo.hs_match,
        origin=demo.origin,
        destination=demo.destination,
        condition_code=demo.condition_code,
        condition_detail=demo.condition_detail,
        effect_json=dict(demo.effect or {}),
        source_document_id=demo.source_document_id,
        effective_from=date(2026, 1, 1),
        effective_to=None,
        status="active",
        data_quality="illustrative",
    )

def apply_effect_to_rates(
    base_rates: dict[str, Decimal],
    effect: dict[str, Any] | None,
) -> dict[str, Decimal]:
    """Overlay exemption effect keys onto MFN component rates."""
    merged = dict(base_rates)
    if not effect:
        return merged
    key_map = {
        "bcd_pct": "bcd_pct",
        "aidc_pct": "aidc_pct",
        "health_cess_pct": "health_cess_pct",
        "sws_pct_of_bcd": "sws_pct_of_bcd",
        "igst_pct": "igst_pct",
        "compensation_cess_pct": "compensation_cess_pct",
    }
    for raw_key, rate_key in key_map.items():
        if raw_key in effect and effect[raw_key] is not None:
            merged[rate_key] = Decimal(str(effect[raw_key]))
    return merged


def notification_label(rule: ExemptionRule) -> str:
    year = f"/{rule.notification_year}" if rule.notification_year else ""
    return f"{rule.notification_id}{year} Sl. {rule.serial_no}"
