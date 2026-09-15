"""Regulation connector protocol."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from backend.app.integrations.core.connector import SourceConnector


@runtime_checkable
class RegulationConnector(SourceConnector, Protocol):
    def discover_regulations(self, query: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        ...
