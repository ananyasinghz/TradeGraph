const LABELS: Record<string, string> = {
  source_verified: 'Verified',
  verified: 'Verified',
  curated_official_backed: 'Curated',
  curated: 'Curated',
  illustrative: 'Illustrative',
  missing: 'Missing',
  needs_review: 'Needs review',
};

export function ComponentQualityBadge({
  quality,
  testId,
  title,
}: {
  quality: string | null | undefined;
  testId?: string;
  title?: string;
}) {
  const raw = (quality || 'missing').toLowerCase();
  const label = LABELS[raw] || raw.replaceAll('_', ' ');
  return (
    <span className="badge" data-testid={testId} title={title || label}>
      {label}
    </span>
  );
}
