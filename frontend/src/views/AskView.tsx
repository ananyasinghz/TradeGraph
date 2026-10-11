import { useEffect, useState } from 'react';
import { ApiError, api, type AskResponse, type CoverageMiss, type Shipment } from '../services/api';
import { CoverageMissPanel } from '../components/CoverageMissPanel';
import { DisclaimerFooter } from '../components/DisclaimerFooter';
import { InfoTip } from '../components/InfoTip';
import { ASK_USER_MODE_OPTIONS, askModeLabel, type OrchestrationMode } from '../content/askModes';
import { OPERATOR } from '../content/operatorCopy';

const DEMOS = [
  'What is the import duty for HS 6109.10 from Bangladesh to India?',
  'Can I claim preferential FTA duty for HS 6109.10 BD to IN under SAFTA?',
  'What proof of origin is needed for preferential cotton T-shirt imports?',
  'Calculate landed cost for HS 6109.10 BD to IN',
];

const NEXT_ACTION_LABELS: Record<string, string> = {
  upload_coo: 'Upload certificate of origin',
  confirm_hs: 'Confirm HS classification',
  add_freight: 'Add freight & insurance',
  open_fta: 'Review preferential / FTA',
  none: 'No follow-up needed',
};

interface AskViewProps {
  onOpenShipment?: (shipmentId: string) => void;
}

export function AskView({ onOpenShipment }: AskViewProps) {
  const [query, setQuery] = useState(DEMOS[0]);
  const [asOf, setAsOf] = useState('2026-06-01');
  const [mode, setMode] = useState<OrchestrationMode>('adaptive');
  const [result, setResult] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [coverageMiss, setCoverageMiss] = useState<CoverageMiss | null>(null);
  const [showTech, setShowTech] = useState(false);
  const [shipments, setShipments] = useState<Shipment[]>([]);
  const [linkedShipmentId, setLinkedShipmentId] = useState('');

  useEffect(() => {
    void api
      .listShipments('open')
      .then(setShipments)
      .catch(() => setShipments([]));
  }, []);

  const run = async () => {
    setError(null);
    setCoverageMiss(null);
    try {
      const res = await api.ask({
        query,
        as_of: asOf,
        orchestration_mode: mode,
        shipment_id: linkedShipmentId || undefined,
      });
      setResult(res);
      const miss = res.result?.coverage_miss as CoverageMiss | undefined;
      if (miss?.message) setCoverageMiss(miss);
    } catch (err) {
      setResult(null);
      if (err instanceof ApiError && err.coverageMiss) {
        setCoverageMiss(err.coverageMiss);
        setError(null);
      } else {
        setError(err instanceof Error ? err.message : 'Ask failed');
      }
    }
  };

  const modeMeta = ASK_USER_MODE_OPTIONS.find((o) => o.id === mode);

  const handleNextAction = (code: string | null | undefined) => {
    if (!code || code === 'none') return;
    if (!linkedShipmentId) {
      setError('Link a clearance case first to act on the next step.');
      return;
    }
    onOpenShipment?.(linkedShipmentId);
  };

  return (
    <section className="panel-view">
      <p className="hint">
        Ask in plain language. Duties still come from TradeGraph’s rate tables and code — not
        invented by an LLM. Link a clearance case for grounded answers with product context.{' '}
        <InfoTip id="nav_ask" />
      </p>
      <div className="result-card" data-testid="ask-link-case">
        <label>
          {OPERATOR.linkCase}
          <select
            value={linkedShipmentId}
            onChange={(e) => setLinkedShipmentId(e.target.value)}
            data-testid="ask-shipment-select"
          >
            <option value="">No case linked (general ask)</option>
            {shipments.map((s) => (
              <option key={s.id} value={s.id}>
                {s.title} · {s.hs_code_working || 'no HS'}
              </option>
            ))}
          </select>
        </label>
        {linkedShipmentId && onOpenShipment ? (
          <button
            type="button"
            className="linkish"
            style={{ marginLeft: 8 }}
            onClick={() => onOpenShipment(linkedShipmentId)}
          >
            {OPERATOR.openCase}
          </button>
        ) : null}
      </div>
      <div className="chip-row">
        {DEMOS.map((d) => (
          <button key={d} type="button" className="chip" onClick={() => setQuery(d)}>
            {d.slice(0, 42)}…
          </button>
        ))}
      </div>
      <textarea value={query} onChange={(e) => setQuery(e.target.value)} rows={3} />
      <div className="toolbar">
        <label>
          <span className="label-with-tip">
            As of <InfoTip id="as_of" />
          </span>
          <input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} />
        </label>
        <label>
          <span className="label-with-tip">
            Answer style <InfoTip id="orchestration_mode" />
          </span>
          <select value={mode} onChange={(e) => setMode(e.target.value as OrchestrationMode)}>
            {ASK_USER_MODE_OPTIONS.map((o) => (
              <option key={o.id} value={o.id}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <button type="button" onClick={() => void run()}>
          Ask
        </button>
      </div>
      {modeMeta && <p className="muted">{modeMeta.hint}</p>}
      {error && <p className="error-banner">{error}</p>}
      {coverageMiss && <CoverageMissPanel miss={coverageMiss} />}
      {result && (
        <div className="result-card">
          <p>
            <strong>{askModeLabel(result.orchestration_mode)}</strong>
            {result.decision ? (
              <>
                {' '}
                · Decision: <strong>{result.decision.replaceAll('_', ' ')}</strong>
              </>
            ) : null}
            {result.source_status ? (
              <>
                {' '}
                · Source: {result.source_status}
              </>
            ) : null}
          </p>
          <p>{result.answer}</p>
          {(result.assumptions || []).length > 0 && (
            <>
              <h4>Assumptions</h4>
              <ul>
                {result.assumptions?.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            </>
          )}
          {result.next_action && (
            <p>
              <strong>Next action:</strong> {result.next_action}
            </p>
          )}
          {result.next_action_code && result.next_action_code !== 'none' ? (
            <div className="toolbar" data-testid="ask-next-action">
              <button
                type="button"
                className="chip chip-active"
                onClick={() => handleNextAction(result.next_action_code)}
              >
                {NEXT_ACTION_LABELS[result.next_action_code] || result.next_action_code}
              </button>
            </div>
          ) : null}
          {result.warnings.length > 0 && (
            <ul>
              {result.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          )}
          <label className="tech-details-toggle muted">
            <input
              type="checkbox"
              checked={showTech}
              onChange={(e) => setShowTech(e.target.checked)}
            />{' '}
            Show technical details
          </label>
          {showTech && (
            <details open className="tech-details">
              <summary>Route / tools</summary>
              <p className="muted">
                {result.route} · {result.tools_invoked.join(', ') || '—'} · {result.latency_ms}ms
              </p>
            </details>
          )}
        </div>
      )}
      <DisclaimerFooter compact />
    </section>
  );
}
