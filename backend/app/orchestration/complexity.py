"""Rule-based query complexity estimation (Phase 3)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

IntentName = Literal[
    "tariff_lookup",
    "landed_cost",
    "checklist",
    "fta_check",
    "regulation_retrieve",
]

ComplexityLabel = Literal["simple", "moderate", "complex"]

HS_RE = re.compile(r"\b(\d{4}\.\d{2}|\d{6,10})\b")


@dataclass(frozen=True)
class ComplexityEstimate:
    score: float
    label: ComplexityLabel
    intents: tuple[IntentName, ...]
    signals: tuple[str, ...]


def _normalize_hs(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if len(digits) >= 6:
        return f"{digits[:4]}.{digits[4:6]}"
    return raw


def detect_intents(query: str) -> list[IntentName]:
    lower = query.lower()
    found: list[IntentName] = []
    if any(k in lower for k in ("fta", "preferential", "agreement", "safta", "rules of origin")):
        found.append("fta_check")
    if any(
        k in lower for k in ("proof of origin", "notification", "regulation", "retrieve", "excerpt")
    ):
        found.append("regulation_retrieve")
    if any(k in lower for k in ("checklist", "document", "certificate", "paperwork")):
        found.append("checklist")
    if any(k in lower for k in ("landed", "calculate", "cost", "tax", "gst", "igst")):
        found.append("landed_cost")
    if any(k in lower for k in ("duty", "tariff", "bcd", "rate", "hs code", "hs ")):
        found.append("tariff_lookup")
    if not found:
        found.append("tariff_lookup")
    # Preserve order, unique
    seen: set[IntentName] = set()
    ordered: list[IntentName] = []
    for intent in found:
        if intent not in seen:
            seen.add(intent)
            ordered.append(intent)
    return ordered


def estimate_complexity(query: str, *, hs_code: str | None = None) -> ComplexityEstimate:
    intents = detect_intents(query)
    lower = query.lower()
    signals: list[str] = [f"intents={len(intents)}"]
    score = 0.15 * max(len(intents) - 1, 0)

    if len(intents) >= 3 or (" and " in lower and len(intents) >= 2):
        score += 0.45
        signals.append("multi_intent")
    if "fta_check" in intents or "regulation_retrieve" in intents:
        score += 0.25
        signals.append("graph_or_retrieval")
    if "landed_cost" in intents:
        score += 0.1
        signals.append("calculation")
    if any(k in lower for k in ("what if", "compare", "versus", "vs ", "fail", "eligible")):
        score += 0.2
        signals.append("conditional_reasoning")

    has_hs = bool(hs_code) or bool(HS_RE.search(query))
    if not has_hs and intents[0] in {"tariff_lookup", "landed_cost", "fta_check"}:
        score += 0.15
        signals.append("missing_hs")

    score = min(score, 1.0)
    if score < 0.35:
        label: ComplexityLabel = "simple"
    elif score < 0.65:
        label = "moderate"
    else:
        label = "complex"
    return ComplexityEstimate(
        score=round(score, 3),
        label=label,
        intents=tuple(intents),
        signals=tuple(signals),
    )


def extract_hs(query: str, fallback: str | None = None) -> str | None:
    match = HS_RE.search(query)
    if match:
        return _normalize_hs(match.group(1))
    return fallback
