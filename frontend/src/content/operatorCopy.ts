/**
 * Operator-facing UI copy for clearing agents / supply-chain users.
 * Keep engineering terms out of day-to-day surfaces.
 */

export const DOC_LABELS: Record<string, string> = {
  commercial_invoice: 'Commercial invoice',
  packing_list: 'Packing list',
  bill_of_lading: 'Bill of lading / airway bill',
  certificate_of_origin: 'Certificate of origin (CoO)',
  fibre_composition: 'Fibre composition declaration',
  composition: 'Product composition',
};

export function docLabel(code: string): string {
  return DOC_LABELS[code] || code.replace(/_/g, ' ');
}

export const OPERATOR = {
  connectionOnline: (corridor: string) => `Connection: Online · ${corridor}`,
  connectionOffline:
    'Connection: Offline — ask IT to start the TradeGraph service',
  connectionChecking: 'Connection: Checking…',

  bannerTitleSample: 'Data you can use today · Sample rates',
  bannerTitleWorking: 'Data you can use today · Working rates',
  bannerForced: ' (requested working rates; sample data still in use)',
  bannerCorridor: 'Trade lane',
  bannerProducts: 'Products covered',
  bannerDutyRates: 'Duty rates',
  bannerDutyRatesValue: (approved: number, sample: number, active: number) =>
    `${active} total (${approved} checked · ${sample} sample)`,
  bannerLastUpdate: 'Last rate update',
  bannerSourceStatus: 'Source status',
  bannerFilingCalc: 'Filing-ready calc',
  bannerFilingYes: 'Available when freight & insurance are filled in',
  bannerFilingNo: 'Not available yet',
  bannerWhyRates: 'Why these rates?',
  bannerError: 'Can’t reach TradeGraph right now — ask IT to start the service and refresh.',
  bannerLoading: 'Loading rate status…',

  badgeSample: 'Sample rate',
  badgeChecked: 'Checked rate',
  badgeLive: 'Live official feed',
  badgeSampleDetail:
    'Sample / teaching data — not an official customs determination. Verify before filing.',
  badgeCheckedDetail:
    'A reviewer made these rates live in TradeGraph (checked / source-verified). Still not a substitute for licensed advice.',
  badgeLiveDetail:
    'Live official feed with freshness checks. Still verify against government sources before filing.',

  nav: {
    home: 'Home',
    cases: 'Clearance cases',
    duty: 'Duty rates',
    landed: 'Landed cost',
    fta: 'Preferential / FTA',
    papers: 'Shipping papers',
    alerts: 'Rate alerts',
    ask: 'Ask a question',
    glossary: 'Glossary',
    admin: 'Rate library (admin)',
    research: 'Research',
    adminSection: 'Admin',
  },

  homeHint: 'What am I working on, what changed, and what should I do next?',
  homeNewCase: 'New clearance case',
  homeLookupDuty: 'Look up duty',
  homeLanded: 'Estimate landed cost',
  homeAsk: 'Ask a question',
  homePapers: 'Check papers',
  homeActiveCases: 'Active clearance cases',
  homeNoCases: 'No clearance cases yet.',
  homeCreateFirst: 'Create your first clearance case',
  homeAlerts: 'Compliance alerts',
  homeDutyChange: 'Duty change',
  homeDataStatus: 'Data status',

  welcomeTitle: 'What can TradeGraph help you do?',
  welcomeClearing:
    'Clearance workspace for Bangladesh → India knitwear (HS chapter 61). Check duty, papers, and landed cost — not a substitute for licensed customs advice.',
  welcomeStudent:
    'Decision-support demo for Bangladesh → India apparel (HS chapter 61). Includes research tools for students.',
  welcomeCapsClearing: [
    'Classify the product (HS code)',
    'Check import duty for BD → IN',
    'Estimate landed cost to clear',
    'See if preferential / FTA duty may apply',
    'Prepare shipping papers checklists',
    'Get alerts when duty rates change',
  ],
  welcomeCapsStudent: [
    "Find a product's HS code",
    'Check import duty for BD → IN',
    'Calculate landed cost',
    'Check trade agreement (FTA) benefits',
    'Prepare shipment document checklists',
    'Compare Ask routing modes in Research',
  ],
  welcomeCta: 'Start a clearance case',
  welcomeRoute: 'Trade lane for this workspace:',

  caseCreateTitle: 'New clearance case',
  caseListTitle: 'Clearance cases',
  caseCreateCta: 'Create clearance case',
  caseTitle: 'Case title',
  caseProduct: 'Product description',
  caseHs: 'Working HS code',
  caseAsOf: 'Rate as-of date',
  caseInvoice: 'Invoice / customs value',
  caseFreight: 'Freight',
  caseInsurance: 'Insurance',
  caseEmpty: 'Select or create a clearance case to open the guided workspace.',
  caseProgress: 'Steps',
  caseSteps: ['Classify product', 'Check duty', 'Cost', 'Papers', 'Preferential'] as const,
  caseTabs: {
    overview: 'Overview',
    product: 'Product',
    classify: 'Classification',
    tariff: 'Duty',
    fta: 'Preferential',
    cost: 'Cost',
    docs: 'Papers',
    evidence: 'Evidence',
    ask: 'Ask',
    activity: 'Activity',
  },
  navSettings: 'Settings',
  navLegal: 'Legal',
  queueAll: 'All cases',
  queueBlocked: 'Blocked',
  queueAlerts: 'Alerts',
  nextActionBar: 'Next action',
  downloadPack: 'Download clearance pack',
  openCase: 'Open case',
  linkCase: 'Link a clearance case',
  searchPlaceholder: 'Search cases, HS, papers…',
  caseEstimate: 'Estimate',
  caseVerified: 'Verified estimate',
  caseFiling: 'Filing preparation',
  caseFilingBlocked:
    'Need checked duty rates and freight + insurance filled in. Use Estimate, or ask admin to make rates live first.',
  caseSaveInputs: 'Save valuation inputs',
  caseHistory: 'Saved duty calcs',
  caseDiff: 'Compare earlier calcs',
  caseShowTech: 'Show technical details',
  caseHideTech: 'Hide technical details',
  caseBuildChecklist: 'Build papers checklist',
  caseReadyBroker: 'Needs broker review',

  tariffHint: 'Trade lane BD→IN · sample rates until an admin makes checked rates live.',
  tariffQuality: 'Rate status',
  tariffSourceDetails: 'Source details',

  calcLead: 'What will this shipment cost to clear?',
  calcEstimate: 'Estimate',
  calcVerified: 'Verified estimate',
  calcFiling: 'Filing preparation',

  sourcesWizardTitle: 'Update duty rates from official notice',
  sourcesWizardSteps: [
    'Load the notice archive',
    'Review proposed rates',
    'Make rates live',
  ] as const,
  sourcesPromote: 'Make demo fixture rates live',
  sourcesLoadOnly: 'Load demo fixture only',
  sourcesTechLog: 'Technical log',
  sourcesAfter:
    'After rates are live: open Duty rates — cotton T-shirts (6109.10) should show Checked rate; filing-ready calc unlocks when freight and insurance are on a clearance case.',

  disclaimerShort:
    'TradeGraph helps you prepare clearance decisions. Always verify classifications, duties, and preferential claims against official sources (and a licensed professional where needed).',
  disclaimerLong:
    'TradeGraph is decision-support software for trade compliance workflows. Classifications, duties, preferential claims, and document packs require verification against official sources and, where appropriate, a licensed customs professional. Sample or illustrative rates are not legal determinations.',
  footerTechToggle: 'Show technical details',
  welcomePersonaLabel: 'Learning persona (UX only)',
  welcomeServerRole: 'Your access role comes from sign-in (viewer / operator / reviewer / admin).',
} as const;

export function sourceStatusOperator(label: string | null | undefined): string {
  if (!label) return 'No duty rate source connected';
  if (label === 'Verified source') return 'Checked rates in use';
  if (label === 'Curated demonstration source') return 'Sample archive connected';
  if (label === 'Live monitored') return 'Live official feed';
  if (label === 'Official source not connected') return 'No duty rate source connected';
  return label;
}

export function productModeTitle(mode: string): string {
  return mode === 'operational' ? OPERATOR.bannerTitleWorking : OPERATOR.bannerTitleSample;
}

export const ROLE_KEY = 'tradegraph.userRole';
export const TECH_DETAILS_KEY = 'tradegraph.showTechnicalDetails';

export type OperatorRole = 'importer' | 'exporter' | 'clearing_agent' | 'student';

export function readOperatorRole(): OperatorRole {
  try {
    const saved = localStorage.getItem(ROLE_KEY) as OperatorRole | null;
    if (
      saved === 'importer' ||
      saved === 'exporter' ||
      saved === 'clearing_agent' ||
      saved === 'student'
    ) {
      return saved;
    }
  } catch {
    /* ignore */
  }
  return 'clearing_agent';
}

export function readShowTechnicalDetails(): boolean {
  try {
    return localStorage.getItem(TECH_DETAILS_KEY) === '1';
  } catch {
    return false;
  }
}

export function writeShowTechnicalDetails(on: boolean): void {
  try {
    localStorage.setItem(TECH_DETAILS_KEY, on ? '1' : '0');
  } catch {
    /* ignore */
  }
}

export function isResearchRole(role: OperatorRole): boolean {
  return role === 'student';
}
