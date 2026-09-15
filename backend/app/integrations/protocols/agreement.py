"""Agreement / RoO connector protocol."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from backend.app.integrations.core.connector import SourceConnector


@runtime_checkable
class AgreementConnector(SourceConnector, Protocol):
    def get_rules_of_origin(
        self,
        agreement_code: str,
        hs_code: str,
    ) -> list[dict[str, Any]]:
        ...
