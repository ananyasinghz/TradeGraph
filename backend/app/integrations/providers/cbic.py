"""CBIC document provider — Level 1/2 curated fixtures + optional PDF evidence (IF-6)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.integrations.adapters import http_json, pdf_document
from backend.app.integrations.core.capabilities import Capability
from backend.app.integrations.core.errors import AdapterError
from backend.app.integrations.core.models import (
    DiscoveredItem,
    SourceDefinition,
    SourceResult,
)
from backend.app.integrations.providers.curated_mirror import CuratedMirrorProvider

ROOT = Path(__file__).resolve().parents[4]

CBIC_DEFINITION = SourceDefinition(
    code="IN_CBIC",
    provider="cbic",
    country="IN",
    capabilities=frozenset(
        {
            Capability.TARIFF_DOCUMENTS,
            Capability.TARIFF_LOOKUP,
            Capability.REGULATIONS,
        }
    ),
    supported_formats=frozenset({"json", "pdf"}),
    requires_auth=False,
    access_method="document",
    honesty_label="Official-source-backed CBIC document archive (not a live government API)",
)

CORPUS_JSON = "config/trade/fixtures/cbic/chapter61_bd_in_corpus.v1.json"
SAMPLE_PDF = "config/trade/fixtures/cbic/sample_notification.pdf"
LEGACY_JSON = "config/trade/fixtures/cbic/cbic_notification_2026_q3.json"


class CbicDocumentProvider(CuratedMirrorProvider):
    """
    India CBIC document ingest provider.

    Primary path: curated JSON corpus (20-50 HS). PDF is archived as evidence /
    extracted when the simple TradeGraph PDF writer format is used.
    """

    def __init__(self, *, corpus_path: str = CORPUS_JSON, pdf_path: str = SAMPLE_PDF) -> None:
        super().__init__(
            definition=CBIC_DEFINITION,
            local_path=corpus_path,
            source_url="https://example.invalid/tradegraph/archives/cbic-ch61-corpus-v1",
        )
        self.pdf_path = pdf_path

    def discover(self, query: dict[str, Any] | None = None) -> list[DiscoveredItem]:
        del query
        items = [
            DiscoveredItem(
                item_id="in_cbic_ch61_corpus_v1",
                title="CBIC chapter 61 curated corpus",
                local_path=self.local_path,
                content_type="application/json",
                metadata={"kind": "corpus_json"},
            )
        ]
        pdf = ROOT / self.pdf_path if not Path(self.pdf_path).is_absolute() else Path(self.pdf_path)
        if pdf.is_file():
            items.append(
                DiscoveredItem(
                    item_id="in_cbic_sample_pdf",
                    title="CBIC sample notification PDF",
                    local_path=self.pdf_path,
                    content_type="application/pdf",
                    metadata={"kind": "evidence_pdf"},
                )
            )
        return items

    def extract_pdf_evidence(self) -> str:
        content = http_json.read_local_bytes(self.pdf_path)
        return pdf_document.extract_pdf_text(content)

    def fetch_result(self, item: DiscoveredItem | None = None) -> SourceResult:
        target = item or self.discover()[0]
        if (target.content_type or "").endswith("pdf") or str(target.local_path or "").endswith(
            ".pdf"
        ):
            content = self.fetch(target)
            checksum = hashlib.sha256(content).hexdigest()
            try:
                text = pdf_document.extract_pdf_text(content)
                warnings: list[str] = []
            except AdapterError as exc:
                text = ""
                warnings = [exc.message]
            return SourceResult(
                source_code=self.definition.code,
                source_url=self.source_url,
                retrieved_at=datetime.now(UTC),
                document_id=f"doc_pdf_{checksum[:16]}",
                checksum=checksum,
                records=[],
                archive_path=target.local_path,
                content_type="application/pdf",
                warnings=warnings,
                errors=[],
                raw_metadata={
                    **self.get_metadata(target),
                    "extracted_text_preview": text[:500],
                    "title": target.title,
                    "publisher": "CBIC (illustrative PDF archive)",
                },
            )
        return super().fetch_result(target)


class CbicLegacyQ3Provider(CuratedMirrorProvider):
    """Keeps the Q3 notification fixture available under CBIC_NOTIFICATION_2026_Q3."""

    def __init__(self) -> None:
        super().__init__(
            definition=SourceDefinition(
                code="CBIC_NOTIFICATION_2026_Q3",
                provider="cbic",
                country="IN",
                capabilities=frozenset(
                    {Capability.TARIFF_DOCUMENTS, Capability.TARIFF_LOOKUP, Capability.REGULATIONS}
                ),
                supported_formats=frozenset({"json"}),
                requires_auth=False,
                access_method="document",
                honesty_label="Official-source-backed curated mirror (not a live CBIC API)",
            ),
            local_path=LEGACY_JSON,
        )
