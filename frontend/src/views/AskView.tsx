import { useState } from 'react';
import { ApiError, api, type AskResponse, type CoverageMiss } from '../services/api';
import { CoverageMissPanel } from '../components/CoverageMissPanel';
import { InfoTip } from '../components/InfoTip';
import { ASK_USER_MODE_OPTIONS, askModeLabel, type OrchestrationMode } from '../content/askModes';

const DEMOS = [
  'What is the import duty for HS 6109.10 from Bangladesh to India?',
  'Can I claim preferential FTA duty for HS 6109.10 BD to IN under SAFTA?',
  'What proof of origin is needed for preferential cotton T-shirt imports?',
  'Calculate landed cost for HS 6109.10 BD to IN',
];

export function AskView() {
  const [query, setQuery] = useState(DEMOS[0]);
  const [asOf, setAsOf] = useState('2026-06-01');
  const [mode, setMode] = useState<OrchestrationMode>('adaptive');
  const [result, setResult] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [coverageMiss, setCoverageMiss] = useState<CoverageMiss | null>(null);
  const [showTech, setShowTech] = useState(false);

  const run = async () => {
    setError(null);
    setCoverageMiss(null);
    try {
      const res = await api.ask({ query, as_of: asOf, orchestration_mode: mode });
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

  return (
    <section className="panel-view">
      <p className="hint">
        Ask in plain language. Duties still come from TradeGraph’s rate tables and code — not
        invented by an LLM. <InfoTip id="nav_ask" />
      </p>
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
          {result.warnings.length > 0 && (
            <ul>
              {result.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          )}
          <details
            className="tech-details"
            open={showTech}
            onToggle={(e) => setShowTech((e.target as HTMLDetailsElement).open)}
          >
            <summary>
              Technical details <InfoTip id="tools_tokens_evidence" />
            </summary>
            <p className="muted">{result.policy_rationale}</p>
            <p>
              Execution: {result.route} · complexity {result.complexity_label} (
              {result.complexity_score}) · tools {result.tool_count}:{' '}
              {result.tools_invoked.join(', ') || '—'} · {result.latency_ms} ms · tokens{' '}
              {result.tokens_in}/{result.tokens_out} · mode{' '}
              <code>{result.orchestration_mode}</code>
            </p>
          </details>
        </div>
      )}
    </section>
  );
}
