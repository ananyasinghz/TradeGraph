"""SQLAlchemy ORM models for TradeGraph (Phase 1 + R2 entities)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


def _uuid() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    """Declarative base for trade schema."""


class DatasetRun(Base):
    __tablename__ = "dataset_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    fingerprint: Mapped[str] = mapped_column(String(128), unique=True)
    record_counts: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Party(Base):
    """Exporter / importer / consignee / manufacturer party."""

    __tablename__ = "parties"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(32), index=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    address_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(512))
    publisher: Mapped[str] = mapped_column(String(256))
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Lifecycle: unverified|fetched|parsed|validation_failed|awaiting_review|
    # approved|published|superseded|rejected|expired (legacy "active" = published)
    status: Mapped[str] = mapped_column(String(32), default="unverified", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    archive_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_kind: Mapped[str] = mapped_column(String(64), default="curated_dataset")
    live_claim: Mapped[bool] = mapped_column(Boolean, default=False)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    tariff_rates: Mapped[list[TariffRate]] = relationship(back_populates="source_document")


class HsCode(Base):
    __tablename__ = "hs_codes"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    description: Mapped[str] = mapped_column(Text)
    chapter: Mapped[str] = mapped_column(String(4), index=True)
    parent_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    source_pack: Mapped[str | None] = mapped_column(String(128), nullable=True)
    heading: Mapped[str | None] = mapped_column(String(8), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tariff_rates: Mapped[list[TariffRate]] = relationship(back_populates="hs")
    synonyms: Mapped[list["HsSynonym"]] = relationship(back_populates="hs")


class HsSynonym(Base):
    __tablename__ = "hs_synonyms"
    __table_args__ = (UniqueConstraint("hs_code", "term", name="uq_hs_synonym_code_term"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    hs_code: Mapped[str] = mapped_column(ForeignKey("hs_codes.code"), index=True)
    term: Mapped[str] = mapped_column(String(128), index=True)
    weight: Mapped[float] = mapped_column(Numeric(8, 4), default=1.0)

    hs: Mapped[HsCode] = relationship(back_populates="synonyms")


class TariffRate(Base):
    """Tariff rule row (product name TariffRule in the usability plan)."""

    __tablename__ = "tariff_rates"
    __table_args__ = (
        UniqueConstraint(
            "hs_code",
            "origin",
            "destination",
            "version",
            name="uq_tariff_hs_corridor_version",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    hs_code: Mapped[str] = mapped_column(ForeignKey("hs_codes.code"), index=True)
    origin: Mapped[str] = mapped_column(String(2), index=True)
    destination: Mapped[str] = mapped_column(String(2), index=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(8, 4))
    rate_type: Mapped[str] = mapped_column(String(32), default="ad_valorem_pct")
    duty_components: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    agreement_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    effective_from: Mapped[date] = mapped_column(Date, index=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_document_id: Mapped[str] = mapped_column(ForeignKey("source_documents.id"))
    version: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    data_quality: Mapped[str] = mapped_column(String(32), default="illustrative")
    superseded_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    regime: Mapped[str] = mapped_column(String(32), default="mfn")
    rule_label: Mapped[str | None] = mapped_column(String(256), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    hs: Mapped[HsCode] = relationship(back_populates="tariff_rates")
    source_document: Mapped[SourceDocument] = relationship(back_populates="tariff_rates")


class DocumentRequirement(Base):
    __tablename__ = "document_requirements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    origin: Mapped[str] = mapped_column(String(2), index=True)
    destination: Mapped[str] = mapped_column(String(2), index=True)
    hs_code: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    agreement_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    doc_code: Mapped[str] = mapped_column(String(64))
    doc_label: Mapped[str] = mapped_column(String(256))
    required: Mapped[bool] = mapped_column(default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class DocumentUpload(Base):
    __tablename__ = "document_uploads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    shipment_id: Mapped[str] = mapped_column(ForeignKey("shipments.id"), index=True)
    doc_code: Mapped[str] = mapped_column(String(64), index=True)
    filename: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    storage_path: Mapped[str] = mapped_column(String(1024))
    checksum: Mapped[str] = mapped_column(String(128))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    uploaded_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Shipment(Base):
    __tablename__ = "shipments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(256))
    product_text: Mapped[str] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(String(2))
    destination: Mapped[str] = mapped_column(String(2))
    hs_code_working: Mapped[str | None] = mapped_column(String(16), nullable=True)
    as_of_date: Mapped[date] = mapped_column(Date)
    incoterm: Mapped[str] = mapped_column(String(16), default="CIF")
    invoice_value: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    qty: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("1"))
    freight: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    insurance: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    regime: Mapped[str] = mapped_column(String(32), default="mfn")
    agreement_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    organization_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    assumptions_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    hs_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    exporter_party_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("parties.id"), nullable=True
    )
    importer_party_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("parties.id"), nullable=True
    )
    consignee_party_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("parties.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    calculations: Mapped[list[ShipmentCalculation]] = relationship(back_populates="shipment")
    checklists: Mapped[list[ShipmentChecklist]] = relationship(back_populates="shipment")
    line_items: Mapped[list[LineItem]] = relationship(back_populates="shipment")
    evidence_rows: Mapped[list[Evidence]] = relationship(back_populates="shipment")
    calculation_snapshots: Mapped[list[CalculationSnapshot]] = relationship(
        back_populates="shipment"
    )


class LineItem(Base):
    __tablename__ = "line_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    shipment_id: Mapped[str] = mapped_column(ForeignKey("shipments.id"), index=True)
    line_number: Mapped[int] = mapped_column(default=1)
    description: Mapped[str] = mapped_column(Text)
    hs_code: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    qty: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("1"))
    unit_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    origin: Mapped[str | None] = mapped_column(String(2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    shipment: Mapped[Shipment] = relationship(back_populates="line_items")


class Evidence(Base):
    """Citation / supporting artifact linked to a shipment (or standalone)."""

    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    shipment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("shipments.id"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(64), default="citation")
    label: Mapped[str] = mapped_column(String(256))
    source_document_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("source_documents.id"), nullable=True
    )
    tariff_rate_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    uri: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="recorded")
    meta_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    shipment: Mapped[Shipment | None] = relationship(back_populates="evidence_rows")


class ShipmentCalculation(Base):
    __tablename__ = "shipment_calculations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    shipment_id: Mapped[str] = mapped_column(ForeignKey("shipments.id"), index=True)
    inputs_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    outputs_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    tariff_rate_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    shipment: Mapped[Shipment] = relationship(back_populates="calculations")


class CalculationSnapshot(Base):
    """Immutable landed-cost snapshot with explicit estimate|customs mode."""

    __tablename__ = "calculation_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    shipment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("shipments.id"), nullable=True, index=True
    )
    calculation_mode: Mapped[str] = mapped_column(String(16), index=True)
    requested_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    title: Mapped[str] = mapped_column(String(256))
    inputs_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    outputs_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    tariff_rate_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_document_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    calculation_engine_version: Mapped[str] = mapped_column(String(32), default="in_duty.v1")
    source_checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tariff_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    data_quality: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    shipment: Mapped[Shipment | None] = relationship(back_populates="calculation_snapshots")


class ScenarioImpact(Base):
    """Financial impact of a tariff change on a saved scenario (IF-11e + IF-12c)."""

    __tablename__ = "scenario_impacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    shipment_id: Mapped[str] = mapped_column(ForeignKey("shipments.id"), index=True)
    organization_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    hs_code: Mapped[str] = mapped_column(String(16), index=True)
    origin: Mapped[str] = mapped_column(String(2))
    destination: Mapped[str] = mapped_column(String(2))
    old_rate: Mapped[Decimal] = mapped_column(Numeric(8, 4))
    new_rate: Mapped[Decimal] = mapped_column(Numeric(8, 4))
    old_landed_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    new_landed_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    duty_delta: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    landed_delta: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    old_tariff_rate_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    new_tariff_rate_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    old_snapshot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    new_snapshot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    recommended_action: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    dedupe_key: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    source_document_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String(128), nullable=True)


class ScenarioEvent(Base):
    """Scenario decision timeline events (IF-12d)."""

    __tablename__ = "scenario_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    scenario_id: Mapped[str] = mapped_column(ForeignKey("shipments.id"), index=True)
    organization_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    summary: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    snapshot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    tariff_rate_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    impact_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ShipmentChecklist(Base):
    __tablename__ = "shipment_checklists"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    shipment_id: Mapped[str] = mapped_column(ForeignKey("shipments.id"), index=True)
    items_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    progress: Mapped[str] = mapped_column(String(32), default="0/0")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    shipment: Mapped[Shipment] = relationship(back_populates="checklists")


class AskRun(Base):
    __tablename__ = "ask_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    shipment_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    query: Mapped[str] = mapped_column(Text)
    route: Mapped[str] = mapped_column(String(64))
    plan_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    evidence_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    tokens_in: Mapped[int] = mapped_column(default=0)
    tokens_out: Mapped[int] = mapped_column(default=0)
    latency_ms: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TradeAgreement(Base):
    __tablename__ = "trade_agreements"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(32), default="illustrative")
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    eligibility_rules: Mapped[list[AgreementEligibility]] = relationship(
        back_populates="agreement"
    )


class AgreementEligibility(Base):
    __tablename__ = "agreement_eligibility"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    agreement_id: Mapped[str] = mapped_column(ForeignKey("trade_agreements.id"), index=True)
    hs_code: Mapped[str] = mapped_column(String(16), index=True)
    origin: Mapped[str] = mapped_column(String(2), index=True)
    destination: Mapped[str] = mapped_column(String(2), index=True)
    preferential_rate_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4))
    status: Mapped[str] = mapped_column(String(32), default="conditional")
    certificate_doc_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    roo_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_document_id: Mapped[str] = mapped_column(ForeignKey("source_documents.id"))
    data_quality: Mapped[str] = mapped_column(String(32), default="illustrative")
    conditions_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    agreement: Mapped[TradeAgreement] = relationship(back_populates="eligibility_rules")


class RegulatoryChunk(Base):
    __tablename__ = "regulatory_chunks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_document_id: Mapped[str] = mapped_column(
        ForeignKey("source_documents.id"), index=True
    )
    text: Mapped[str] = mapped_column(Text)
    hs_code: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    hs_code: Mapped[str] = mapped_column(String(16), index=True)
    origin: Mapped[str] = mapped_column(String(2))
    destination: Mapped[str] = mapped_column(String(2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_rate_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    shipment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("shipments.id"), nullable=True, index=True
    )
    organization_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(256))
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    tax_identifier: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UserAccount(Base):
    """Application user mapped from IdP subject (IF-10)."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), index=True
    )
    email: Mapped[str] = mapped_column(String(256), unique=True)
    name: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(32), default="viewer")
    idp_subject: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DataVersion(Base):
    __tablename__ = "data_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    label: Mapped[str] = mapped_column(String(128))
    fingerprint: Mapped[str] = mapped_column(String(128), index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    batch_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    record_counts: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class IngestionBatch(Base):
    __tablename__ = "ingestion_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_key: Mapped[str] = mapped_column(String(128), index=True)
    archive_path: Mapped[str] = mapped_column(String(1024))
    checksum: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(512))
    publisher: Mapped[str] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(32), index=True, default="pending_review")
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    validation_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_source_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    data_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    proposals: Mapped[list[IngestionProposal]] = relationship(back_populates="batch")


class IngestionProposal(Base):
    __tablename__ = "ingestion_proposals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    batch_id: Mapped[str] = mapped_column(ForeignKey("ingestion_batches.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    validation_status: Mapped[str] = mapped_column(String(16), default="ok")
    validation_errors: Mapped[list[str]] = mapped_column(JSON, default=list)
    publish_status: Mapped[str] = mapped_column(String(16), default="pending")

    batch: Mapped[IngestionBatch] = relationship(back_populates="proposals")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    actor: Mapped[str] = mapped_column(String(128), default="anonymous")
    role: Mapped[str] = mapped_column(String(32), default="viewer")
    action: Mapped[str] = mapped_column(String(64), index=True)
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    kind: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(256))
    body: Mapped[str] = mapped_column(Text)
    watchlist_item_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    shipment_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    job_type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="completed")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class SourceConnection(Base):
    """Configured official-source endpoints (Phase A registry)."""

    __tablename__ = "source_connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(512))
    publisher: Mapped[str] = mapped_column(String(256))
    fetch_mode: Mapped[str] = mapped_column(String(32), default="curated_mirror")
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    local_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    origin: Mapped[str] = mapped_column(String(2), default="BD")
    destination: Mapped[str] = mapped_column(String(2), default="IN")
    hs_chapter: Mapped[str] = mapped_column(String(4), default="61")
    adapter: Mapped[str] = mapped_column(String(64), default="curated_json_mirror")
    honesty_label: Mapped[str] = mapped_column(
        String(128), default="Official-source-backed curated mirror"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_archive_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    last_source_document_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # IF-3 enrichment
    authority: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    access_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    requires_auth: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    capabilities_json: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    schedule: Mapped[str | None] = mapped_column(String(64), nullable=True)
    connector_type: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Country(Base):
    __tablename__ = "countries"

    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Corridor(Base):
    __tablename__ = "corridors"
    __table_args__ = (
        UniqueConstraint(
            "origin_country",
            "destination_country",
            name="uq_corridors_origin_destination",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    origin_country: Mapped[str] = mapped_column(String(2), index=True)
    destination_country: Mapped[str] = mapped_column(String(2), index=True)
    status: Mapped[str] = mapped_column(String(32), default="demonstration", index=True)
    supported_hs_chapters: Mapped[list[Any]] = mapped_column(JSON, default=list)
    supported_regimes: Mapped[list[Any]] = mapped_column(JSON, default=list)
    tariff_source_codes: Mapped[list[Any]] = mapped_column(JSON, default=list)
    agreement_source_codes: Mapped[list[Any]] = mapped_column(JSON, default=list)
    regulation_source_codes: Mapped[list[Any]] = mapped_column(JSON, default=list)
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class SourceCoverage(Base):
    __tablename__ = "source_coverage"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_connection_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("source_connections.id"), nullable=True
    )
    source_code: Mapped[str] = mapped_column(String(128), index=True)
    corridor_id: Mapped[str] = mapped_column(String(36), ForeignKey("corridors.id"), index=True)
    hs_chapter: Mapped[str] = mapped_column(String(4))
    capability: Mapped[str] = mapped_column(String(64))
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class FieldMapping(Base):
    __tablename__ = "field_mappings"
    __table_args__ = (
        UniqueConstraint("source_code", "format", name="uq_field_mappings_source_format"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_code: Mapped[str] = mapped_column(String(128), index=True)
    format: Mapped[str] = mapped_column(String(32))
    mapping_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    parser_version: Mapped[str] = mapped_column(String(32), default="1")
