/**
 * Plain-English help copy for InfoTip + Glossary.
 * Keep each entry to 1–2 short sentences.
 */

export type HelpKey =
  | 'hs_code'
  | 'origin'
  | 'as_of'
  | 'bcd'
  | 'sws'
  | 'igst'
  | 'landed_cost'
  | 'invoice_value'
  | 'fta'
  | 'mfn'
  | 'preferential_vs_mfn'
  | 'roo'
  | 'certificate_of_origin'
  | 'data_quality'
  | 'illustrative'
  | 'demo_verified'
  | 'orchestration_mode'
  | 'adaptive'
  | 'direct_lookup'
  | 'fixed_multi'
  | 'always_llm'
  | 'tools_tokens_evidence'
  | 'ingest_run'
  | 'validation_error'
  | 'ingest_approve'
  | 'checksum'
  | 'data_version'
  | 'watchlist_change'
  | 'supersession'
  | 'shipment_workspace'
  | 'working_hs'
  | 'calculate_shipment'
  | 'checklist_build'
  | 'doc_templates'
  | 'shipment_checklists'
  | 'api_status'
  | 'corridor_scope'
  | 'disclaimer'
  | 'nav_dashboard'
  | 'nav_shipments'
  | 'nav_tariffs'
  | 'nav_calculator'
  | 'nav_agreements'
  | 'nav_watchlist'
  | 'nav_documents'
  | 'nav_sources'
  | 'nav_research'
  | 'nav_ask'
  | 'nav_glossary';

export type HelpGroup = 'trade' | 'app' | 'ask';

export interface HelpEntry {
  key: HelpKey;
  title: string;
  body: string;
  group: HelpGroup;
}

export const HELP_ENTRIES: HelpEntry[] = [
  {
    key: 'hs_code',
    title: 'HS code',
    body: 'A product classification number used by customs. Example: 6109.10 means cotton T-shirts (knitted).',
    group: 'trade',
  },
  {
    key: 'origin',
    title: 'Origin / destination',
    body: 'Where the goods ship from and to. This prototype is locked to Bangladesh (BD) → India (IN).',
    group: 'trade',
  },
  {
    key: 'as_of',
    title: 'As of date',
    body: 'The date we pretend is “today” when looking up which tariff rate was in force.',
    group: 'trade',
  },
  {
    key: 'bcd',
    title: 'BCD',
    body: 'Basic Customs Duty — the main import duty percentage applied on the assessable value.',
    group: 'trade',
  },
  {
    key: 'sws',
    title: 'SWS',
    body: 'Social Welfare Surcharge — an extra charge calculated as a percentage of BCD in this prototype.',
    group: 'trade',
  },
  {
    key: 'igst',
    title: 'IGST',
    body: 'Integrated GST — tax on imports in this calculator, applied after duty components.',
    group: 'trade',
  },
  {
    key: 'landed_cost',
    title: 'Landed cost',
    body: 'Rough total of goods value plus duties and taxes. Computed by code, never by an AI guess.',
    group: 'trade',
  },
  {
    key: 'invoice_value',
    title: 'Invoice / CIF value',
    body: 'The commercial value of the shipment used as the starting number for duty math.',
    group: 'trade',
  },
  {
    key: 'fta',
    title: 'FTA',
    body: 'Free Trade Agreement — a deal that can lower duty if rules of origin and paperwork are met.',
    group: 'trade',
  },
  {
    key: 'mfn',
    title: 'MFN rate',
    body: 'Most-Favoured-Nation rate — the standard duty when no preferential FTA claim applies.',
    group: 'trade',
  },
  {
    key: 'preferential_vs_mfn',
    title: 'Preferential vs MFN',
    body: 'Preferential is the lower FTA rate if eligible; MFN is the normal rate without that claim.',
    group: 'trade',
  },
  {
    key: 'roo',
    title: 'Rules of origin (RoO)',
    body: 'Conditions that prove goods “originate” in a partner country so preferential duty can apply.',
    group: 'trade',
  },
  {
    key: 'certificate_of_origin',
    title: 'Certificate of origin',
    body: 'Paperwork that supports an FTA claim. Missing it usually blocks preferential duty.',
    group: 'trade',
  },
  {
    key: 'data_quality',
    title: 'Rate status',
    body: 'Sample rate = teaching data. Checked rate = a reviewer made it live in TradeGraph. Always verify before filing.',
    group: 'app',
  },
  {
    key: 'illustrative',
    title: 'Sample rate',
    body: 'Teaching / sample data — not an official legal determination. Always verify for real shipments.',
    group: 'app',
  },
  {
    key: 'demo_verified',
    title: 'Checked rate',
    body: 'A reviewer loaded an official notice and made these rates live in the app (still not a substitute for official advice).',
    group: 'app',
  },
  {
    key: 'watchlist_change',
    title: 'Duty change alerts',
    body: 'Alerts when a watched product’s duty rate is replaced by a newer one for this trade lane.',
    group: 'app',
  },
  {
    key: 'supersession',
    title: 'Duty rate replaced',
    body: 'A newer duty rate version replaced an older active rate for the same HS and trade lane.',
    group: 'app',
  },
  {
    key: 'shipment_workspace',
    title: 'Clearance case',
    body: 'One file for a clearance enquiry: product, HS, date, value, duty calc, and shipping papers.',
    group: 'app',
  },
  {
    key: 'working_hs',
    title: 'Working HS',
    body: 'The HS code you are using for this clearance case while you refine classification.',
    group: 'app',
  },
  {
    key: 'calculate_shipment',
    title: 'Duty & landed cost',
    body: 'Runs the same duty math as Landed cost and saves it on this clearance case.',
    group: 'app',
  },
  {
    key: 'checklist_build',
    title: 'Build papers checklist',
    body: 'Builds a shipping-papers list from the requirements for this trade lane and HS.',
    group: 'app',
  },
  {
    key: 'doc_templates',
    title: 'Required papers',
    body: 'Documents this trade lane may need (commercial invoice, packing list, certificate of origin, etc.).',
    group: 'app',
  },
  {
    key: 'shipment_checklists',
    title: 'Papers progress',
    body: 'Per-case progress after you build a papers checklist. Open a clearance case to work the list.',
    group: 'app',
  },
  {
    key: 'ingest_run',
    title: 'Load notice',
    body: 'Loads a saved customs notice, extracts proposed rates, and checks them — nothing goes live yet.',
    group: 'app',
  },
  {
    key: 'validation_error',
    title: 'Rate check failed',
    body: 'A proposed rate failed hard checks (wrong trade lane, unknown HS, bad rate). It will not go live.',
    group: 'app',
  },
  {
    key: 'ingest_approve',
    title: 'Make rates live',
    body: 'Nothing becomes an active duty rate until a human clicks Make rates live. Invalid rows stay skipped.',
    group: 'app',
  },
  {
    key: 'checksum',
    title: 'File fingerprint',
    body: 'A fingerprint of the archived notice so you can tell which exact source file was reviewed (admin detail).',
    group: 'app',
  },
  {
    key: 'data_version',
    title: 'Rate version',
    body: 'A published batch label after rates go live — records what changed and when.',
    group: 'app',
  },
  {
    key: 'api_status',
    title: 'Connection',
    body: 'Shows whether TradeGraph is reachable and which trade lane is active (BD→IN knitwear).',
    group: 'app',
  },
  {
    key: 'corridor_scope',
    title: 'Trade lane scope',
    body: 'This workspace covers Bangladesh → India and HS chapter 61 (knit apparel).',
    group: 'app',
  },
  {
    key: 'disclaimer',
    title: 'Disclaimer',
    body: 'TradeGraph is decision-support software, not licensed customs advice. Always verify against official sources.',
    group: 'app',
  },
  {
    key: 'orchestration_mode',
    title: 'Ask mode (research)',
    body: 'How Ask chooses tools: everyday adaptive path vs research baselines that always look up or fan out.',
    group: 'ask',
  },
  {
    key: 'adaptive',
    title: 'Everyday Ask',
    body: 'Picks the minimum tools needed for the question — usually fastest for simple duty lookups.',
    group: 'ask',
  },
  {
    key: 'direct_lookup',
    title: 'direct_lookup',
    body: 'Research baseline that always runs a structured tariff lookup only — for comparing cost vs everyday Ask.',
    group: 'ask',
  },
  {
    key: 'fixed_multi',
    title: 'fixed_multi',
    body: 'Research baseline that always runs the full multi-tool workflow, even for simple questions.',
    group: 'ask',
  },
  {
    key: 'always_llm',
    title: 'always_llm',
    body: 'Research baseline that simulates always using an LLM path. Duty numbers stay code-based.',
    group: 'ask',
  },
  {
    key: 'tools_tokens_evidence',
    title: 'Tools / tokens / evidence',
    body: 'Research metrics: how many tools ran, estimated token cost, and how grounded the answer is.',
    group: 'ask',
  },
  {
    key: 'nav_dashboard',
    title: 'Home',
    body: 'Overview: open clearance cases, duty-change alerts, and next actions.',
    group: 'app',
  },
  {
    key: 'nav_shipments',
    title: 'Clearance cases',
    body: 'Create and manage clearance cases — duty, preferential claims, landed cost, and papers.',
    group: 'app',
  },
  {
    key: 'nav_tariffs',
    title: 'Duty rates',
    body: 'Look up duty rates by product HS code for the BD→IN trade lane.',
    group: 'app',
  },
  {
    key: 'nav_calculator',
    title: 'Landed cost',
    body: 'Estimate what this shipment will cost to clear from invoice value and duty — no chat required.',
    group: 'app',
  },
  {
    key: 'nav_agreements',
    title: 'Preferential / FTA',
    body: 'Check whether a preferential (FTA) duty might apply and what evidence is needed.',
    group: 'app',
  },
  {
    key: 'nav_watchlist',
    title: 'Rate alerts',
    body: 'Track HS codes and get alerts when duty rates change.',
    group: 'app',
  },
  {
    key: 'nav_documents',
    title: 'Shipping papers',
    body: 'Browse required papers and see checklist progress across clearance cases.',
    group: 'app',
  },
  {
    key: 'nav_sources',
    title: 'Rate library (admin)',
    body: 'Load an official notice, review proposed rates, and make them live.',
    group: 'app',
  },
  {
    key: 'nav_research',
    title: 'Research',
    body: 'Benchmark Ask routing modes, tokens, and latency. Not part of day-to-day clearance work.',
    group: 'app',
  },
  {
    key: 'nav_ask',
    title: 'Ask a question',
    body: 'Ask in plain language; TradeGraph uses the same duty and papers tools as the forms.',
    group: 'ask',
  },
  {
    key: 'nav_glossary',
    title: 'Glossary',
    body: 'All plain-English definitions used by the ⓘ tips in one place.',
    group: 'app',
  },
];

export const HELP_COPY: Record<HelpKey, string> = Object.fromEntries(
  HELP_ENTRIES.map((e) => [e.key, e.body]),
) as Record<HelpKey, string>;

export const HELP_TITLE: Record<HelpKey, string> = Object.fromEntries(
  HELP_ENTRIES.map((e) => [e.key, e.title]),
) as Record<HelpKey, string>;
