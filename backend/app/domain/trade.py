"""Shared domain schemas for TradeGraph Phase 1 APIs."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import Field, model_validator

from backend.app.domain.base import ContractModel


class SourceDocumentOut(ContractModel):
    id: str
    title: str
    publisher: str
    url: str | None = None
    effective_from: date | None = None
    status: str
    notes: str | None = None
    checksum: str | None = None
    archive_path: str | None = None
    content_type: str | None = None
    source_kind: str = "curated_dataset"
    live_claim: bool = False
    live_government_feed: bool = False
    fetched_at: datetime | None = None
    parsed_at: datetime | None = None
    reviewed_at: datetime | None = None
    published_at: datetime | None = None
    superseded_by: str | None = None
    review_notes: str | None = None
    honesty_notice: str | None = None


class SourceArchiveRequest(ContractModel):
    title: str = Field(min_length=1, max_length=512)
    publisher: str = Field(min_length=1, max_length=256)
    archive_path: str = Field(min_length=1, max_length=1024)
    source_id: str | None = Field(default=None, max_length=64)
    url: str | None = None
    effective_from: date | None = None
    content_type: str | None = None
    notes: str | None = None


class SourceStatusTransition(ContractModel):
    status: Literal[
        "unverified",
        "fetched",
        "parsed",
        "validation_failed",
        "awaiting_review",
        "approved",
        "published",
        "superseded",
        "rejected",
        "expired",
    ]
    notes: str | None = None


class HsCodeOut(ContractModel):
    code: str
    description: str
    chapter: str
    parent_code: str | None = None


class TariffRateOut(ContractModel):
    id: str
    hs_code: str
    origin: str
    destination: str
    rate: Decimal
    rate_type: str
    duty_components: dict[str, Any]
    agreement_id: str | None = None
    effective_from: date
    effective_to: date | None = None
    source_document_id: str
    version: int
    status: str
    data_quality: Literal["illustrative", "demo_verified", "source_verified"]
    superseded_by: str | None = None
    regime: str = "mfn"
    rule_label: str | None = None
    notes: str | None = None
    source: SourceDocumentOut | None = None
    hs_description: str | None = None
    # IF-7 evidence / freshness
    lookup_status: Literal["found", "stale", "coverage_miss"] | None = None
    confidence: str | None = None
    source_stale: bool = False
    selection_warnings: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] | None = None


class TariffLookupOut(ContractModel):
    status: Literal["found", "stale", "coverage_miss"]
    tariff: TariffRateOut | None = None
    message: str | None = None
    last_verified_at: datetime | None = None
    selection_warnings: list[str] = Field(default_factory=list)
    preferred_source_codes: list[str] = Field(default_factory=list)


class LandedCostInput(ContractModel):
    hs_code: str = Field(min_length=4, max_length=16)
    origin: str = Field(min_length=2, max_length=2)
    destination: str = Field(min_length=2, max_length=2)
    as_of: date
    invoice_value: Decimal = Field(gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    incoterm: str = Field(default="CIF", min_length=3, max_length=16)
    freight: Decimal | None = Field(default=None, ge=0)
    insurance: Decimal | None = Field(default=None, ge=0)
    requested_mode: Literal["estimate", "customs"] | None = None
    shipment_id: str | None = None
    persist_snapshot: bool = True
    selected_exemption_id: str | None = None


class CustomsModeAvailability(ContractModel):
    """Preflight for customs-mode calculation (IF-11a)."""

    customs_mode_available: bool
    customs_mode_blockers: list[str] = Field(default_factory=list)
    customs_mode_hint: str = ""
    approved_tariff_rule_count: int = 0


class DutyStackLine(ContractModel):
    code: str
    display_name: str
    tariff_rate_pct: Decimal
    effective_rate_pct: Decimal
    amount: Decimal
    notification_sl: str | None = None
    component_key: str | None = None
    data_quality: str | None = None
    source_key: str | None = None
    source_document_id: str | None = None
    provenance_notes: str | None = None


class ComponentProvenanceOut(ContractModel):
    component_key: str
    value: Decimal | None = None
    data_quality: str = "missing"
    source_key: str | None = None
    source_document_id: str | None = None
    effective_from: date | None = None
    notes: str | None = None


class ExemptionRuleOut(ContractModel):
    id: str
    notification_id: str
    notification_year: int | None = None
    serial_no: str
    label: str
    hs_match: str
    origin: str
    destination: str = "IN"
    condition_code: str
    condition_detail: str
    effect: dict[str, Any] = Field(default_factory=dict)
    source_document_id: str | None = None
    eligibility: Literal["eligible_now", "eligible_if_coo", "not_eligible"] = "eligible_now"
    eligibility_reason: str = ""


class DutyStructureOut(ContractModel):
    hs_code: str
    origin: str
    destination: str
    as_of: date
    assessable_value: Decimal
    currency: str
    tariff_rate_id: str | None = None
    data_quality: str = "illustrative"
    stack: list[DutyStackLine] = Field(default_factory=list)
    component_sources: list[ComponentProvenanceOut] = Field(default_factory=list)
    coverage: dict[str, str] = Field(default_factory=dict)
    total_duties: Decimal
    landed_cost: Decimal
    mfn_total_duties: Decimal
    duty_savings: Decimal = Decimal("0")
    selected_exemption_id: str | None = None
    selected_exemption_label: str | None = None
    exemptions: list[ExemptionRuleOut] = Field(default_factory=list)
    preferential_status: str | None = None
    preferential_blocked_reason: str | None = None
    honesty_note: str = (
        "Component-sourced duty structure for BD→IN. BCD/SWS/IGST carry separate provenance; "
        "IGST notifications never invent BCD. Not a substitute for ICEGATE / official CBIC."
    )


class TariffCoverageChapterOut(ContractModel):
    chapter: str
    classification_codes: int = 0
    bcd_rates: int = 0
    sws_rates: int = 0
    igst_rates: int = 0
    exemption_rules: int = 0
    preferential_rules: int = 0
    # Per-component status — never confuse numeric 0% with missing data.
    bcd_status: Literal["verified", "curated", "missing", "needs_review", "illustrative"] = (
        "missing"
    )
    sws_status: Literal["verified", "curated", "missing", "needs_review", "illustrative"] = (
        "missing"
    )
    igst_status: Literal["verified", "curated", "missing", "needs_review", "illustrative"] = (
        "missing"
    )
    classification_status: Literal[
        "verified", "curated", "missing", "needs_review", "illustrative"
    ] = "missing"
    exemption_status: Literal[
        "verified", "curated", "missing", "needs_review", "illustrative"
    ] = "missing"
    preferential_status: Literal[
        "verified", "curated", "missing", "needs_review", "illustrative"
    ] = "missing"


class TariffCoverageOut(ContractModel):
    origin: str = "BD"
    destination: str = "IN"
    chapters: list[TariffCoverageChapterOut] = Field(default_factory=list)
    honesty_note: str = (
        "Coverage counts are operational inventory, not a claim of complete First Schedule. "
        "Status 'missing' means no sourced component — not a 0% rate."
    )


class LandedCostBreakdown(ContractModel):
    assessable_value: Decimal
    bcd: Decimal
    sws: Decimal
    igst: Decimal
    aidc: Decimal = Decimal("0")
    health_cess: Decimal = Decimal("0")
    compensation_cess: Decimal = Decimal("0")
    total_duties_taxes: Decimal
    landed_cost: Decimal
    currency: str
    bcd_rate_pct: Decimal
    sws_pct_of_bcd: Decimal
    igst_rate_pct: Decimal
    aidc_rate_pct: Decimal = Decimal("0")
    health_cess_rate_pct: Decimal = Decimal("0")
    compensation_cess_rate_pct: Decimal = Decimal("0")
    tariff_rate_id: str
    data_quality: str
    source_document_id: str
    effective_from: date
    effective_to: date | None = None
    disclaimer: str
    formula_steps: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    calculation_mode: Literal["estimate", "customs"] = "estimate"
    title: str = "Estimated landed cost"
    assumptions: list[str] = Field(default_factory=list)
    customs_mode_available: bool | None = None
    customs_mode_blockers: list[str] = Field(default_factory=list)
    duty_stack: list[DutyStackLine] = Field(default_factory=list)
    exemption_rule_id: str | None = None
    exemption_label: str | None = None
    mfn_total_duties: Decimal | None = None
    duty_savings: Decimal | None = None
    honesty_note: str = (
        "Illustrative duty stack for demo — not a complete ICEGATE determination. "
        "Verify BCD/AIDC/cess/exemption Sl. Nos. against official notifications."
    )


DocStatus = Literal["not_started", "draft", "needs_review", "ready"]


class ChecklistItemOut(ContractModel):
    doc_code: str
    doc_label: str
    required: bool
    notes: str | None = None
    done: bool = False
    status: DocStatus = "not_started"


class ChecklistOut(ContractModel):
    origin: str
    destination: str
    hs_code: str | None = None
    items: list[ChecklistItemOut]
    progress: str


class ChecklistItemStatusUpdate(ContractModel):
    status: DocStatus


class DraftExportOut(ContractModel):
    kind: Literal["commercial_invoice", "packing_list", "checklist"]
    filename: str
    text: str
    content_type: str = "text/plain; charset=utf-8"
    pdf_base64: str | None = None


class DocumentUploadOut(ContractModel):
    id: str
    shipment_id: str
    doc_code: str
    filename: str
    content_type: str
    checksum: str
    uploaded_at: datetime
    uploaded_by: str | None = None
    notes: str | None = None
    storage_path: str


class DocumentFormField(ContractModel):
    name: str
    label: str
    value: str | None = None
    required: bool = False


class DocumentFormOut(ContractModel):
    kind: Literal["commercial_invoice", "packing_list", "certificate_of_origin"]
    title: str
    fields: list[DocumentFormField] = Field(default_factory=list)
    disclaimer: str


class DocWhyRequiredOut(ContractModel):
    doc_code: str
    doc_label: str
    required: bool
    notes: str | None = None
    why: str
    source_tip: str | None = None
    retrieval_excerpt: str | None = None
    retrieval_source_id: str | None = None


class PartyOut(ContractModel):
    id: str
    organization_id: str | None = None
    name: str
    role: str
    country: str | None = None
    address_text: str | None = None
    tax_id: str | None = None
    notes: str | None = None
    created_at: datetime


class PartyCreate(ContractModel):
    name: str = Field(min_length=1, max_length=256)
    role: Literal["exporter", "importer", "consignee", "manufacturer", "other"] = "exporter"
    country: str | None = Field(default=None, min_length=2, max_length=2)
    address_text: str | None = None
    tax_id: str | None = None
    notes: str | None = None


class PartyUpdate(ContractModel):
    name: str | None = Field(default=None, min_length=1, max_length=256)
    role: Literal["exporter", "importer", "consignee", "manufacturer", "other"] | None = None
    country: str | None = Field(default=None, min_length=2, max_length=2)
    address_text: str | None = None
    tax_id: str | None = None
    notes: str | None = None


class LineItemOut(ContractModel):
    id: str
    shipment_id: str
    line_number: int
    description: str
    hs_code: str | None = None
    qty: Decimal
    unit_value: Decimal | None = None
    currency: str
    origin: str | None = None
    notes: str | None = None


class LineItemCreate(ContractModel):
    description: str = Field(min_length=1)
    line_number: int = Field(default=1, ge=1)
    hs_code: str | None = None
    qty: Decimal = Field(default=Decimal("1"), gt=0)
    unit_value: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    origin: str | None = Field(default=None, min_length=2, max_length=2)
    notes: str | None = None


class LineItemUpdate(ContractModel):
    description: str | None = Field(default=None, min_length=1)
    line_number: int | None = Field(default=None, ge=1)
    hs_code: str | None = None
    qty: Decimal | None = Field(default=None, gt=0)
    unit_value: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    origin: str | None = Field(default=None, min_length=2, max_length=2)
    notes: str | None = None


class EvidenceOut(ContractModel):
    id: str
    shipment_id: str | None = None
    kind: str
    label: str
    source_document_id: str | None = None
    tariff_rate_id: str | None = None
    excerpt: str | None = None
    uri: str | None = None
    checksum: str | None = None
    status: str
    meta: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class EvidenceCreate(ContractModel):
    kind: str = Field(default="citation", max_length=64)
    label: str = Field(min_length=1, max_length=256)
    source_document_id: str | None = None
    tariff_rate_id: str | None = None
    excerpt: str | None = None
    uri: str | None = None
    checksum: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class ClassificationCandidate(ContractModel):
    hs_code: str
    description: str
    chapter: str
    score: float
    reasons: list[str] = Field(default_factory=list)
    confidence_label: str = "possible_match"


class ClassificationCandidatesOut(ContractModel):
    product_text: str
    chapter: str
    candidates: list[ClassificationCandidate] = Field(default_factory=list)
    disclaimer: str


class ClassificationConfirmRequest(ContractModel):
    hs_code: str = Field(min_length=4, max_length=16)
    override_hs: str | None = Field(default=None, min_length=4, max_length=16)
    reason: str | None = Field(default=None, max_length=2000)


class ClassificationSuggestRequest(ContractModel):
    product_text: str = Field(min_length=1)
    chapter: str | None = Field(default=None, max_length=4)
    limit: int = Field(default=5, ge=1, le=10)


class CalculationSnapshotOut(ContractModel):
    id: str
    shipment_id: str | None = None
    calculation_mode: Literal["estimate", "customs"]
    requested_mode: Literal["estimate", "customs"] | None = None
    title: str
    inputs: dict[str, Any]
    outputs: LandedCostBreakdown
    tariff_rate_id: str | None = None
    source_document_id: str | None = None
    calculation_engine_version: str = "in_duty.v1"
    source_checksum: str | None = None
    tariff_version: int | None = None
    data_quality: str | None = None
    created_at: datetime


class SnapshotDiffOut(ContractModel):
    left_id: str
    right_id: str
    fields: dict[str, dict[str, Any]] = Field(default_factory=dict)
    summary: str = ""


class ScenarioImpactOut(ContractModel):
    id: str
    shipment_id: str
    shipment_title: str | None = None
    organization_id: str | None = None
    hs_code: str
    origin: str
    destination: str
    old_rate: Decimal
    new_rate: Decimal
    old_landed_cost: Decimal | None = None
    new_landed_cost: Decimal | None = None
    duty_delta: Decimal | None = None
    landed_delta: Decimal | None = None
    currency: str
    old_tariff_rate_id: str | None = None
    new_tariff_rate_id: str | None = None
    old_snapshot_id: str | None = None
    new_snapshot_id: str | None = None
    recommended_action: str
    summary: str
    created_at: datetime
    source_document_id: str | None = None
    effective_from: date | None = None
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    dedupe_key: str | None = None
    old_stack_signature: str | None = None
    new_stack_signature: str | None = None
    component_deltas: dict[str, Any] = Field(default_factory=dict)


class ScenarioTimelineEventOut(ContractModel):
    id: str
    scenario_id: str
    event_type: str
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)
    snapshot_id: str | None = None
    tariff_rate_id: str | None = None
    impact_id: str | None = None
    created_at: datetime


class ScenarioTimelineOut(ContractModel):
    scenario_id: str
    events: list[ScenarioTimelineEventOut] = Field(default_factory=list)


class ShipmentCalculateRequest(ContractModel):
    requested_mode: Literal["estimate", "customs"] | None = None
    freight: Decimal | None = Field(default=None, ge=0)
    insurance: Decimal | None = Field(default=None, ge=0)
    selected_exemption_id: str | None = None


class ShipmentCreate(ContractModel):
    title: str = Field(min_length=1, max_length=256)
    product_text: str = Field(min_length=1)
    origin: str = Field(default="BD", min_length=2, max_length=2)
    destination: str = Field(default="IN", min_length=2, max_length=2)
    hs_code_working: str | None = None
    as_of_date: date
    incoterm: str = Field(default="CIF", max_length=16)
    invoice_value: Decimal = Field(gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    qty: Decimal = Field(default=Decimal("1"), gt=0)
    freight: Decimal | None = Field(default=None, ge=0)
    insurance: Decimal | None = Field(default=None, ge=0)
    regime: str = Field(default="mfn", max_length=32)
    agreement_code: str | None = Field(default=None, max_length=64)
    organization_id: str | None = None
    assumptions: dict[str, Any] = Field(default_factory=dict)
    exporter_party_id: str | None = None
    importer_party_id: str | None = None
    consignee_party_id: str | None = None


class ShipmentUpdate(ContractModel):
    title: str | None = None
    product_text: str | None = None
    hs_code_working: str | None = None
    as_of_date: date | None = None
    incoterm: str | None = None
    invoice_value: Decimal | None = None
    currency: str | None = None
    qty: Decimal | None = None
    freight: Decimal | None = Field(default=None, ge=0)
    insurance: Decimal | None = Field(default=None, ge=0)
    regime: str | None = Field(default=None, max_length=32)
    agreement_code: str | None = None
    organization_id: str | None = None
    assumptions: dict[str, Any] | None = None
    status: str | None = None
    exporter_party_id: str | None = None
    importer_party_id: str | None = None
    consignee_party_id: str | None = None


class ShipmentOut(ContractModel):
    id: str
    title: str
    product_text: str
    origin: str
    destination: str
    hs_code_working: str | None
    as_of_date: date
    incoterm: str
    invoice_value: Decimal
    currency: str
    qty: Decimal
    freight: Decimal | None = None
    insurance: Decimal | None = None
    regime: str = "mfn"
    agreement_code: str | None = None
    organization_id: str | None = None
    assumptions: dict[str, Any] = Field(default_factory=dict)
    hs_confirmed_at: datetime | None = None
    status: str
    closed_at: datetime | None = None
    archived_at: datetime | None = None
    assign_reviewer_user_id: str | None = None
    lifecycle: Literal["open", "closed", "discarded"] = "open"
    exporter_party_id: str | None = None
    importer_party_id: str | None = None
    consignee_party_id: str | None = None
    created_at: datetime
    updated_at: datetime
    latest_calculation: LandedCostBreakdown | None = None
    checklist: ChecklistOut | None = None
    line_items: list[LineItemOut] = Field(default_factory=list)
    evidence: list[EvidenceOut] = Field(default_factory=list)
    calculation_snapshots: list[CalculationSnapshotOut] = Field(default_factory=list)


class AskRequest(ContractModel):
    query: str = Field(default="", max_length=2000)
    shipment_id: str | None = None
    as_of: date | None = None
    orchestration_mode: (
        Literal["adaptive", "direct_lookup", "fixed_multi", "always_llm"] | None
    ) = None
    focus: Literal["tariff", "shipment_gaps", "fta", "landed_cost"] | None = None
    hs_code: str | None = None
    origin: str | None = None
    destination: str | None = None

    @model_validator(mode="after")
    def require_query_or_focus(self) -> AskRequest:
        if not (self.query or "").strip() and self.focus is None:
            raise ValueError("Provide a query or a focus action")
        return self


class AskResponse(ContractModel):
    ask_run_id: str
    query: str
    route: str
    answer: str
    result: dict[str, Any]
    evidence: list[dict[str, Any]]
    tools_invoked: list[str]
    latency_ms: int
    tokens_in: int = 0
    tokens_out: int = 0
    warnings: list[str] = Field(default_factory=list)
    orchestration_mode: str = "adaptive"
    complexity_score: float = 0.0
    complexity_label: str = "simple"
    evidence_score: float = 0.0
    tool_count: int = 0
    policy_rationale: str = ""
    decision: Literal[
        "confirmed",
        "likely",
        "estimated",
        "needs_information",
        "not_supported",
        "no_approved_source",
    ] = "estimated"
    assumptions: list[str] = Field(default_factory=list)
    next_action: str = ""
    next_action_code: (
        Literal["upload_coo", "confirm_hs", "add_freight", "open_fta", "none"] | None
    ) = None
    source_status: str = "illustrative"


class AskHistoryItemOut(ContractModel):
    ask_run_id: str
    shipment_id: str | None = None
    query: str
    route: str
    answer: str | None = None
    decision: str | None = None
    next_action: str | None = None
    next_action_code: (
        Literal["upload_coo", "confirm_hs", "add_freight", "open_fta", "none"] | None
    ) = None
    tools_invoked: list[str] = Field(default_factory=list)
    latency_ms: int = 0
    created_at: datetime


class TradeAgreementOut(ContractModel):
    id: str
    name: str
    status: str
    effective_from: date | None = None
    notes: str | None = None


class FtaConditionInput(ContractModel):
    origin_criteria_met: bool = False
    rvc_pct: Decimal | None = Field(default=None, ge=0, le=100)
    processing_notes: str | None = None


class FtaConditionEvaluation(ContractModel):
    id: str
    type: str
    label: str
    status: Literal["passed", "failed", "needs_evidence"]
    detail: str = ""


class FtaCheckRequest(ContractModel):
    hs_code: str = Field(min_length=4, max_length=16)
    origin: str = Field(default="BD", min_length=2, max_length=2)
    destination: str = Field(default="IN", min_length=2, max_length=2)
    as_of: date
    agreement_id: str | None = None
    shipment_id: str | None = None
    conditions: FtaConditionInput | None = None


class FtaCheckResult(ContractModel):
    hs_code: str
    origin: str
    destination: str
    as_of: date
    status: Literal[
        "eligible",
        "potentially_eligible",
        "ineligible",
        "needs_evidence",
        "not_covered",
        "rule_not_available",
        "unknown",
    ]
    mfn_rate_pct: Decimal | None = None
    preferential_rate_pct: Decimal | None = None
    agreement_id: str | None = None
    agreement_name: str | None = None
    certificate_doc_code: str | None = None
    roo_summary: str | None = None
    graph_path: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    conditions: list[FtaConditionEvaluation] = Field(default_factory=list)
    data_quality: str = "illustrative"
    disclaimer: str


class ReadinessFactor(ContractModel):
    code: str
    label: str
    weight: int
    score: int
    detail: str


class ReadinessStatusChip(ContractModel):
    code: str
    label: str
    active: bool
    detail: str = ""


class ReadinessEvidenceItem(ContractModel):
    code: str
    label: str
    complete: bool


class ReadinessOut(ContractModel):
    score: int
    band: Literal["blocked", "partial", "ready"]
    overall_status: Literal["ready", "partial", "review_required", "blocked"] = "partial"
    calculation_ready: bool = False
    classification_uncertain: bool = False
    fta_unverified: bool = False
    documents_incomplete: bool = False
    source_stale: bool = False
    human_review_required: bool = False
    factors: list[ReadinessFactor] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    statuses: list[ReadinessStatusChip] = Field(default_factory=list)
    complete_items: list[ReadinessEvidenceItem] = Field(default_factory=list)
    missing_items: list[ReadinessEvidenceItem] = Field(default_factory=list)
    complete_evidence: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)


class AuthWhoAmI(ContractModel):
    authenticated: bool
    auth_enabled: bool
    allow_anonymous_publish: bool = False
    actor: str
    role: Literal["viewer", "operator", "reviewer", "admin"]
    email: str | None = None
    organization_id: str | None = None
    auth_method: str | None = None
    user_id: str | None = None
    display_name: str | None = None
    notification_prefs: dict[str, Any] = Field(default_factory=dict)
    mfa_required: bool = False


class AuthMeUpdate(ContractModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=256)
    notification_prefs: dict[str, Any] | None = None


class AdminUserOut(ContractModel):
    id: str
    email: str
    name: str
    role: str
    organization_id: str
    organization_name: str | None = None
    created_at: datetime


class AdminUserRoleUpdate(ContractModel):
    role: Literal["viewer", "operator", "reviewer", "admin"]


class UserInviteCreate(ContractModel):
    email: str = Field(min_length=3, max_length=256)
    role: Literal["viewer", "operator", "reviewer", "admin"] = "viewer"


class UserInviteOut(ContractModel):
    id: str
    organization_id: str
    email: str
    role: str
    invited_by: str | None = None
    status: str
    created_at: datetime
    accepted_at: datetime | None = None


class CaseCommentCreate(ContractModel):
    body: str = Field(min_length=1, max_length=8000)


class CaseCommentOut(ContractModel):
    id: str
    shipment_id: str
    organization_id: str | None = None
    author_user_id: str | None = None
    author_actor: str
    body: str
    created_at: datetime


class AssignReviewerRequest(ContractModel):
    assign_reviewer_user_id: str | None = None


class ProductTemplateCreate(ContractModel):
    name: str = Field(min_length=1, max_length=256)
    product_text: str = Field(min_length=1)
    hs_code: str | None = None
    origin: str | None = Field(default=None, min_length=2, max_length=2)
    destination: str | None = Field(default=None, min_length=2, max_length=2)
    notes: str | None = None


class ProductTemplateUpdate(ContractModel):
    name: str | None = Field(default=None, min_length=1, max_length=256)
    product_text: str | None = Field(default=None, min_length=1)
    hs_code: str | None = None
    origin: str | None = Field(default=None, min_length=2, max_length=2)
    destination: str | None = Field(default=None, min_length=2, max_length=2)
    notes: str | None = None


class ProductTemplateOut(ContractModel):
    id: str
    organization_id: str
    name: str
    product_text: str
    hs_code: str | None = None
    origin: str | None = None
    destination: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class ShareLinkOut(ContractModel):
    id: str
    token: str
    shipment_id: str
    organization_id: str | None = None
    created_by: str | None = None
    created_at: datetime
    expires_at: datetime | None = None
    share_path: str


class PublicShareOut(ContractModel):
    shipment_id: str
    title: str
    readiness: ReadinessOut
    papers: list[ChecklistItemOut] = Field(default_factory=list)


class FtaCompareOut(ContractModel):
    shipment_id: str
    without_preferential: CalculationSnapshotOut
    with_preferential: CalculationSnapshotOut
    diff: SnapshotDiffOut
    preferential_rate_pct: Decimal | None = None
    preferential_applied: bool = False
    preferential_status: str | None = None
    preferential_blocked_reason: str | None = None
    agreement_id: str | None = None
    agreement_name: str | None = None
    honesty_note: str = (
        "Preferential BCD applies only when FTA status is eligible (including CoO evidence). "
        "Illustrative until verified against official SAFTA / CBIC instruments."
    )


class SearchHitOut(ContractModel):
    kind: Literal["shipment", "hs", "document"]
    id: str
    title: str
    snippet: str | None = None
    shipment_id: str | None = None
    hs_code: str | None = None


class SearchOut(ContractModel):
    query: str
    results: list[SearchHitOut] = Field(default_factory=list)


class AuditLogOut(ContractModel):
    id: str
    created_at: datetime
    actor: str
    role: str
    action: str
    resource_type: str | None = None
    resource_id: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None


class NotificationOut(ContractModel):
    id: str
    kind: str
    title: str
    body: str
    watchlist_item_id: str | None = None
    shipment_id: str | None = None
    user_id: str | None = None
    organization_id: str | None = None
    is_read: bool
    created_at: datetime


class JobRunOut(ContractModel):
    id: str
    job_type: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    summary: dict[str, Any] = Field(default_factory=dict)


class CoverageMissOut(ContractModel):
    code: Literal["COVERAGE_MISS"] = "COVERAGE_MISS"
    message: str
    origin: str
    destination: str
    hs_code: str | None = None
    as_of: date | None = None
    possible_reasons: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    dataset_coverage: dict[str, Any] = Field(default_factory=dict)


class RetrievalHit(ContractModel):
    chunk_id: str
    source_document_id: str
    hs_code: str | None = None
    score: float
    text: str
    tags: list[str] = Field(default_factory=list)


class WatchlistItemCreate(ContractModel):
    hs_code: str | None = Field(default=None, min_length=4, max_length=16)
    origin: str = Field(default="BD", min_length=2, max_length=2)
    destination: str = Field(default="IN", min_length=2, max_length=2)
    shipment_id: str | None = None

    @model_validator(mode="after")
    def require_hs_or_shipment(self) -> WatchlistItemCreate:
        if not self.hs_code and not self.shipment_id:
            raise ValueError("Provide hs_code or shipment_id")
        return self


class WatchlistItemOut(ContractModel):
    id: str
    hs_code: str
    origin: str
    destination: str
    created_at: datetime
    last_seen_rate_id: str | None = None
    shipment_id: str | None = None
    shipment_title: str | None = None
    organization_id: str | None = None


class WatchlistChange(ContractModel):
    watchlist_item_id: str
    hs_code: str
    origin: str
    destination: str
    old_rate: Decimal
    new_rate: Decimal
    old_version: int
    new_version: int
    effective_from: date
    source_document_id: str
    summary: str
    affected_shipment_ids: list[str] = Field(default_factory=list)
    affected_shipment_titles: list[str] = Field(default_factory=list)


class BenchmarkCaseResult(ContractModel):
    case_id: str
    mode: str
    correct: bool
    route: str
    tools_invoked: list[str]
    tool_count: int
    latency_ms: int
    tokens_in: int
    tokens_out: int
    evidence_score: float
    complexity_score: float
    notes: str = ""


class BenchmarkModeSummary(ContractModel):
    mode: str
    cases: int
    accuracy: float
    avg_latency_ms: float
    avg_tokens_in: float
    avg_tokens_out: float
    avg_tool_count: float
    avg_evidence_score: float


class BenchmarkRunResult(ContractModel):
    summaries: list[BenchmarkModeSummary]
    cases: list[BenchmarkCaseResult]


class IngestRunRequest(ContractModel):
    source_key: str | None = Field(default="cbic_notification_2026_q3")
    archive_path: str | None = None
    force: bool = False


class IngestionProposalOut(ContractModel):
    id: str
    kind: str
    payload: dict[str, Any]
    validation_status: str
    validation_errors: list[str] = Field(default_factory=list)
    publish_status: str


class IngestionBatchOut(ContractModel):
    id: str
    source_key: str
    archive_path: str
    checksum: str
    title: str
    publisher: str
    status: str
    effective_from: date | None = None
    validation_summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    reviewed_at: datetime | None = None
    review_notes: str | None = None
    published_source_id: str | None = None
    data_version_id: str | None = None


class IngestionBatchDetail(IngestionBatchOut):
    proposals: list[IngestionProposalOut] = Field(default_factory=list)


class IngestReviewRequest(ContractModel):
    notes: str | None = None


class DataVersionOut(ContractModel):
    id: str
    label: str
    fingerprint: str
    notes: str | None = None
    published_at: datetime
    batch_id: str | None = None
    record_counts: dict[str, Any] = Field(default_factory=dict)


class DocumentRequirementOut(ContractModel):
    id: str
    origin: str
    destination: str
    hs_code: str | None = None
    doc_code: str
    doc_label: str
    required: bool
    notes: str | None = None


class DashboardShipmentCard(ContractModel):
    id: str
    title: str
    origin: str
    destination: str
    hs_code_working: str | None = None
    status: str
    as_of_date: date
    chips: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    readiness_band: Literal["blocked", "partial", "ready"] | None = None
    updated_at: datetime


class DashboardAlert(ContractModel):
    kind: str
    severity: str
    message: str
    shipment_id: str | None = None
    hs_code: str | None = None
    old_rate: Decimal | None = None
    new_rate: Decimal | None = None
    duty_delta: Decimal | None = None
    landed_delta: Decimal | None = None
    currency: str | None = None
    recommended_action: str | None = None
    impact_id: str | None = None
    shipment_title: str | None = None
    source_document_id: str | None = None
    effective_from: date | None = None
    previous_calculation_id: str | None = None
    new_calculation_id: str | None = None


class CoverageOut(ContractModel):
    origin: str
    destination: str
    hs_chapters: list[str] = Field(default_factory=list)


class ActiveRulesOut(ContractModel):
    total: int = 0
    approved: int = 0
    illustrative: int = 0


class LatestSourceBatchOut(ContractModel):
    id: str | None = None
    label: str | None = None
    status: str | None = None
    published_at: datetime | None = None


class DataStatusOut(ContractModel):
    corridor: str
    hs_chapter: str
    dataset_type: str
    last_approved_at: datetime | None = None
    last_approved_label: str | None = None
    note: str
    effective_product_status: Literal["illustrative", "mixed", "verified"] = "illustrative"
    active_rules: ActiveRulesOut = Field(default_factory=ActiveRulesOut)
    latest_source_batch: LatestSourceBatchOut | None = None
    trust_notice: str | None = None


class DashboardOut(ContractModel):
    shipments: list[DashboardShipmentCard] = Field(default_factory=list)
    alerts: list[DashboardAlert] = Field(default_factory=list)
    data_status: DataStatusOut


class WorkspaceRiskFlag(ContractModel):
    code: str
    severity: Literal["info", "warn", "blocker"]
    message: str


class ScenarioOverviewOut(ContractModel):
    """Composed clearance-case overview (IF-12b)."""

    status_chips: list[str] = Field(default_factory=list)
    trade_summary: dict[str, Any] = Field(default_factory=dict)
    decision_result: dict[str, Any] = Field(default_factory=dict)
    why_this_result: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    complete_evidence: list[str] = Field(default_factory=list)
    recent_changes: list[dict[str, Any]] = Field(default_factory=list)
    next_action_buttons: list[dict[str, str]] = Field(default_factory=list)


class ShipmentWorkspaceOut(ContractModel):
    shipment: ShipmentOut
    tariff: TariffRateOut | None = None
    fta: FtaCheckResult | None = None
    calculation: LandedCostBreakdown | None = None
    checklist: ChecklistOut | None = None
    classification_candidates: list[ClassificationCandidate] = Field(default_factory=list)
    calculation_snapshots: list[CalculationSnapshotOut] = Field(default_factory=list)
    readiness: ReadinessOut | None = None
    overview: ScenarioOverviewOut | None = None
    uploads: list[DocumentUploadOut] = Field(default_factory=list)
    risks: list[WorkspaceRiskFlag] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    summary: str = ""
    customs_mode_available: bool = False
    customs_mode_blockers: list[str] = Field(default_factory=list)
    customs_mode_hint: str = ""
    approved_tariff_rule_count: int = 0
    illustrative_tariff_rule_count: int = 0


class SystemStatusOut(ContractModel):
    """Global honesty / coverage status (PRODUCT_USABILITY_PLAN S1 + IF-11a + IF-12a)."""

    product_mode: Literal["demonstration", "operational"]
    requested_product_mode: Literal["demonstration", "operational"]
    mode_forced: bool = False
    mode_lock_reason: str | None = None
    corridor: str
    origin: str
    destination: str
    hs_chapter: str
    hs_chapters: list[str] = Field(default_factory=list)
    coverage: CoverageOut | None = None
    active_rules: ActiveRulesOut = Field(default_factory=ActiveRulesOut)
    latest_source_batch: LatestSourceBatchOut | None = None
    effective_product_status: Literal["illustrative", "mixed", "verified"] = "illustrative"
    trust_notice: str | None = None
    approved_tariff_rule_count: int = 0
    illustrative_tariff_rule_count: int = 0
    active_tariff_rule_count: int = 0
    last_approved_at: datetime | None = None
    last_approved_label: str | None = None
    official_source_connection: str = "Not configured"
    source_connection_kind: Literal[
        "none", "curated_mirror", "verified_published", "live_monitored"
    ] = "none"
    source_connection_label: str = "Official source not connected"
    live_government_feed: bool = False
    live_feed_reason: str | None = None
    enabled_source_connection_count: int = 0
    last_source_fetch_at: datetime | None = None
    source_fetch_interval_minutes: int | None = None
    customs_mode_available: bool = False
    customs_mode_blockers: list[str] = Field(default_factory=list)
    customs_mode_hint: str = ""
    notices: list[str] = Field(default_factory=list)
    disclaimer: str


class SourceConnectionOut(ContractModel):
    id: str
    key: str
    title: str
    publisher: str
    fetch_mode: str
    source_url: str | None = None
    document_url: str | None = None
    local_path: str | None = None
    enabled: bool
    origin: str
    destination: str
    hs_chapter: str
    adapter: str
    honesty_label: str
    notes: str | None = None
    last_checked_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    last_checksum: str | None = None
    last_archive_path: str | None = None
    last_source_document_id: str | None = None
    created_at: datetime
    pipeline_stage: str | None = None
    last_final_url: str | None = None
    last_content_type: str | None = None
    last_http_status: int | None = None
    last_semantic_fingerprint: str | None = None
    last_ingest_batch_id: str | None = None
    last_published_version_id: str | None = None
    last_published_at: datetime | None = None
    next_attempt_at: datetime | None = None
    refresh_mode: Literal["manual_only", "scheduled"] = "manual_only"
    fetch_overdue: bool = False
    freshness_sla_hours: int | None = None
    published_rates_usable: bool = True
    lane: Literal["live_official", "demo_fixture", "local_archive", "other"] = "other"


class SourceFetchResult(ContractModel):
    connection: SourceConnectionOut
    checksum: str
    archive_path: str
    source_document_id: str
    resolved_from: str
    ingest_batch_id: str | None = None
    message: str
    outcome: str | None = None
    semantic_fingerprint: str | None = None


class SourceFeedStatusOut(ContractModel):
    configured: bool
    enabled_connection_count: int
    official_source_connection: str
    source_connection_kind: Literal[
        "none", "curated_mirror", "verified_published", "live_monitored"
    ] = "none"
    source_connection_label: str = "Official source not connected"
    live_government_feed: bool
    live_feed_enabled_setting: bool
    live_feed_reason: str
    last_successful_fetch_at: datetime | None = None
    last_attempt_at: datetime | None = None
    scheduler_enabled: bool = False
    refresh_mode: Literal["manual_only", "scheduled"] = "manual_only"
    scheduler_interval_minutes: int
    has_live_adapter: bool = False
    next_attempt_at: datetime | None = None
    fetch_overdue: bool = False
    published_rates_usable: bool = True
    last_error: str | None = None


class SourcePipelineStatusOut(ContractModel):
    key: str
    stage: str
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    last_checksum: str | None = None
    last_archive_path: str | None = None
    final_url: str | None = None
    content_type: str | None = None
    http_status: int | None = None
    semantic_fingerprint: str | None = None
    ingest_batch_id: str | None = None
    published_version_id: str | None = None
    published_at: datetime | None = None
    next_attempt_at: datetime | None = None
    parser_version: str | None = None
    outcome: str | None = None


class IngestBatchDiffOut(ContractModel):
    batch_id: str
    source_key: str
    effective_from: date | None = None
    checksum: str
    archive_path: str
    changes: list[dict[str, Any]] = Field(default_factory=list)
    quarantined: list[dict[str, Any]] = Field(default_factory=list)
    affected_hs_codes: list[str] = Field(default_factory=list)


class PromoteCbicResult(ContractModel):
    """IF-11b: fixture → ingest → approve → publish summary."""

    batch_id: str
    data_version_id: str | None = None
    published_source_id: str | None = None
    rates_published: int = 0
    approved_tariff_rule_count: int = 0
    message: str = ""


class OrganizationOut(ContractModel):
    id: str
    name: str
    country: str | None = None
    tax_identifier: str | None = None
    mfa_required: bool = False
    slack_webhook_url: str | None = None
    created_at: datetime


class UserAccountOut(ContractModel):
    id: str
    organization_id: str
    email: str
    name: str
    role: str
    idp_subject: str | None = None
    notification_prefs: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class CountryOut(ContractModel):
    code: str
    name: str
    active: bool = True


class CorridorOut(ContractModel):
    id: str
    origin_country: str
    destination_country: str
    status: str
    operational: bool = False
    supported_hs_chapters: list[str] = Field(default_factory=list)
    supported_regimes: list[str] = Field(default_factory=list)
    tariff_source_codes: list[str] = Field(default_factory=list)
    agreement_source_codes: list[str] = Field(default_factory=list)
    regulation_source_codes: list[str] = Field(default_factory=list)
    last_verified_at: datetime | None = None
    notes: str | None = None


class SourceCoverageOut(ContractModel):
    id: str
    source_code: str
    corridor_id: str
    hs_chapter: str
    capability: str
    last_verified_at: datetime | None = None
