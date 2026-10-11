import { InfoTip } from '../components/InfoTip';
import { OPERATOR } from '../content/operatorCopy';

export function DemoFixturePanel({
  canPublish,
  busy,
  onPromote,
  onLoadOnly,
}: {
  canPublish: boolean;
  busy: boolean;
  onPromote: () => void;
  onLoadOnly: () => void;
}) {
  return (
    <details className="result-card" data-testid="demo-fixture-panel">
      <summary>
        <strong>Demo fixture lane</strong> — curated Q3 JSON (not live CBIC)
      </summary>
      <p className="muted">
        Use this only for local demos. It loads{' '}
        <code>cbic_notification_2026_q3</code> from disk — never a courier.cbic.gov.in fetch.
      </p>
      <ol className="list">
        {OPERATOR.sourcesWizardSteps.map((step, i) => (
          <li key={step}>
            <strong>
              {i + 1}. {step}
            </strong>
          </li>
        ))}
      </ol>
      <div className="toolbar">
        {canPublish ? (
          <button
            type="button"
            className="primary-cta"
            disabled={busy}
            onClick={() => void onPromote()}
            data-testid="sources-promote"
          >
            {OPERATOR.sourcesPromote}
          </button>
        ) : (
          <p className="muted" data-testid="sources-promote-denied">
            Promote requires an authenticated reviewer or admin (or local demo publish flag).
          </p>
        )}
        <button type="button" disabled={busy} onClick={() => void onLoadOnly()}>
          {OPERATOR.sourcesLoadOnly}
        </button>
        <InfoTip id="ingest_run" />
      </div>
      <p className="muted">{OPERATOR.sourcesAfter}</p>
    </details>
  );
}
