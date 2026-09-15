"""Helpers for tariff data_quality badges (illustrative / demo_verified / source_verified)."""

from __future__ import annotations

VERIFIED_QUALITIES = frozenset({"demo_verified", "source_verified"})


def is_verified_quality(quality: str | None) -> bool:
    return (quality or "") in VERIFIED_QUALITIES


def normalize_quality(quality: str | None) -> str:
    q = quality or "illustrative"
    if q in VERIFIED_QUALITIES or q == "illustrative":
        return q
    return "illustrative"
