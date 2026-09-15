"""Curated JSON mirror provider — wraps local official-style archives (IF-1)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.integrations.adapters import http_json
from backend.app.integrations.core.capabilities import Capability
from backend.app.integrations.core.errors import AdapterError
from backend.app.integrations.core.models import (
    DiscoveredItem,
    SourceDefinition,
    SourceResult,
)

ROOT = Path(__file__).resolve().parents[4]

DEFAULT_LOCAL = "config/trade/fixtures/cbic/cbic_notification_2026_q3.json"

CURATED_MIRROR_DEFINITION = SourceDefinition(
    code="CURATED_MIRROR_CBIC_Q3",
    provider="curated_mirror",
    country="IN",
    capabilities=frozenset(
        {
            Capability.TARIFF_DOCUMENTS,
            Capability.TARIFF_LOOKUP,
            Capability.REGULATIONS,
        }
    ),
    supported_formats=frozenset({"json"}),
    requires_auth=False,
    access_method="document",
    honesty_label="Official-source-backed curated mirror (not a live CBIC API)",
)


class CuratedMirrorProvider:
    """
    Level-1/2 document provider: reads a curated local JSON archive.

    Product services must not import this class directly — use IntegrationRegistry.
    """

    def __init__(
        self,
        *,
        definition: SourceDefinition | None = None,
        local_path: str = DEFAULT_LOCAL,
        source_url: str | None = None,
    ) -> None:
        self.definition = definition or CURATED_MIRROR_DEFINITION
        self.local_path = local_path
        self.source_url = source_url

    def discover(self, query: dict[str, Any] | None = None) -> list[DiscoveredItem]:
        del query
        return [
            DiscoveredItem(
                item_id=self.definition.code,
                title=self.definition.code,
                source_url=self.source_url,
                local_path=self.local_path,
                content_type="application/json",
                metadata={"access_method": self.definition.access_method},
            )
        ]

    def fetch(self, item: DiscoveredItem) -> bytes:
        path = item.local_path or self.local_path
        if path:
            return http_json.read_local_bytes(path)
        if item.source_url or self.source_url:
            content, _ = http_json.http_get_bytes(item.source_url or self.source_url or "")
            return content
        raise AdapterError("Curated mirror requires local_path or source_url")

    def get_metadata(self, item: DiscoveredItem) -> dict[str, Any]:
        return {
            "source_code": self.definition.code,
            "provider": self.definition.provider,
            "country": self.definition.country,
            "capabilities": sorted(c.value for c in self.definition.capabilities),
            "item_id": item.item_id,
            "local_path": item.local_path or self.local_path,
            "source_url": item.source_url or self.source_url,
            "honesty_label": self.definition.honesty_label,
        }

    def lookup_tariff(
        self,
        hs_code: str,
        origin_country: str,
        destination_country: str,
        as_of_date: str,
    ) -> list[dict[str, Any]]:
        del as_of_date
        result = self.fetch_result()
        rates = []
        for record in result.records:
            if record.get("_kind") != "tariff_rate":
                continue
            if str(record.get("hs_code")) != hs_code:
                continue
            if str(record.get("origin", "")).upper() != origin_country.upper():
                continue
            if str(record.get("destination", "")).upper() != destination_country.upper():
                continue
            rates.append(record)
        return rates

    def fetch_result(self, item: DiscoveredItem | None = None) -> SourceResult:
        discovered = item or self.discover()[0]
        content = self.fetch(discovered)
        checksum = hashlib.sha256(content).hexdigest()
        payload = http_json.parse_json_bytes(content)
        if not isinstance(payload, dict):
            raise AdapterError("Curated mirror JSON must be an object", code="JSON_SHAPE_ERROR")

        records: list[dict[str, Any]] = []
        for rate in payload.get("rates") or []:
            row = dict(rate)
            row["_kind"] = "tariff_rate"
            records.append(row)
        for chunk in payload.get("chunks") or []:
            row = dict(chunk)
            row["_kind"] = "regulatory_chunk"
            records.append(row)

        rel = discovered.local_path or self.local_path
        try:
            if rel:
                abs_path = Path(rel) if Path(rel).is_absolute() else ROOT / rel
                rel = str(abs_path.relative_to(ROOT)).replace("\\", "/")
        except ValueError:
            rel = str(rel).replace("\\", "/") if rel else None

        return SourceResult(
            source_code=self.definition.code,
            source_url=discovered.source_url or self.source_url,
            retrieved_at=datetime.now(UTC),
            document_id=f"doc_{checksum[:16]}",
            checksum=checksum,
            records=records,
            archive_path=rel,
            content_type="application/json",
            warnings=[],
            errors=[],
            raw_metadata={
                **self.get_metadata(discovered),
                "title": payload.get("title"),
                "publisher": payload.get("publisher"),
                "effective_from": payload.get("effective_from"),
                "notice_id": payload.get("notice_id"),
                "parsed": True,
                "payload_keys": sorted(payload.keys()),
            },
        )

    def discover_regulations(self, query: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        del query
        result = self.fetch_result()
        return [r for r in result.records if r.get("_kind") == "regulatory_chunk"]
