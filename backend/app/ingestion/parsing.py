"""Parsing stage — records already extracted by provider adapters into SourceResult."""

from __future__ import annotations

from typing import Any

from backend.app.integrations.core.models import SourceResult


def parse(result: SourceResult) -> list[dict[str, Any]]:
    """Return raw records from a SourceResult (provider-owned parse)."""
    return list(result.records)
