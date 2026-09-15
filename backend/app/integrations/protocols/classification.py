"""Classification assistance connector protocol."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from backend.app.integrations.core.connector import SourceConnector


@runtime_checkable
class ClassificationConnector(SourceConnector, Protocol):
    def classify_product(self, product_text: str) -> list[dict[str, Any]]:
        ...
