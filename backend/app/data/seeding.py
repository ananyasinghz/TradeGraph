"""Load and apply TradeGraph seed catalogs."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.app.data.models import (
    AgreementEligibility,
    AuditLog,
    CalculationSnapshot,
    Corridor,
    Country,
    DatasetRun,
    DocumentRequirement,
    DocumentUpload,
    Evidence,
    FieldMapping,
    HsCode,
    JobRun,
    LineItem,
    Notification,
    Organization,
    Party,
    RegulatoryChunk,
    SourceConnection,
    SourceCoverage,
    SourceDocument,
    TariffRate,
    TradeAgreement,
    UserAccount,
    WatchlistItem,
)


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(value)


def load_catalog(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Seed catalog must be a mapping")
    return payload


def seed(session: Session, catalog: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    fingerprint = str(catalog["fingerprint"])
    existing = session.scalar(select(DatasetRun).where(DatasetRun.fingerprint == fingerprint))
    if existing is not None and not force:
        return {"created": False, "fingerprint": fingerprint, "counts": existing.record_counts}

    if force:
        for model in (
            WatchlistItem,
            Notification,
            JobRun,
            AuditLog,
            RegulatoryChunk,
            AgreementEligibility,
            TradeAgreement,
            CalculationSnapshot,
            Evidence,
            DocumentUpload,
            LineItem,
            TariffRate,
            DocumentRequirement,
            HsCode,
            SourceDocument,
            SourceCoverage,
            SourceConnection,
            FieldMapping,
            Corridor,
            Country,
            UserAccount,
            Organization,
            Party,
            DatasetRun,
        ):
            session.execute(delete(model))

    now = datetime.now(UTC)
    for src in catalog.get("sources", []):
        raw_status = src.get("status", "published")
        status = "published" if raw_status == "active" else raw_status
        session.add(
            SourceDocument(
                id=src["id"],
                title=src["title"],
                publisher=src["publisher"],
                url=src.get("url"),
                retrieved_at=now,
                effective_from=_parse_date(src.get("effective_from")),
                file_path=src.get("archive_path"),
                archive_path=src.get("archive_path"),
                checksum=src.get("checksum")
                or hashlib.sha256(src["id"].encode()).hexdigest()[:16],
                status=status,
                notes=src.get("notes"),
                content_type=src.get("content_type", "text/yaml"),
                source_kind=src.get("source_kind", "curated_dataset"),
                live_claim=False,
                fetched_at=now,
                published_at=now if status == "published" else None,
            )
        )
    session.flush()

    for party in catalog.get("parties", []):
        party_row = Party(
            name=party["name"],
            role=party.get("role", "exporter"),
            country=str(party["country"]).upper() if party.get("country") else None,
            address_text=party.get("address_text"),
            tax_id=party.get("tax_id"),
            notes=party.get("notes"),
            created_at=now,
        )
        if party.get("id"):
            party_row.id = str(party["id"])
        session.add(party_row)
    session.flush()

    for hs in catalog.get("hs_codes", []):
        session.add(
            HsCode(
                code=str(hs["code"]),
                description=hs["description"],
                chapter=str(hs["chapter"]),
                parent_code=hs.get("parent_code"),
            )
        )
    session.flush()

    for rate in catalog.get("tariff_rates", []):
        regime = rate.get("regime") or (
            "preferential" if rate.get("agreement_id") else "mfn"
        )
        row = TariffRate(
            hs_code=str(rate["hs_code"]),
            origin=str(rate["origin"]).upper(),
            destination=str(rate["destination"]).upper(),
            rate=Decimal(str(rate["rate"])),
            rate_type=rate.get("rate_type", "ad_valorem_pct"),
            duty_components=dict(rate.get("duty_components") or {}),
            agreement_id=rate.get("agreement_id"),
            effective_from=_parse_date(rate["effective_from"]) or date.today(),
            effective_to=_parse_date(rate.get("effective_to")),
            source_document_id=rate["source_document_id"],
            version=int(rate.get("version", 1)),
            status=rate.get("status", "active"),
            data_quality=rate.get("data_quality", "illustrative"),
            superseded_by=None,
            regime=regime,
            rule_label=rate.get("rule_label"),
            notes=rate.get("notes"),
        )
        session.add(row)
        session.flush()

    v1 = session.scalar(
        select(TariffRate).where(
            TariffRate.hs_code == "6109.10",
            TariffRate.version == 1,
            TariffRate.origin == "BD",
            TariffRate.destination == "IN",
            TariffRate.agreement_id.is_(None),
        )
    )
    v2 = session.scalar(
        select(TariffRate).where(
            TariffRate.hs_code == "6109.10",
            TariffRate.version == 2,
            TariffRate.origin == "BD",
            TariffRate.destination == "IN",
            TariffRate.agreement_id.is_(None),
        )
    )
    if v1 is not None and v2 is not None:
        v1.superseded_by = v2.id

    for req in catalog.get("document_requirements", []):
        session.add(
            DocumentRequirement(
                origin=str(req["origin"]).upper(),
                destination=str(req["destination"]).upper(),
                hs_code=str(req["hs_code"]) if req.get("hs_code") else None,
                agreement_id=req.get("agreement_id"),
                doc_code=req["doc_code"],
                doc_label=req["doc_label"],
                required=bool(req.get("required", True)),
                notes=req.get("notes"),
            )
        )

    for agr in catalog.get("trade_agreements", []):
        session.add(
            TradeAgreement(
                id=agr["id"],
                name=agr["name"],
                status=agr.get("status", "illustrative"),
                effective_from=_parse_date(agr.get("effective_from")),
                notes=agr.get("notes"),
            )
        )
    session.flush()

    for rule in catalog.get("agreement_eligibility", []):
        session.add(
            AgreementEligibility(
                agreement_id=rule["agreement_id"],
                hs_code=str(rule["hs_code"]),
                origin=str(rule["origin"]).upper(),
                destination=str(rule["destination"]).upper(),
                preferential_rate_pct=Decimal(str(rule["preferential_rate_pct"])),
                status=rule.get("status", "conditional"),
                certificate_doc_code=rule.get("certificate_doc_code"),
                roo_summary=rule.get("roo_summary"),
                source_document_id=rule["source_document_id"],
                data_quality=rule.get("data_quality", "illustrative"),
                conditions_json=list(rule.get("conditions") or []),
            )
        )

    for chunk in catalog.get("regulatory_chunks", []):
        session.add(
            RegulatoryChunk(
                id=chunk["id"],
                source_document_id=chunk["source_document_id"],
                text=str(chunk["text"]).strip(),
                hs_code=str(chunk["hs_code"]) if chunk.get("hs_code") else None,
                tags=list(chunk.get("tags") or []),
            )
        )

    # Seed a default watchlist row so change feed is visible after first load.
    if v2 is not None:
        from backend.app.services.org_service import ensure_demo_org

        org = ensure_demo_org(session)
        session.add(
            WatchlistItem(
                hs_code="6109.10",
                origin="BD",
                destination="IN",
                created_at=now,
                last_seen_rate_id=v2.id,
                organization_id=org.id,
            )
        )

    counts = {
        "sources": len(catalog.get("sources", [])),
        "parties": len(catalog.get("parties", [])),
        "hs_codes": len(catalog.get("hs_codes", [])),
        "tariff_rates": len(catalog.get("tariff_rates", [])),
        "document_requirements": len(catalog.get("document_requirements", [])),
        "trade_agreements": len(catalog.get("trade_agreements", [])),
        "agreement_eligibility": len(catalog.get("agreement_eligibility", [])),
        "regulatory_chunks": len(catalog.get("regulatory_chunks", [])),
        "watchlist_items": 1 if v2 is not None else 0,
    }
    session.add(
        DatasetRun(
            fingerprint=fingerprint,
            record_counts=counts,
            created_at=now,
        )
    )
    from backend.app.services.corridor_service import ensure_default_corridors
    from backend.app.services.source_connection_service import ensure_default_connections

    ensure_default_connections(session)
    ensure_default_corridors(session)
    return {"created": True, "fingerprint": fingerprint, "counts": counts}
