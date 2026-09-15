"""In-process provider registry."""

from __future__ import annotations

from backend.app.integrations.core.connector import SourceConnector
from backend.app.integrations.core.errors import ProviderNotFoundError


class IntegrationRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, SourceConnector] = {}

    def register(self, code: str, provider: SourceConnector) -> None:
        self._providers[code.upper()] = provider

    def get(self, code: str) -> SourceConnector:
        key = code.upper()
        if key not in self._providers:
            raise ProviderNotFoundError(code)
        return self._providers[key]

    def has(self, code: str) -> bool:
        return code.upper() in self._providers

    def codes(self) -> list[str]:
        return sorted(self._providers.keys())

    def clear(self) -> None:
        self._providers.clear()


_REGISTRY: IntegrationRegistry | None = None


def get_registry() -> IntegrationRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = IntegrationRegistry()
        from backend.app.integrations.registry import bootstrap_registry

        bootstrap_registry(_REGISTRY)
    return _REGISTRY


def reset_registry_for_tests() -> None:
    """Clear singleton so tests can re-bootstrap."""
    global _REGISTRY
    if _REGISTRY is not None:
        _REGISTRY.clear()
    _REGISTRY = None
