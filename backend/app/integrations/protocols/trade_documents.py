"""Trade document requirements connector protocol."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from backend.app.integrations.core.connector import SourceConnector


@runtime_checkable
class TradeDocumentsConnector(SourceConnector, Protocol):
    def list_document_requirements(
        self,
        origin_country: str,
        destination_country: str,
        hs_code: str,
    ) -> list[dict[str, Any]]:
        ...
