/**
 * Research Lab: benchmarks and orchestration baselines (not for operators).
 */
import { useState } from 'react';
import { api } from '../services/api';
import { InfoTip } from '../components/InfoTip';
import { RESEARCH_MODE_OPTIONS } from '../content/askModes';
import { DutyCoveragePanel } from '../sources/DutyCoveragePanel';

export function ResearchLabView() {
  const [modes, setModes] = useState<string[]>(['adaptive', 'direct_lookup', 'fixed_multi']);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const toggle = (id: string) => {
    setModes((prev) => (prev.includes(id) ? prev.filter((m) => m !== id) : [...prev, id]));
  };

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      setResult(await api.runBenchmark(modes));
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : 'Benchmark failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel-view">
      <p className="hint">
        Research tools for routing comparison, token/latency baselines, and ablation. Day-to-day
        clearance work stays under Clearance cases / Ask a question.{' '}
        <InfoTip id="orchestration_mode" />
      </p>
      <div className="section-title-row">
        <h3>Routing comparison modes</h3>
      </div>
      <ul className="list">
        {RESEARCH_MODE_OPTIONS.map((o) => (
          <li key={o.id}>
            <label className="label-with-tip">
              <input
                type="checkbox"
                checked={modes.includes(o.id)}
                onChange={() => toggle(o.id)}
              />{' '}
              <strong>{o.label}</strong> <code>{o.id}</code>
            </label>
            <div className="muted">{o.hint}</div>
          </li>
        ))}
      </ul>
      <div className="toolbar">
        <button type="button" onClick={() => void run()} disabled={busy || modes.length === 0}>
          {busy ? 'Running…' : 'Run /eval benchmark'}
        </button>
      </div>
      {error && <p className="error-banner">{error}</p>}
      {result && (
        <div className="result-card">
          <h3>Benchmark summary</h3>
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
      <div data-testid="tariff-coverage-matrix">
        <DutyCoveragePanel />
      </div>
    </section>
  );
}
