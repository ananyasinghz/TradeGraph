/**
 * Human-readable confidence / rate-status badges (operator language).
 */

export type ConfidenceKind =
  | 'illustrative'
  | 'verified'
  | 'live_monitored'
  | 'demonstration'
  | 'approved_demo'
  | 'current'
  | 'historical'
  | 'needs_review'
  | 'official';

const LABELS: Record<ConfidenceKind, { label: string; detail: string; className: string }> = {
  illustrative: {
    label: 'Sample rate',
    detail: 'Sample / teaching data — not an official customs determination. Verify before filing.',
    className: 'confidence-badge confidence-demo',
  },
  verified: {
    label: 'Checked rate',
    detail:
      'A reviewer made these rates live in TradeGraph. Still not a substitute for licensed advice.',
    className: 'confidence-badge confidence-approved',
  },
  live_monitored: {
    label: 'Live official feed',
    detail:
      'Live official feed with freshness checks. Still verify against government sources before filing.',
    className: 'confidence-badge confidence-official',
  },
  demonstration: {
    label: 'Sample rate',
    detail: 'Sample / teaching data — not an official customs determination.',
    className: 'confidence-badge confidence-demo',
  },
  approved_demo: {
    label: 'Checked rate',
    detail: 'A reviewer made this rate live in the demo. Still not legal advice.',
    className: 'confidence-badge confidence-approved',
  },
  current: {
    label: 'Current rate',
    detail: 'Valid for the selected as-of date.',
    className: 'confidence-badge confidence-current',
  },
  historical: {
    label: 'Historical rate',
    detail: 'Valid only for an earlier period relative to today / your as-of date.',
    className: 'confidence-badge confidence-historical',
  },
  needs_review: {
    label: 'Needs broker review',
    detail: 'Uncertainty detected — verify with a broker before relying on this.',
    className: 'confidence-badge confidence-review',
  },
  official: {
    label: 'Official source',
    detail: 'Tied to an official-style source reference in this workspace.',
    className: 'confidence-badge confidence-official',
  },
};

export function mapDataQuality(
  quality: string | null | undefined,
): ConfidenceKind {
  if (quality === 'demo_verified' || quality === 'source_verified') return 'verified';
  if (quality === 'live_monitored') return 'live_monitored';
  return 'illustrative';
}

interface DataConfidenceBadgeProps {
  kind?: ConfidenceKind;
  dataQuality?: string | null;
  titleOverride?: string;
}

export function DataConfidenceBadge({
  kind,
  dataQuality,
  titleOverride,
}: DataConfidenceBadgeProps) {
  const resolved = kind || mapDataQuality(dataQuality);
  const meta = LABELS[resolved];
  return (
    <span className={meta.className} title={titleOverride || meta.detail}>
      {meta.label}
    </span>
  );
}
