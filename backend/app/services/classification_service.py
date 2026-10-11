"""HS classification candidate suggestions (FTS + structured priors)."""

from __future__ import annotations

import re
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.errors import AppError
from backend.app.data.models import HsCode, Shipment, ShipmentChecklist
from backend.app.domain.trade import (
    ClassificationCandidate,
    ClassificationCandidatesOut,
    ClassificationConfirmRequest,
    ShipmentOut,
    ShipmentUpdate,
)
from backend.app.services import hs_attribute_service, hs_catalog_service, shipment_service
from backend.app.services.hs_attributes import ProductAttributes, extract_attributes_rules

_STOP = frozenset(
    {
        "a",
        "an",
        "and",
        "or",
        "of",
        "the",
        "for",
        "with",
        "from",
        "to",
        "in",
        "on",
        "other",
        "similar",
        "articles",
        "article",
        "made",
        "percent",
        "100",
    }
)


def _tokens(text: str) -> set[str]:
    parts = re.findall(r"[a-z0-9]+", text.lower())
    return {p for p in parts if len(p) > 2 and p not in _STOP}


def _prior_boost(
    code: str, attrs: ProductAttributes, product_tokens: set[str]
) -> tuple[float, list[str]]:
    del product_tokens  # reserved for future material token checks
    digits = re.sub(r"\D", "", code)
    boost = 0.0
    reasons: list[str] = []
    g = attrs.garment_type
    c = attrs.construction
    if g == "tshirt" and digits.startswith("6109"):
        boost += 0.45
        reasons.append("T-shirt cue -> heading 6109")
    if g == "tshirt" and digits.startswith(("6203", "6204", "6205", "6206")):
        boost -= 0.35
        reasons.append("downrank woven jackets/shirts for T-shirt query")
    if g == "shirt" and digits.startswith("6105"):
        boost += 0.25
        reasons.append("shirt cue -> heading 6105")
    if g == "shirt" and c == "woven" and digits.startswith("6205"):
        boost += 0.3
        reasons.append("woven shirt -> heading 6205")
    if g == "shirt" and digits.startswith(("6203", "6204")):
        boost -= 0.25
        reasons.append("downrank jackets/ensembles for shirt query")
    if g == "blouse" and digits.startswith("6106"):
        boost += 0.25
        reasons.append("blouse cue -> heading 6106")
    if g == "knit_top" and digits.startswith("6110"):
        boost += 0.25
        reasons.append("knit top cue -> heading 6110")
    if g == "trousers":
        if c == "woven" and digits.startswith(("6203", "6204")):
            boost += 0.4
            reasons.append("woven trousers -> chapter 62")
        elif c == "knit" and digits.startswith(("6103", "6104")):
            boost += 0.4
            reasons.append("knit trousers -> chapter 61")
        elif digits.startswith(("6203", "6204", "6103", "6104")):
            boost += 0.28
            reasons.append("trousers / pants garment prior")
        if digits.startswith(("6107", "6108", "6207")):
            boost -= 0.35
            reasons.append("downrank underpants/briefs for pants query")
    if g == "fastener" and digits.startswith("7318"):
        boost += 0.4
        reasons.append("screws/bolts -> 7318")
    if g == "computer" and digits.startswith("8471"):
        boost += 0.4
        reasons.append("computer/laptop -> 8471")
    if g == "phone" and digits.startswith("8517"):
        boost += 0.4
        reasons.append("phone -> 8517")
    if g == "babies" and digits.startswith("6111"):
        boost += 0.4
        reasons.append("babies garments -> 6111")
    if g == "underwear" and digits.startswith(("6108", "6107")):
        boost += 0.35
        reasons.append("underwear/briefs -> 6107/6108")
    if attrs.material == "linen" and digits.startswith(("6203", "6204", "5309", "5311")):
        boost += 0.12
        reasons.append("linen material prior")
    if attrs.material == "cotton":
        boost += 0.05
    if attrs.gender == "women" and digits.startswith(("6104", "6106", "6204")):
        boost += 0.08
        reasons.append("women's heading prior")
    if attrs.gender == "men" and digits.startswith(("6103", "6105", "6203")):
        boost += 0.08
        reasons.append("men's heading prior")
    if g == "trousers" and c is None and digits.startswith(("6203", "6204")):
        boost += 0.12
        reasons.append("trousers default toward woven ch.62")
    return boost, reasons


def _lexical_overlap_score(
    product_tokens: set[str], description: str, *, raw_text: str = ""
) -> tuple[float, list[str]]:
    del raw_text
    desc_tokens = _tokens(description)
    overlap = sorted(product_tokens & desc_tokens)
    if not product_tokens:
        return 0.0, []
    base = len(overlap) / max(len(product_tokens), 1)
    reasons = [f"token overlap: {', '.join(overlap)}"] if overlap else []
    return base, reasons


def _confidence_label(score: float) -> str:
    if score >= 0.55:
        return "strong_match"
    if score >= 0.3:
        return "possible_match"
    return "weak_match"


def suggest_candidates(
    session: Session,
    *,
    product_text: str,
    chapter: str | None = None,
    limit: int = 5,
    attributes: ProductAttributes | None = None,
    allow_ollama: bool = False,
) -> ClassificationCandidatesOut:
    text = (product_text or "").strip()
    if not text:
        raise AppError(
            code="PRODUCT_TEXT_REQUIRED",
            message="Product text is required for classification candidates",
            status_code=400,
        )
    product_tokens = _tokens(text)
    attrs = attributes or hs_attribute_service.extract_product_attributes(
        text, allow_ollama=allow_ollama
    )

    fts_hits = hs_catalog_service.fts_search(session, text, limit=50)
    if not fts_hits:
        alt = text
        if attrs.garment_type == "trousers":
            alt = f"{text} trousers pants"
        elif attrs.garment_type == "tshirt":
            alt = f"{text} t-shirt knitted"
        fts_hits = hs_catalog_service.fts_search(session, alt, limit=50)

    candidate_codes: list[str] = [c for c, _ in fts_hits]
    if not candidate_codes:
        stmt = select(HsCode).order_by(HsCode.code).limit(5000)
        if chapter:
            stmt = select(HsCode).where(HsCode.chapter == chapter).order_by(HsCode.code)
        candidate_codes = [r.code for r in session.scalars(stmt).all()]

    fts_rank = {code: rank for code, rank in fts_hits}
    ranked: list[tuple[float, ClassificationCandidate]] = []
    for code in candidate_codes:
        row = session.get(HsCode, code)
        if row is None:
            continue
        if chapter and row.chapter != chapter:
            continue
        lex, lex_reasons = _lexical_overlap_score(
            product_tokens, row.description, raw_text=text
        )
        prior, prior_reasons = _prior_boost(code, attrs, product_tokens)
        fts_contrib = 0.0
        if code in fts_rank:
            fts_contrib = max(0.0, min(0.35, 0.35 / (1.0 + abs(fts_rank[code]))))
            lex_reasons = [f"FTS hit (bm25={fts_rank[code]:.3f})", *lex_reasons]
        raw_score = lex + prior + fts_contrib
        if raw_score <= 0:
            continue
        reasons = [*lex_reasons, *prior_reasons]
        if attrs.construction:
            reasons.append(f"construction={attrs.construction}")
        if attrs.material:
            reasons.append(f"material={attrs.material}")
        ranked.append(
            (
                raw_score,
                ClassificationCandidate(
                    hs_code=row.code,
                    description=row.description,
                    chapter=row.chapter,
                    score=round(min(raw_score, 0.99), 4),
                    reasons=reasons,
                    confidence_label=_confidence_label(raw_score),
                ),
            )
        )
    ranked.sort(key=lambda pair: (-pair[0], pair[1].hs_code))
    top = [c for _, c in ranked[: max(1, min(limit, 10))]]
    return ClassificationCandidatesOut(
        product_text=text,
        chapter=chapter or "all",
        candidates=top,
        disclaimer=(
            "Classification candidates are ranked suggestions from the local "
            "HS nomenclature (FTS + rules) — not an official customs determination. "
            "Confirm before duty math."
        ),
    )


def candidates_for_shipment(
    session: Session,
    shipment_id: str,
    *,
    limit: int = 5,
    allow_ollama: bool = False,
) -> ClassificationCandidatesOut:
    row = session.get(Shipment, shipment_id)
    if row is None:
        raise AppError(code="SHIPMENT_NOT_FOUND", message="Shipment not found", status_code=404)
    return suggest_candidates(
        session,
        product_text=row.product_text,
        chapter=None,
        limit=limit,
        allow_ollama=allow_ollama,
    )


def confirm_classification(
    session: Session, shipment_id: str, payload: ClassificationConfirmRequest
) -> ShipmentOut:
    from datetime import UTC, datetime

    effective_hs = (payload.override_hs or payload.hs_code).strip()
    hs = session.get(HsCode, effective_hs)
    if hs is None:
        raise AppError(
            code="HS_NOT_IN_CATALOG",
            message=f"HS code {effective_hs} is not in the local catalog",
            status_code=400,
        )
    if payload.override_hs and not (payload.reason or "").strip():
        raise AppError(
            code="OVERRIDE_REASON_REQUIRED",
            message="Provide a reason when confirming with override_hs",
            status_code=400,
        )
    row = session.get(Shipment, shipment_id)
    if row is None:
        raise AppError(code="SHIPMENT_NOT_FOUND", message="Shipment not found", status_code=404)
    from backend.app.services.shipment_service import _assert_mutable

    _assert_mutable(row, action="confirm classification")
    assumptions = dict(getattr(row, "assumptions_json", None) or {})
    if payload.override_hs:
        assumptions["hs_override"] = {
            "candidate_hs": payload.hs_code,
            "override_hs": effective_hs,
            "reason": (payload.reason or "").strip(),
        }
    elif "hs_override" in assumptions:
        assumptions.pop("hs_override", None)
    shipment_service.update_shipment(
        session,
        shipment_id,
        ShipmentUpdate(hs_code_working=effective_hs, assumptions=assumptions),
    )
    row = session.get(Shipment, shipment_id)
    assert row is not None
    row.hs_confirmed_at = datetime.now(UTC)
    session.flush()
    prior = session.scalars(
        select(ShipmentChecklist)
        .where(ShipmentChecklist.shipment_id == shipment_id)
        .order_by(ShipmentChecklist.updated_at.desc())
    ).first()
    if prior is not None:
        shipment_service.build_shipment_checklist(session, shipment_id)
    from backend.app.services import timeline_service

    timeline_service.record_event(
        session,
        scenario_id=shipment_id,
        organization_id=row.organization_id,
        event_type="hs_change",
        summary=(
            f"HS overridden to {effective_hs}"
            if payload.override_hs
            else f"HS confirmed as {effective_hs}"
        ),
        payload={
            "hs_code": payload.hs_code,
            "override_hs": payload.override_hs,
            "reason": payload.reason,
            "effective_hs": effective_hs,
        },
    )
    return shipment_service.get_shipment(session, shipment_id)


def rank_descriptions(
    product_text: str, descriptions: Iterable[tuple[str, str]]
) -> list[tuple[str, float]]:
    """Test helper: rank (code, description) pairs without DB/FTS."""
    tokens = _tokens(product_text)
    attrs = extract_attributes_rules(product_text)
    out: list[tuple[str, float]] = []
    for code, desc in descriptions:
        lex, _ = _lexical_overlap_score(tokens, desc, raw_text=product_text)
        prior, _ = _prior_boost(code, attrs, tokens)
        out.append((code, lex + prior))
    out.sort(key=lambda x: -x[1])
    return out
