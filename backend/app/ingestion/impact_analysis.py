"""Impact analysis stub — rule diffs feed watchlist jobs later."""

from __future__ import annotations

from typing import Any


def summarize_batch_impact(
    *,
    rates_ok: int,
    rates_error: int,
    chunks_ok: int,
) -> dict[str, Any]:
    return {
        "rates_ok": rates_ok,
        "rates_error": rates_error,
        "chunks_ok": chunks_ok,
        "watchlist_notify_recommended": rates_ok > 0,
    }
