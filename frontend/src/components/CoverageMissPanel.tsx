import type { CoverageMiss } from '../services/api';

interface CoverageMissPanelProps {
  miss: CoverageMiss;
}

export function CoverageMissPanel({ miss }: CoverageMissPanelProps) {
  const coverage = miss.dataset_coverage || {};
  return (
    <div className="coverage-miss" role="status" data-testid="coverage-miss">
      <h3>No approved coverage for this query</h3>
      <p>{miss.message}</p>
      <dl className="kv">
        <div>
          <dt>Origin</dt>
          <dd>{miss.origin}</dd>
        </div>
        <div>
          <dt>Destination</dt>
          <dd>{miss.destination}</dd>
        </div>
        <div>
          <dt>HS code</dt>
          <dd>{miss.hs_code || '—'}</dd>
        </div>
        <div>
          <dt>As of</dt>
          <dd>{miss.as_of || '—'}</dd>
        </div>
      </dl>
      {miss.possible_reasons?.length > 0 && (
        <>
          <h4>Possible reasons</h4>
          <ul>
            {miss.possible_reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </>
      )}
      {miss.next_actions?.length > 0 && (
        <>
          <h4>Next actions</h4>
          <ul>
            {miss.next_actions.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </>
      )}
      <p className="muted">
        Dataset coverage: {String(coverage.corridor || '—')} · chapters{' '}
        {Array.isArray(coverage.hs_chapters) ? coverage.hs_chapters.join(', ') : '—'} · approved
        rules {String(coverage.approved_tariff_rules ?? '—')} · last publish{' '}
        {String(coverage.last_published_label || coverage.last_published_update || 'none')}
      </p>
    </div>
  );
}
