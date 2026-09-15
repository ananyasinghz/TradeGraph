"""Tariff connector protocol."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from backend.app.integrations.core.connector import SourceConnector


@runtime_checkable
class TariffConnector(SourceConnector, Protocol):
    def lookup_tariff(
        self,
        hs_code: str,
        origin_country: str,
        destination_country: str,
        as_of_date: str,
    ) -> list[dict[str, Any]]:
        ...
