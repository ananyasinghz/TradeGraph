"""Load and validate HS classification gold sets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_GOLD = ROOT / "config" / "trade" / "eval" / "hs_gold_v1.yaml"


def load_hs_gold(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or DEFAULT_GOLD
    raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    items = raw.get("items") or []
    if not isinstance(items, list):
        raise ValueError("hs gold file must contain an items list")
    out: list[dict[str, Any]] = []
    for row in items:
        if not isinstance(row, dict):
            continue
        text = str(row.get("product_text") or "").strip()
        expected = str(row.get("expected_hs") or "").strip()
        if not text or not expected:
            continue
        out.append(
            {
                "product_text": text,
                "expected_hs": expected,
                "notes": str(row.get("notes") or ""),
            }
        )
    return out


def expected_matches(candidate_code: str, expected_hs: str) -> bool:
    """Prefix match: expected 6109 matches 6109.10; exact also OK."""
    cand = candidate_code.replace(".", "").strip()
    exp = expected_hs.replace(".", "").strip()
    if not cand or not exp:
        return False
    return cand.startswith(exp) or exp.startswith(cand)
