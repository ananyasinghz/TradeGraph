"""Generic source connector protocol."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from backend.app.integrations.core.models import DiscoveredItem, SourceDefinition, SourceResult


@runtime_checkable
class SourceConnector(Protocol):
    """Every provider implements discover / fetch / metadata."""

    definition: SourceDefinition

    def discover(self, query: dict[str, Any] | None = None) -> list[DiscoveredItem]:
        ...

    def fetch(self, item: DiscoveredItem) -> bytes:
        ...

    def get_metadata(self, item: DiscoveredItem) -> dict[str, Any]:
        ...

    def fetch_result(self, item: DiscoveredItem | None = None) -> SourceResult:
        """Fetch + checksum + record envelope (optional convenience)."""
        ...
