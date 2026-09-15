"""Integration shared models / contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from backend.app.integrations.core.capabilities import Capability


@dataclass(frozen=True)
class SourceDefinition:
    code: str
    provider: str
    country: str
    capabilities: frozenset[Capability]
    supported_formats: frozenset[str]
    requires_auth: bool = False
    access_method: str = "document"  # manual | document | http | api
    honesty_label: str = "Official-source-backed curated data"


@dataclass
class DiscoveredItem:
    item_id: str
    title: str
    source_url: str | None = None
    local_path: str | None = None
    content_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceResult:
    source_code: str
    source_url: str | None
    retrieved_at: datetime
    document_id: str
    checksum: str
    records: list[dict[str, Any]] = field(default_factory=list)
    archive_path: str | None = None
    content_type: str | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    raw_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedTariffRule:
    hs_code: str
    origin_country: str
    destination_country: str
    regime: str
    duty_rate: Decimal
    effective_from: date
    effective_to: date | None
    source_document_id: str
    source_page: int | None = None
    duty_components: dict[str, Any] = field(default_factory=dict)
    notes: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
