import { validationLabel } from './sourceHelpers';

export function QuarantineSummary({
  okCount,
  errCount,
  eligibleCount,
  quarantineErrors,
}: {
  okCount: number;
  errCount: number;
  eligibleCount: number;
  quarantineErrors: string[];
}) {
  const reasons = [...new Set(quarantineErrors.map(validationLabel))];
  if (okCount > 0) {
    return (
      <div data-testid="publish-eligibility-banner">
        <p className="hint">
          Publishing {eligibleCount || okCount} eligible row
          {(eligibleCount || okCount) === 1 ? '' : 's'}; {errCount} quarantined row
          {errCount === 1 ? '' : 's'} will be skipped and will not become operational rates.
        </p>
        {reasons.length > 0 ? (
          <p className="muted" data-testid="quarantine-reasons">
            Quarantine reasons: {reasons.join('; ')}
          </p>
        ) : null}
      </div>
    );
  }
  return (
    <p className="error-banner" data-testid="publish-eligibility-banner">
      No eligible rows to publish (ok = 0). Quarantined rows stay skipped
      {reasons.length ? ` (${reasons.join('; ')})` : ''}.
    </p>
  );
}
