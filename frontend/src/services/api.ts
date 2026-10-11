/**
 * Live API client for FastAPI `/api/v1` (Phase 1).
 */

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  environment: string;
  contract_version: string;
  timestamp: string;
  prototype_corridor?: string;
}

export interface HsCode {
  code: string;
  description: string;
  chapter: string;
  parent_code: string | null;
}

export interface SourceDocument {
  id: string;
  title: string;
  publisher: string;
  url: string | null;
  effective_from: string | null;
  status: string;
  notes: string | null;
  checksum?: string | null;
  archive_path?: string | null;
  content_type?: string | null;
  source_kind?: string;
  live_claim?: boolean;
  live_government_feed?: boolean;
  honesty_notice?: string | null;
  published_at?: string | null;
}

export interface ClassificationCandidate {
  hs_code: string;
  description: string;
  chapter: string;
  score: number;
  reasons: string[];
  confidence_label: string;
}

export interface ClassificationCandidates {
  product_text: string;
  chapter: string;
  candidates: ClassificationCandidate[];
  disclaimer: string;
}

export interface CalculationSnapshot {
  id: string;
  shipment_id: string | null;
  calculation_mode: 'estimate' | 'customs';
  requested_mode: 'estimate' | 'customs' | null;
  title: string;
  inputs: Record<string, unknown>;
  outputs: LandedCostBreakdown;
  tariff_rate_id: string | null;
  source_document_id: string | null;
  calculation_engine_version?: string;
  source_checksum?: string | null;
  tariff_version?: number | null;
  data_quality?: string | null;
  created_at: string;
}

export interface SnapshotDiff {
  left_id: string;
  right_id: string;
  fields: Record<string, { left: unknown; right: unknown }>;
  summary: string;
}

export interface TariffRate {
  id: string;
  hs_code: string;
  origin: string;
  destination: string;
  rate: string | number;
  rate_type: string;
  duty_components: Record<string, unknown>;
  effective_from: string;
  effective_to: string | null;
  source_document_id: string;
  version: number;
  status: string;
  data_quality: string;
  superseded_by: string | null;
  source?: SourceDocument | null;
  hs_description?: string | null;
  lookup_status?: 'found' | 'stale' | 'coverage_miss' | null;
  confidence?: string | null;
  source_stale?: boolean;
  selection_warnings?: string[];
  evidence?: {
    document_id?: string;
    title?: string | null;
    publisher?: string;
    archive_path?: string | null;
    checksum?: string | null;
    retrieved_at?: string | null;
    published_at?: string | null;
    status?: string;
    verified?: boolean;
    message?: string;
  } | null;
}

export interface TariffLookup {
  status: 'found' | 'stale' | 'coverage_miss';
  tariff: TariffRate | null;
  message: string | null;
  last_verified_at: string | null;
  selection_warnings: string[];
  preferred_source_codes: string[];
}

export interface LandedCostInput {
  hs_code: string;
  origin: string;
  destination: string;
  as_of: string;
  invoice_value: number | string;
  currency?: string;
  incoterm?: string;
  freight?: number | string | null;
  insurance?: number | string | null;
  requested_mode?: 'estimate' | 'customs' | null;
  selected_exemption_id?: string | null;
}

export interface DutyStackLine {
  code: string;
  display_name: string;
  tariff_rate_pct: string | number;
  effective_rate_pct: string | number;
  amount: string | number;
  notification_sl?: string | null;
  component_key?: string | null;
  data_quality?: string | null;
  source_key?: string | null;
  source_document_id?: string | null;
  provenance_notes?: string | null;
}

export interface ComponentProvenance {
  component_key: string;
  value?: string | number | null;
  data_quality: string;
  source_key?: string | null;
  source_document_id?: string | null;
  effective_from?: string | null;
  notes?: string | null;
}

export interface TariffCoverageChapter {
  chapter: string;
  classification_codes: number;
  bcd_rates: number;
  sws_rates?: number;
  igst_rates: number;
  exemption_rules: number;
  preferential_rules: number;
  bcd_status?: string;
  sws_status?: string;
  igst_status?: string;
  classification_status?: string;
  exemption_status?: string;
  preferential_status?: string;
}

export interface TariffCoverage {
  origin: string;
  destination: string;
  chapters: TariffCoverageChapter[];
  honesty_note: string;
}

export interface ExemptionRule {
  id: string;
  notification_id: string;
  notification_year?: number | null;
  serial_no: string;
  label: string;
  hs_match: string;
  origin: string;
  destination: string;
  condition_code: string;
  condition_detail: string;
  effect: Record<string, unknown>;
  source_document_id?: string | null;
  eligibility: 'eligible_now' | 'eligible_if_coo' | 'not_eligible';
  eligibility_reason: string;
}

export interface DutyStructure {
  hs_code: string;
  origin: string;
  destination: string;
  as_of: string;
  assessable_value: string | number;
  currency: string;
  tariff_rate_id?: string | null;
  data_quality: string;
  stack: DutyStackLine[];
  component_sources?: ComponentProvenance[];
  coverage?: Record<string, string>;
  total_duties: string | number;
  landed_cost: string | number;
  mfn_total_duties: string | number;
  duty_savings: string | number;
  selected_exemption_id?: string | null;
  selected_exemption_label?: string | null;
  exemptions: ExemptionRule[];
  preferential_status?: string | null;
  preferential_blocked_reason?: string | null;
  honesty_note: string;
}

export interface LandedCostBreakdown {
  assessable_value: string | number;
  bcd: string | number;
  sws: string | number;
  igst: string | number;
  aidc?: string | number;
  health_cess?: string | number;
  compensation_cess?: string | number;
  total_duties_taxes: string | number;
  landed_cost: string | number;
  currency: string;
  bcd_rate_pct: string | number;
  sws_pct_of_bcd: string | number;
  igst_rate_pct: string | number;
  aidc_rate_pct?: string | number;
  health_cess_rate_pct?: string | number;
  compensation_cess_rate_pct?: string | number;
  tariff_rate_id: string;
  data_quality: string;
  source_document_id: string;
  effective_from: string;
  effective_to: string | null;
  disclaimer: string;
  formula_steps?: string[];
  warnings?: string[];
  calculation_mode?: 'estimate' | 'customs';
  title?: string;
  assumptions?: string[];
  duty_stack?: DutyStackLine[];
  exemption_rule_id?: string | null;
  exemption_label?: string | null;
  mfn_total_duties?: string | number | null;
  duty_savings?: string | number | null;
  honesty_note?: string;
}

export type DocStatus = 'not_started' | 'draft' | 'needs_review' | 'ready';

export interface ChecklistItem {
  doc_code: string;
  doc_label: string;
  required: boolean;
  notes: string | null;
  done: boolean;
  status?: DocStatus;
}

export interface Checklist {
  origin: string;
  destination: string;
  hs_code: string | null;
  items: ChecklistItem[];
  progress: string;
}

export interface Shipment {
  id: string;
  title: string;
  product_text: string;
  origin: string;
  destination: string;
  hs_code_working: string | null;
  as_of_date: string;
  incoterm: string;
  invoice_value: string | number;
  currency: string;
  qty: string | number;
  freight?: string | number | null;
  insurance?: string | number | null;
  regime?: string;
  agreement_code?: string | null;
  organization_id?: string | null;
  assumptions?: Record<string, unknown>;
  hs_confirmed_at?: string | null;
  status: string;
  closed_at?: string | null;
  archived_at?: string | null;
  assign_reviewer_user_id?: string | null;
  lifecycle?: 'open' | 'closed' | 'discarded';
  exporter_party_id?: string | null;
  importer_party_id?: string | null;
  consignee_party_id?: string | null;
  created_at: string;
  updated_at: string;
  latest_calculation?: LandedCostBreakdown | null;
  checklist?: Checklist | null;
  line_items?: LineItem[];
  evidence?: EvidenceItem[];
  calculation_snapshots?: CalculationSnapshot[];
}

export interface WorkspaceRiskFlag {
  code: string;
  severity: string;
  message: string;
}

export interface ScenarioOverview {
  status_chips: string[];
  trade_summary: Record<string, unknown>;
  decision_result: Record<string, unknown>;
  why_this_result: string[];
  missing_evidence: string[];
  complete_evidence: string[];
  recent_changes: Record<string, unknown>[];
  next_action_buttons: { id: string; label: string; tab: string }[];
}

export interface ShipmentWorkspace {
  shipment: Shipment;
  tariff: TariffRate | null;
  fta: FtaCheckResult | null;
  calculation: LandedCostBreakdown | null;
  checklist: Checklist | null;
  classification_candidates?: ClassificationCandidate[];
  calculation_snapshots?: CalculationSnapshot[];
  readiness?: {
    score: number;
    band: 'blocked' | 'partial' | 'ready';
    overall_status?: string;
    calculation_ready?: boolean;
    classification_uncertain?: boolean;
    fta_unverified?: boolean;
    documents_incomplete?: boolean;
    source_stale?: boolean;
    human_review_required?: boolean;
    factors: { code: string; label: string; weight: number; score: number; detail: string }[];
    missing: string[];
    blocked_reasons?: string[];
    statuses?: { code: string; label: string; active: boolean; detail: string }[];
    complete_items?: { code: string; label: string; complete: boolean }[];
    missing_items?: { code: string; label: string; complete: boolean }[];
    complete_evidence?: string[];
    missing_evidence?: string[];
  } | null;
  overview?: ScenarioOverview | null;
  uploads?: {
    id: string;
    doc_code: string;
    filename: string;
    checksum: string;
    uploaded_at: string;
  }[];
  risks: WorkspaceRiskFlag[];
  next_actions: string[];
  summary: string;
  customs_mode_available?: boolean;
  customs_mode_blockers?: string[];
  customs_mode_hint?: string;
  approved_tariff_rule_count?: number;
  illustrative_tariff_rule_count?: number;
}

export interface AskResponse {
  ask_run_id: string;
  query: string;
  route: string;
  answer: string;
  result: Record<string, unknown>;
  evidence: Record<string, unknown>[];
  tools_invoked: string[];
  latency_ms: number;
  tokens_in: number;
  tokens_out: number;
  warnings: string[];
  orchestration_mode?: string;
  complexity_score?: number;
  complexity_label?: string;
  evidence_score?: number;
  tool_count?: number;
  policy_rationale?: string;
  decision?:
    | 'confirmed'
    | 'likely'
    | 'estimated'
    | 'needs_information'
    | 'not_supported'
    | 'no_approved_source';
  assumptions?: string[];
  next_action?: string;
  next_action_code?: 'upload_coo' | 'confirm_hs' | 'add_freight' | 'open_fta' | 'none' | null;
  source_status?: string;
}

export interface TradeAgreement {
  id: string;
  name: string;
  status: string;
  effective_from: string | null;
  notes: string | null;
}

export interface FtaCheckResult {
  hs_code: string;
  origin: string;
  destination: string;
  as_of: string;
  status: string;
  mfn_rate_pct: string | number | null;
  preferential_rate_pct: string | number | null;
  agreement_id: string | null;
  agreement_name: string | null;
  certificate_doc_code: string | null;
  roo_summary: string | null;
  graph_path: Record<string, unknown>[];
  evidence: Record<string, unknown>[];
  reasons?: string[];
  conditions?: {
    id: string;
    type: string;
    label: string;
    status: string;
    detail: string;
  }[];
  data_quality: string;
  disclaimer: string;
}

export interface CoverageMiss {
  code?: string;
  message: string;
  origin: string;
  destination: string;
  hs_code: string | null;
  as_of: string | null;
  possible_reasons: string[];
  next_actions: string[];
  dataset_coverage: Record<string, unknown>;
}

export class ApiError extends Error {
  code?: string;
  details?: Record<string, unknown>;
  coverageMiss?: CoverageMiss;

  constructor(
    message: string,
    opts?: { code?: string; details?: Record<string, unknown>; coverageMiss?: CoverageMiss },
  ) {
    super(message);
    this.name = 'ApiError';
    this.code = opts?.code;
    this.details = opts?.details;
    this.coverageMiss = opts?.coverageMiss;
  }
}

export interface WatchlistItem {
  id: string;
  hs_code: string;
  origin: string;
  destination: string;
  created_at: string;
  last_seen_rate_id: string | null;
  shipment_id?: string | null;
  shipment_title?: string | null;
}

export interface WatchlistChange {
  watchlist_item_id: string;
  hs_code: string;
  origin: string;
  destination: string;
  old_rate: string | number;
  new_rate: string | number;
  old_version: number;
  new_version: number;
  effective_from: string;
  source_document_id: string;
  summary: string;
  affected_shipment_ids?: string[];
  affected_shipment_titles?: string[];
}

export interface DraftExport {
  kind: 'commercial_invoice' | 'packing_list' | 'checklist';
  filename: string;
  text: string;
  content_type?: string;
  pdf_base64?: string | null;
}

export interface DocWhyRequired {
  doc_code: string;
  doc_label: string;
  required: boolean;
  notes: string | null;
  why: string;
  source_tip: string | null;
  retrieval_excerpt: string | null;
  retrieval_source_id: string | null;
}

export interface DataVersion {
  id: string;
  label: string;
  fingerprint: string;
  notes: string | null;
  published_at: string;
  batch_id: string | null;
  record_counts: Record<string, unknown>;
}

export interface IngestionProposal {
  id: string;
  kind: string;
  payload: Record<string, unknown>;
  validation_status: string;
  validation_errors: string[];
  publish_status: string;
}

export interface IngestionBatchOut {
  id: string;
  source_key: string;
  archive_path: string;
  checksum: string;
  title: string;
  publisher: string;
  status: string;
  effective_from: string | null;
  validation_summary: Record<string, unknown>;
  created_at: string;
  reviewed_at: string | null;
  review_notes: string | null;
  published_source_id: string | null;
  data_version_id: string | null;
}

export interface IngestionBatchDetail extends IngestionBatchOut {
  proposals: IngestionProposal[];
}

export interface RetrievalHit {
  chunk_id: string;
  source_document_id: string;
  hs_code: string | null;
  score: number;
  text: string;
  tags: string[];
}

export interface DocumentRequirement {
  id: string;
  origin: string;
  destination: string;
  hs_code: string | null;
  doc_code: string;
  doc_label: string;
  required: boolean;
  notes: string | null;
}

export interface DashboardShipmentCard {
  id: string;
  title: string;
  origin: string;
  destination: string;
  hs_code_working: string | null;
  status: string;
  as_of_date: string;
  chips: string[];
  blocked_reasons?: string[];
  readiness_band?: 'blocked' | 'partial' | 'ready' | null;
  updated_at: string;
}

export interface DashboardAlert {
  kind: string;
  severity: string;
  message: string;
  shipment_id: string | null;
  hs_code?: string | null;
  old_rate?: string | number | null;
  new_rate?: string | number | null;
  duty_delta?: string | number | null;
  landed_delta?: string | number | null;
  currency?: string | null;
  recommended_action?: string | null;
  impact_id?: string | null;
  shipment_title?: string | null;
  source_document_id?: string | null;
  effective_from?: string | null;
  previous_calculation_id?: string | null;
  new_calculation_id?: string | null;
}

export interface ScenarioTimelineEvent {
  id: string;
  scenario_id: string;
  event_type: string;
  summary: string;
  payload: Record<string, unknown>;
  snapshot_id?: string | null;
  tariff_rate_id?: string | null;
  impact_id?: string | null;
  created_at: string;
}

export interface ScenarioTimeline {
  scenario_id: string;
  events: ScenarioTimelineEvent[];
}

export interface ActiveRulesOut {
  total: number;
  approved: number;
  illustrative: number;
}

export interface LatestSourceBatchOut {
  id: string | null;
  label: string | null;
  status: string | null;
  published_at: string | null;
}

export interface DataStatusOut {
  corridor: string;
  hs_chapter: string;
  dataset_type: string;
  last_approved_at: string | null;
  last_approved_label: string | null;
  note: string;
  effective_product_status?: 'illustrative' | 'mixed' | 'verified';
  active_rules?: ActiveRulesOut;
  latest_source_batch?: LatestSourceBatchOut | null;
  trust_notice?: string | null;
}

export interface DashboardOut {
  shipments: DashboardShipmentCard[];
  alerts: DashboardAlert[];
  data_status: DataStatusOut;
}

export interface SystemStatus {
  product_mode: 'demonstration' | 'operational';
  requested_product_mode: 'demonstration' | 'operational';
  mode_forced: boolean;
  mode_lock_reason: string | null;
  corridor: string;
  origin: string;
  destination: string;
  hs_chapter: string;
  hs_chapters: string[];
  coverage?: { origin: string; destination: string; hs_chapters: string[] } | null;
  active_rules?: ActiveRulesOut;
  latest_source_batch?: LatestSourceBatchOut | null;
  effective_product_status?: 'illustrative' | 'mixed' | 'verified';
  trust_notice?: string | null;
  approved_tariff_rule_count: number;
  illustrative_tariff_rule_count: number;
  active_tariff_rule_count: number;
  last_approved_at: string | null;
  last_approved_label: string | null;
  official_source_connection: string;
  source_connection_kind?: 'none' | 'curated_mirror' | 'verified_published' | 'live_monitored';
  source_connection_label?: string;
  live_government_feed: boolean;
  live_feed_reason?: string | null;
  enabled_source_connection_count?: number;
  last_source_fetch_at?: string | null;
  source_fetch_interval_minutes?: number | null;
  customs_mode_available?: boolean;
  customs_mode_blockers?: string[];
  customs_mode_hint?: string;
  notices: string[];
  disclaimer: string;
}

export interface CustomsModeAvailability {
  customs_mode_available: boolean;
  customs_mode_blockers: string[];
  customs_mode_hint: string;
  approved_tariff_rule_count: number;
}

export interface PromoteCbicResult {
  batch_id: string;
  data_version_id: string | null;
  published_source_id: string | null;
  rates_published: number;
  approved_tariff_rule_count: number;
  message: string;
}

export interface SourceConnection {
  id: string;
  key: string;
  title: string;
  publisher: string;
  fetch_mode: string;
  source_url: string | null;
  document_url?: string | null;
  local_path: string | null;
  enabled: boolean;
  origin: string;
  destination: string;
  hs_chapter: string;
  adapter: string;
  honesty_label: string;
  notes: string | null;
  last_checked_at: string | null;
  last_success_at: string | null;
  last_error: string | null;
  last_checksum: string | null;
  last_archive_path: string | null;
  last_source_document_id: string | null;
  created_at: string;
  pipeline_stage?: string | null;
  last_final_url?: string | null;
  last_content_type?: string | null;
  last_ingest_batch_id?: string | null;
  last_published_version_id?: string | null;
  last_published_at?: string | null;
  next_attempt_at?: string | null;
  refresh_mode?: 'manual_only' | 'scheduled';
  fetch_overdue?: boolean;
  freshness_sla_hours?: number | null;
  published_rates_usable?: boolean;
  lane?: 'live_official' | 'demo_fixture' | 'local_archive' | 'other';
}

export interface SourceFetchResult {
  connection: SourceConnection;
  checksum: string;
  archive_path: string;
  source_document_id: string;
  resolved_from: string;
  ingest_batch_id: string | null;
  message: string;
  outcome?: string | null;
  semantic_fingerprint?: string | null;
}

export interface SourceFeedStatus {
  configured: boolean;
  enabled_connection_count: number;
  official_source_connection: string;
  source_connection_kind?: string;
  source_connection_label?: string;
  live_government_feed: boolean;
  live_feed_enabled_setting: boolean;
  live_feed_reason: string;
  last_successful_fetch_at: string | null;
  last_attempt_at?: string | null;
  scheduler_enabled?: boolean;
  refresh_mode?: 'manual_only' | 'scheduled';
  scheduler_interval_minutes: number;
  has_live_adapter?: boolean;
  next_attempt_at?: string | null;
  fetch_overdue?: boolean;
  published_rates_usable?: boolean;
  last_error?: string | null;
}

export interface IngestBatchDiff {
  batch_id: string;
  source_key: string;
  effective_from: string | null;
  checksum: string;
  archive_path: string;
  changes: Array<Record<string, unknown>>;
  quarantined: Array<Record<string, unknown>>;
  affected_hs_codes: string[];
}

export interface JobRun {
  id: string;
  job_type: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  summary: Record<string, unknown>;
}

function apiBase(): string {
  const configured = import.meta.env.VITE_API_BASE_URL as string | undefined;
  if (configured && configured.length > 0) {
    return configured.replace(/\/$/, '');
  }
  return '';
}

export interface AuthWhoAmI {
  authenticated: boolean;
  auth_enabled: boolean;
  allow_anonymous_publish?: boolean;
  actor: string;
  role: 'viewer' | 'operator' | 'reviewer' | 'admin' | string;
  email: string | null;
  organization_id: string | null;
  auth_method: string | null;
  user_id?: string | null;
  display_name?: string | null;
  notification_prefs?: Record<string, unknown>;
  mfa_required?: boolean;
}

export interface UserAccount {
  id: string;
  organization_id: string;
  email: string;
  name: string;
  role: string;
  idp_subject?: string | null;
  notification_prefs: Record<string, unknown>;
  created_at: string;
}

export interface AdminUser {
  id: string;
  email: string;
  name: string;
  role: string;
  organization_id: string;
  organization_name?: string | null;
  created_at: string;
}

export interface UserInvite {
  id: string;
  organization_id: string;
  email: string;
  role: string;
  invited_by?: string | null;
  status: string;
  created_at: string;
  accepted_at?: string | null;
}

export interface Party {
  id: string;
  organization_id?: string | null;
  name: string;
  role: string;
  country?: string | null;
  address_text?: string | null;
  tax_id?: string | null;
  notes?: string | null;
  created_at: string;
}

export interface LineItem {
  id: string;
  shipment_id: string;
  line_number: number;
  description: string;
  hs_code?: string | null;
  qty: string | number;
  unit_value?: string | number | null;
  currency: string;
  origin?: string | null;
  notes?: string | null;
}

export interface EvidenceItem {
  id: string;
  shipment_id?: string | null;
  kind: string;
  label: string;
  source_document_id?: string | null;
  tariff_rate_id?: string | null;
  excerpt?: string | null;
  uri?: string | null;
  checksum?: string | null;
  status: string;
  meta?: Record<string, unknown>;
  created_at: string;
}

export interface CaseComment {
  id: string;
  shipment_id: string;
  organization_id?: string | null;
  author_user_id?: string | null;
  author_actor: string;
  body: string;
  created_at: string;
}

export interface AskHistoryItem {
  ask_run_id: string;
  shipment_id?: string | null;
  query: string;
  route: string;
  answer?: string | null;
  decision?: string | null;
  next_action?: string | null;
  next_action_code?: 'upload_coo' | 'confirm_hs' | 'add_freight' | 'open_fta' | 'none' | null;
  tools_invoked: string[];
  latency_ms: number;
  created_at: string;
}

export interface ScenarioImpact {
  id: string;
  shipment_id: string;
  shipment_title?: string | null;
  hs_code: string;
  origin: string;
  destination: string;
  old_rate: string | number;
  new_rate: string | number;
  duty_delta?: string | number | null;
  landed_delta?: string | number | null;
  currency: string;
  recommended_action: string;
  summary: string;
  created_at: string;
  acknowledged_at?: string | null;
  source_document_id?: string | null;
  effective_from?: string | null;
  old_stack_signature?: string | null;
  new_stack_signature?: string | null;
  component_deltas?: Record<string, { old?: number; new?: number }>;
}

export interface NotificationItem {
  id: string;
  kind: string;
  title: string;
  body: string;
  watchlist_item_id?: string | null;
  shipment_id?: string | null;
  user_id?: string | null;
  organization_id?: string | null;
  is_read: boolean;
  created_at: string;
}

export interface ShareLink {
  id: string;
  token: string;
  shipment_id: string;
  organization_id?: string | null;
  created_by?: string | null;
  created_at: string;
  expires_at?: string | null;
  share_path: string;
}

export interface PublicShare {
  shipment_id: string;
  title: string;
  readiness: NonNullable<ShipmentWorkspace['readiness']>;
  papers: ChecklistItem[];
}

export interface SearchHit {
  kind: 'shipment' | 'hs' | 'document';
  id: string;
  title: string;
  snippet?: string | null;
  shipment_id?: string | null;
  hs_code?: string | null;
}

export interface SearchOut {
  query: string;
  results: SearchHit[];
}

export interface ProductTemplate {
  id: string;
  organization_id: string;
  name: string;
  product_text: string;
  hs_code?: string | null;
  origin?: string | null;
  destination?: string | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Organization {
  id: string;
  name: string;
  country?: string | null;
  tax_identifier?: string | null;
  mfa_required?: boolean;
  created_at?: string;
}

export interface FtaCompareOut {
  shipment_id: string;
  without_preferential: CalculationSnapshot;
  with_preferential: CalculationSnapshot;
  diff: SnapshotDiff;
  preferential_rate_pct?: string | number | null;
  agreement_id?: string | null;
  agreement_name?: string | null;
}

type TokenProvider = (forceRefresh?: boolean) => Promise<string | null>;

let accessTokenProvider: TokenProvider = async () => null;

export function setAccessTokenProvider(provider: TokenProvider): void {
  accessTokenProvider = provider;
}

async function authHeaders(extra?: HeadersInit, skipJson = false): Promise<Headers> {
  const headers = new Headers(extra || {});
  if (!skipJson && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const token = await accessTokenProvider(false);
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  return headers;
}

async function request<T>(path: string, init?: RequestInit, retried = false): Promise<T> {
  const headers = await authHeaders(init?.headers);
  const response = await fetch(`${apiBase()}${path}`, {
    ...init,
    headers,
  });
  let finalResponse = response;
  if (response.status === 401 && !retried) {
    const refreshed = await accessTokenProvider(true);
    if (refreshed) {
      const retryHeaders = new Headers(init?.headers || {});
      if (!retryHeaders.has('Content-Type') && !(init?.body instanceof FormData)) {
        retryHeaders.set('Content-Type', 'application/json');
      }
      retryHeaders.set('Authorization', `Bearer ${refreshed}`);
      finalResponse = await fetch(`${apiBase()}${path}`, { ...init, headers: retryHeaders });
    }
  }
  if (!finalResponse.ok) {
    let message = `API ${path} failed: ${finalResponse.status}`;
    let code: string | undefined;
    let details: Record<string, unknown> | undefined;
    try {
      const body = await finalResponse.json();
      message = body?.error?.message || message;
      code = body?.error?.code;
      details = body?.error?.details;
    } catch {
      /* ignore */
    }
    const coverageMiss =
      code === 'COVERAGE_MISS' && details
        ? (details as unknown as CoverageMiss)
        : undefined;
    throw new ApiError(message, { code, details, coverageMiss });
  }
  if (finalResponse.status === 204) return undefined as T;
  return finalResponse.json() as Promise<T>;
}

async function requestBlob(path: string, filenameHint?: string): Promise<Blob> {
  const headers = await authHeaders(undefined, true);
  headers.delete('Content-Type');
  let response = await fetch(`${apiBase()}${path}`, { headers });
  if (response.status === 401) {
    const refreshed = await accessTokenProvider(true);
    if (refreshed) {
      const retryHeaders = new Headers();
      retryHeaders.set('Authorization', `Bearer ${refreshed}`);
      response = await fetch(`${apiBase()}${path}`, { headers: retryHeaders });
    }
  }
  if (!response.ok) {
    let message = `API ${path} failed: ${response.status}`;
    try {
      const body = await response.json();
      message = body?.error?.message || message;
    } catch {
      /* ignore */
    }
    throw new ApiError(message);
  }
  const blob = await response.blob();
  if (filenameHint) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filenameHint;
    a.click();
    URL.revokeObjectURL(url);
  }
  return blob;
}

export const api = {
  getWhoAmI: () => request<AuthWhoAmI>('/api/v1/auth/whoami'),
  patchMe: (body: { display_name?: string; notification_prefs?: Record<string, unknown> }) =>
    request<UserAccount>('/api/v1/auth/me', { method: 'PATCH', body: JSON.stringify(body) }),
  getHealth: () => request<HealthResponse>('/api/v1/health'),
  getSystemStatus: () => request<SystemStatus>('/api/v1/system/status'),
  getCustomsAvailability: () =>
    request<CustomsModeAvailability>('/api/v1/calculate/customs-availability'),
  getDashboard: (opts?: { queue?: 'blocked' | 'alerts' | 'all' }) => {
    const params = new URLSearchParams();
    if (opts?.queue) params.set('queue', opts.queue);
    const q = params.toString();
    return request<DashboardOut>(`/api/v1/dashboard${q ? `?${q}` : ''}`);
  },
  listOrganizations: () => request<Organization[]>('/api/v1/organizations'),
  listHsCodes: (q?: string, chapter = '61') => {
    const params = new URLSearchParams();
    if (q) params.set('q', q);
    if (chapter) params.set('chapter', chapter);
    return request<HsCode[]>(`/api/v1/hs-codes?${params}`);
  },
  listTariffs: (opts: {
    hs?: string;
    origin?: string;
    destination?: string;
    as_of?: string;
    include_history?: boolean;
    agreement_id?: string;
  }) => {
    const params = new URLSearchParams();
    if (opts.hs) params.set('hs', opts.hs);
    if (opts.origin) params.set('origin', opts.origin);
    if (opts.destination) params.set('destination', opts.destination);
    if (opts.as_of) params.set('as_of', opts.as_of);
    if (opts.include_history) params.set('include_history', 'true');
    if (opts.agreement_id) params.set('agreement_id', opts.agreement_id);
    return request<TariffRate[]>(`/api/v1/tariffs?${params}`);
  },
  lookupTariff: (opts: {
    hs: string;
    as_of: string;
    origin?: string;
    destination?: string;
    regime?: string;
  }) => {
    const params = new URLSearchParams({ hs: opts.hs, as_of: opts.as_of });
    if (opts.origin) params.set('origin', opts.origin);
    if (opts.destination) params.set('destination', opts.destination);
    if (opts.regime) params.set('regime', opts.regime);
    return request<TariffLookup>(`/api/v1/tariffs/lookup?${params}`);
  },
  tariffHistory: (id: string) => request<TariffRate[]>(`/api/v1/tariffs/${id}/history`),
  calculateLandedCost: (body: LandedCostInput) =>
    request<LandedCostBreakdown>('/api/v1/calculate/landed-cost', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  listShipments: (lifecycle: 'open' | 'closed' | 'discarded' | 'all' = 'open') =>
    request<Shipment[]>(`/api/v1/shipments?lifecycle=${lifecycle}`),
  createShipment: (body: Record<string, unknown>) =>
    request<Shipment>('/api/v1/shipments', { method: 'POST', body: JSON.stringify(body) }),
  getShipment: (id: string) => request<Shipment>(`/api/v1/shipments/${id}`),
  getShipmentWorkspace: (id: string) =>
    request<ShipmentWorkspace>(`/api/v1/shipments/${id}/workspace`),
  updateShipment: (id: string, body: Record<string, unknown>) =>
    request<Shipment>(`/api/v1/shipments/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  closeShipment: (id: string) =>
    request<Shipment>(`/api/v1/shipments/${id}/close`, { method: 'POST', body: '{}' }),
  reopenShipment: (id: string) =>
    request<Shipment>(`/api/v1/shipments/${id}/reopen`, { method: 'POST', body: '{}' }),
  discardShipment: (id: string) =>
    request<Shipment>(`/api/v1/shipments/${id}`, { method: 'DELETE' }),
  calculateShipment: (
    id: string,
    body?: {
      requested_mode?: 'estimate' | 'customs' | null;
      freight?: number | string | null;
      insurance?: number | string | null;
      selected_exemption_id?: string | null;
    },
  ) =>
    request<Shipment>(`/api/v1/shipments/${id}/calculate`, {
      method: 'POST',
      body: JSON.stringify(body || {}),
    }),
  getDutyStructure: (params: {
    hs: string;
    origin: string;
    destination?: string;
    as_of: string;
    assessable_value?: number | string;
    currency?: string;
    selected_exemption_id?: string | null;
    shipment_id?: string | null;
  }) => {
    const q = new URLSearchParams({
      hs: params.hs,
      origin: params.origin,
      destination: params.destination || 'IN',
      as_of: params.as_of,
    });
    if (params.assessable_value != null) q.set('assessable_value', String(params.assessable_value));
    if (params.currency) q.set('currency', params.currency);
    if (params.selected_exemption_id) q.set('selected_exemption_id', params.selected_exemption_id);
    if (params.shipment_id) q.set('shipment_id', params.shipment_id);
    return request<DutyStructure>(`/api/v1/duty/structure?${q}`);
  },
  getDutyCoverage: (params?: { origin?: string; destination?: string }) => {
    const q = new URLSearchParams({
      origin: params?.origin || 'BD',
      destination: params?.destination || 'IN',
    });
    return request<TariffCoverage>(`/api/v1/duty/coverage?${q}`);
  },
  listDutyExemptions: (params: {
    hs: string;
    origin: string;
    destination?: string;
    as_of: string;
    shipment_id?: string | null;
  }) => {
    const q = new URLSearchParams({
      hs: params.hs,
      origin: params.origin,
      destination: params.destination || 'IN',
      as_of: params.as_of,
    });
    if (params.shipment_id) q.set('shipment_id', params.shipment_id);
    return request<ExemptionRule[]>(`/api/v1/duty/exemptions?${q}`);
  },
  listCalculationSnapshots: (id: string) =>
    request<CalculationSnapshot[]>(`/api/v1/shipments/${id}/calculation-snapshots`),
  listScenarioCalculations: (id: string) =>
    request<CalculationSnapshot[]>(`/api/v1/scenarios/${id}/calculations`),
  getScenarioTimeline: (id: string) =>
    request<ScenarioTimeline>(`/api/v1/scenarios/${id}/timeline`),
  getShipmentTimeline: (id: string) =>
    request<ScenarioTimeline>(`/api/v1/shipments/${id}/timeline`),
  getAskHistory: (shipmentId: string) =>
    request<AskHistoryItem[]>(`/api/v1/shipments/${shipmentId}/ask-history`),
  downloadShipmentPack: (id: string) =>
    requestBlob(`/api/v1/shipments/${id}/pack`, `shipment_${id.slice(0, 8)}_pack.zip`),
  exportSummaryPdf: (id: string) =>
    requestBlob(`/api/v1/shipments/${id}/summary.pdf`, `shipment_${id.slice(0, 8)}_summary.pdf`),
  exportCostCsv: (id: string) =>
    requestBlob(`/api/v1/shipments/${id}/cost.csv`, `shipment_${id.slice(0, 8)}_cost.csv`),
  compareFta: (id: string) =>
    request<FtaCompareOut>(`/api/v1/shipments/${id}/compare-fta`, {
      method: 'POST',
      body: '{}',
    }),
  patchLineItem: (shipmentId: string, lineId: string, body: Record<string, unknown>) =>
    request<Shipment>(`/api/v1/shipments/${shipmentId}/line-items/${lineId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  deleteLineItem: (shipmentId: string, lineId: string) =>
    request<Shipment>(`/api/v1/shipments/${shipmentId}/line-items/${lineId}`, {
      method: 'DELETE',
    }),
  addLineItem: (shipmentId: string, body: Record<string, unknown>) =>
    request<Shipment>(`/api/v1/shipments/${shipmentId}/line-items`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  addEvidence: (shipmentId: string, body: Record<string, unknown>) =>
    request<Shipment>(`/api/v1/shipments/${shipmentId}/evidence`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  listComments: (shipmentId: string) =>
    request<CaseComment[]>(`/api/v1/shipments/${shipmentId}/comments`),
  addComment: (shipmentId: string, body: string) =>
    request<CaseComment>(`/api/v1/shipments/${shipmentId}/comments`, {
      method: 'POST',
      body: JSON.stringify({ body }),
    }),
  assignReviewer: (shipmentId: string, assign_reviewer_user_id: string | null) =>
    request<Shipment>(`/api/v1/shipments/${shipmentId}/assign-reviewer`, {
      method: 'PATCH',
      body: JSON.stringify({ assign_reviewer_user_id }),
    }),
  createShareLink: (shipmentId: string) =>
    request<ShareLink>(`/api/v1/shipments/${shipmentId}/share-links`, {
      method: 'POST',
      body: '{}',
    }),
  getPublicShare: (token: string) =>
    request<PublicShare>(`/api/v1/public/share/${encodeURIComponent(token)}`),
  listImpacts: () => request<ScenarioImpact[]>('/api/v1/impacts'),
  acknowledgeImpact: (impactId: string) =>
    request<ScenarioImpact>(`/api/v1/impacts/${impactId}/acknowledge`, {
      method: 'POST',
      body: '{}',
    }),
  listNotifications: (unreadOnly = false) =>
    request<NotificationItem[]>(
      `/api/v1/notifications${unreadOnly ? '?unread_only=true' : ''}`,
    ),
  markNotificationRead: (id: string) =>
    request<NotificationItem>(`/api/v1/notifications/${id}/read`, {
      method: 'POST',
      body: '{}',
    }),
  listAdminUsers: () => request<AdminUser[]>('/api/v1/admin/users'),
  patchAdminUser: (userId: string, role: string) =>
    request<AdminUser>(`/api/v1/admin/users/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify({ role }),
    }),
  createInvite: (body: { email: string; role?: string }) =>
    request<UserInvite>('/api/v1/admin/invites', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  listInvites: () => request<UserInvite[]>('/api/v1/admin/invites'),
  listParties: () => request<Party[]>('/api/v1/parties'),
  createParty: (body: Record<string, unknown>) =>
    request<Party>('/api/v1/parties', { method: 'POST', body: JSON.stringify(body) }),
  listProductTemplates: () => request<ProductTemplate[]>('/api/v1/product-templates'),
  globalSearch: (q: string) =>
    request<SearchOut>(`/api/v1/search?q=${encodeURIComponent(q)}`),
  getCalculation: (id: string) =>
    request<CalculationSnapshot>(`/api/v1/calculations/${id}`),
  diffCalculations: (leftId: string, rightId: string) =>
    request<SnapshotDiff>(`/api/v1/calculations/${leftId}/diff/${rightId}`),
  classificationCandidates: (id: string) =>
    request<ClassificationCandidates>(`/api/v1/shipments/${id}/classification/candidates`),
  confirmClassification: (id: string, hs_code: string) =>
    request<Shipment>(`/api/v1/shipments/${id}/classification/confirm`, {
      method: 'POST',
      body: JSON.stringify({ hs_code }),
    }),
  suggestClassification: (body: { product_text: string; chapter?: string; limit?: number }) =>
    request<ClassificationCandidates>('/api/v1/classification/candidates', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  checklistShipment: (id: string) =>
    request<Shipment>(`/api/v1/shipments/${id}/checklist`, { method: 'POST', body: '{}' }),
  updateDocumentStatus: (shipmentId: string, docCode: string, status: DocStatus) =>
    request<Shipment>(`/api/v1/shipments/${shipmentId}/documents/${docCode}`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),
  exportShipmentDraft: (
    shipmentId: string,
    kind: 'commercial_invoice' | 'packing_list' | 'checklist',
    asPdf = false,
  ) =>
    request<DraftExport>(
      `/api/v1/shipments/${shipmentId}/drafts/${kind}${asPdf ? '?as_pdf=true' : ''}`,
    ),
  uploadShipmentDocument: async (shipmentId: string, docCode: string, file: File) => {
    const body = new FormData();
    body.append('doc_code', docCode);
    body.append('file', file);
    const headers = await authHeaders(undefined, true);
    headers.delete('Content-Type');
    const res = await fetch(`${apiBase()}/api/v1/shipments/${shipmentId}/uploads`, {
      method: 'POST',
      headers,
      body,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err?.error?.message || `Upload failed (${res.status})`);
    }
    return res.json();
  },
  listSources: () => request<SourceDocument[]>('/api/v1/sources'),
  getSource: (id: string) => request<SourceDocument>(`/api/v1/sources/${id}`),
  transitionSource: (id: string, status: string, notes?: string) =>
    request<SourceDocument>(`/api/v1/sources/${id}/transition`, {
      method: 'POST',
      body: JSON.stringify({ status, notes: notes || null }),
    }),
  listDocumentRequirements: (opts?: { origin?: string; destination?: string; hs?: string }) => {
    const params = new URLSearchParams();
    if (opts?.origin) params.set('origin', opts.origin);
    if (opts?.destination) params.set('destination', opts.destination);
    if (opts?.hs) params.set('hs', opts.hs);
    const q = params.toString();
    return request<DocumentRequirement[]>(`/api/v1/document-requirements${q ? `?${q}` : ''}`);
  },
  documentWhyRequired: (opts: {
    doc_code: string;
    origin?: string;
    destination?: string;
    hs?: string;
  }) => {
    const params = new URLSearchParams({ doc_code: opts.doc_code });
    if (opts.origin) params.set('origin', opts.origin);
    if (opts.destination) params.set('destination', opts.destination);
    if (opts.hs) params.set('hs', opts.hs);
    return request<DocWhyRequired>(`/api/v1/document-requirements/why?${params}`);
  },
  runIngest: (body?: { source_key?: string; archive_path?: string; force?: boolean }) =>
    request<IngestionBatchDetail>('/api/v1/ingest/run', {
      method: 'POST',
      body: JSON.stringify(body || {}),
    }),
  listIngestBatches: () => request<IngestionBatchOut[]>('/api/v1/ingest/batches'),
  getIngestBatch: (id: string) => request<IngestionBatchDetail>(`/api/v1/ingest/batches/${id}`),
  getIngestBatchDiff: (id: string) =>
    request<IngestBatchDiff>(`/api/v1/ingest/batches/${encodeURIComponent(id)}/diff`),
  approveIngestBatch: (id: string, notes?: string) =>
    request<IngestionBatchDetail>(`/api/v1/ingest/batches/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ notes: notes || null }),
    }),
  promoteCbic: (notes?: string) =>
    request<PromoteCbicResult>('/api/v1/ingest/promote-cbic', {
      method: 'POST',
      body: JSON.stringify({ notes: notes || null }),
    }),
  rejectIngestBatch: (id: string, notes?: string) =>
    request<IngestionBatchDetail>(`/api/v1/ingest/batches/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ notes: notes || null }),
    }),
  listScenarios: () => request<Shipment[]>('/api/v1/scenarios'),
  createScenario: (body: Record<string, unknown>) =>
    request<Shipment>('/api/v1/scenarios', { method: 'POST', body: JSON.stringify(body) }),
  getScenarioWorkspace: (id: string) =>
    request<ShipmentWorkspace>(`/api/v1/scenarios/${id}/workspace`),
  updateScenario: (id: string, body: Record<string, unknown>) =>
    request<Shipment>(`/api/v1/scenarios/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  calculateScenario: (
    id: string,
    body?: { requested_mode?: 'estimate' | 'customs' | null },
  ) =>
    request<Shipment>(`/api/v1/scenarios/${id}/calculate`, {
      method: 'POST',
      body: JSON.stringify(body || {}),
    }),
  confirmScenarioHs: (id: string, hs_code: string) =>
    request<Shipment>(`/api/v1/scenarios/${id}/confirm-hs`, {
      method: 'POST',
      body: JSON.stringify({ hs_code }),
    }),
  listDataVersions: () => request<DataVersion[]>('/api/v1/data-versions'),
  ask: (body: {
    query?: string;
    shipment_id?: string;
    as_of?: string;
    orchestration_mode?: string;
    focus?: 'tariff' | 'shipment_gaps' | 'fta' | 'landed_cost';
    hs_code?: string;
    origin?: string;
    destination?: string;
  }) => request<AskResponse>('/api/v1/ask', { method: 'POST', body: JSON.stringify(body) }),
  runBenchmark: (modes?: string[]) => {
    const params = new URLSearchParams();
    for (const mode of modes || []) params.append('modes', mode);
    const q = params.toString();
    return request<Record<string, unknown>>(`/api/v1/eval/run${q ? `?${q}` : ''}`, {
      method: 'POST',
    });
  },
  listAgreements: () => request<TradeAgreement[]>('/api/v1/agreements'),
  checkFta: (body: {
    hs_code: string;
    origin?: string;
    destination?: string;
    as_of: string;
    agreement_id?: string;
  }) =>
    request<FtaCheckResult>('/api/v1/fta/check', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  retrieve: (q: string, hs?: string) => {
    const params = new URLSearchParams({ q });
    if (hs) params.set('hs', hs);
    return request<RetrievalHit[]>(`/api/v1/retrieve?${params}`);
  },
  listWatchlist: () => request<WatchlistItem[]>('/api/v1/watchlist'),
  addWatchlist: (body: {
    hs_code?: string;
    origin?: string;
    destination?: string;
    shipment_id?: string;
  }) => request<WatchlistItem>('/api/v1/watchlist', { method: 'POST', body: JSON.stringify(body) }),
  watchlistChanges: () => request<WatchlistChange[]>('/api/v1/watchlist/changes'),
  graphSummary: () => request<Record<string, unknown>>('/api/v1/graph/summary'),
  listSourceConnections: () =>
    request<SourceConnection[]>('/api/v1/source-connections'),
  getSourceFeedStatus: () =>
    request<SourceFeedStatus>('/api/v1/source-connections/feed-status'),
  fetchSourceConnection: (key: string, runIngest?: boolean) => {
    const q =
      runIngest === undefined ? '' : `?run_ingest=${runIngest ? 'true' : 'false'}`;
    return request<SourceFetchResult>(
      `/api/v1/source-connections/${encodeURIComponent(key)}/fetch${q}`,
      { method: 'POST' },
    );
  },
  runSourceFetchJob: (runIngest = false) =>
    request<JobRun>(`/api/v1/jobs/source-fetch?run_ingest=${runIngest}`, { method: 'POST' }),
};
