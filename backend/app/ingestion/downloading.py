"""Download / fetch stage."""

from __future__ import annotations

from backend.app.integrations.core.models import DiscoveredItem, SourceResult
from backend.app.integrations.core.registry import get_registry


def download(source_code: str, item: DiscoveredItem | None = None) -> SourceResult:
    provider = get_registry().get(source_code)
    return provider.fetch_result(item)
