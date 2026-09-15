"""HS classification evaluation against gold set."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.app.services import classification_service
from backend.app.services.hs_gold_service import expected_matches, load_hs_gold


def evaluate_hs_classify(
    session: Session,
    *,
    limit: int = 5,
    min_items_for_threshold: int = 50,
    top3_threshold: float = 0.70,
) -> dict[str, Any]:
    items = load_hs_gold()
    hits_top1 = 0
    hits_top3 = 0
    misses: list[dict[str, Any]] = []
    for row in items:
        result = classification_service.suggest_candidates(
            session,
            product_text=row["product_text"],
            chapter=None,
            limit=limit,
        )
        codes = [c.hs_code for c in result.candidates]
        top1 = bool(codes) and expected_matches(codes[0], row["expected_hs"])
        top3 = any(expected_matches(c, row["expected_hs"]) for c in codes[:3])
        if top1:
            hits_top1 += 1
        if top3:
            hits_top3 += 1
        else:
            misses.append(
                {
                    "product_text": row["product_text"],
                    "expected_hs": row["expected_hs"],
                    "got": codes,
                    "notes": row.get("notes"),
                }
            )
    n = max(len(items), 1)
    top1_recall = hits_top1 / n
    top3_recall = hits_top3 / n
    gate_failed = len(items) >= min_items_for_threshold and top3_recall < top3_threshold
    return {
        "n": len(items),
        "top1_recall": round(top1_recall, 4),
        "top3_recall": round(top3_recall, 4),
        "misses": misses[:25],
        "threshold": top3_threshold,
        "gate_failed": gate_failed,
    }
