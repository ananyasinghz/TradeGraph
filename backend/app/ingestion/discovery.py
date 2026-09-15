"""Discovery stage — list items from a registered provider."""

from __future__ import annotations

from typing import Any

from backend.app.integrations.core.models import DiscoveredItem
from backend.app.integrations.core.registry import get_registry


def discover(source_code: str, query: dict[str, Any] | None = None) -> list[DiscoveredItem]:
    provider = get_registry().get(source_code)
    return provider.discover(query)
