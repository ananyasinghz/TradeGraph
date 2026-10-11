import { useState } from 'react';
import { api, type AskResponse } from '../services/api';

type AskFocus = 'tariff' | 'shipment_gaps' | 'fta' | 'landed_cost';

interface ContextAskButtonProps {
  label: string;
  focus: AskFocus;
  shipmentId?: string;
  hsCode?: string;
  asOf?: string;
  origin?: string;
  destination?: string;
}

export function ContextAskButton({
  label,
  focus,
  shipmentId,
  hsCode,
  asOf,
  origin = 'BD',
  destination = 'IN',
}: ContextAskButtonProps) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      const response = await api.ask({
        query: '',
        focus,
        shipment_id: shipmentId,
        hs_code: hsCode,
        as_of: asOf,
        origin,
        destination,
        orchestration_mode: 'adaptive',
      });
      setResult(response);
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : 'Ask failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="context-ask">
      <button type="button" disabled={busy} onClick={() => void run()}>
        {busy ? 'Asking…' : label}
      </button>
      {error && <p className="error-banner">{error}</p>}
      {result && (
        <div className="context-ask-result">
          <p>{result.answer}</p>
          <details className="tech-details">
            <summary>Technical details</summary>
            <p className="muted">
              {result.route} · tools {result.tools_invoked.join(', ') || '—'} · evidence{' '}
              {result.evidence_score}
            </p>
          </details>
        </div>
      )}
    </div>
  );
}

interface CaseAskPanelProps {
  shipmentId: string;
  hsCode?: string;
  asOf?: string;
  origin?: string;
  destination?: string;
}

/** Free-form Ask bound to the open shipment (loads case context for grounded Ollama). */
export function CaseAskPanel({
  shipmentId,
  hsCode,
  asOf,
  origin = 'BD',
  destination = 'IN',
}: CaseAskPanelProps) {
  const [query, setQuery] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    const q = query.trim();
    if (!q) return;
    setBusy(true);
    setError(null);
    try {
      const response = await api.ask({
        query: q,
        shipment_id: shipmentId,
        hs_code: hsCode,
        as_of: asOf,
        origin,
        destination,
        orchestration_mode: 'adaptive',
      });
      setResult(response);
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : 'Ask failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="context-ask case-ask-panel" data-testid="case-ask-panel">
      <h4>Ask about this case</h4>
      <p className="muted">
        Uses this shipment’s HS, corridor, and product text. With Ollama on, answers are short
        grounded explanations — rates still come from TradeGraph tools.
      </p>
      <textarea
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        rows={2}
        placeholder="e.g. Can we claim preferential duty on this shipment?"
      />
      <div className="toolbar">
        <button type="button" disabled={busy || !query.trim()} onClick={() => void run()}>
          {busy ? 'Asking…' : 'Ask'}
        </button>
      </div>
      {error && <p className="error-banner">{error}</p>}
      {result && (
        <div className="context-ask-result">
          <p>{result.answer}</p>
          <details className="tech-details">
            <summary>Technical details</summary>
            <p className="muted">
              {result.route} · tools {result.tools_invoked.join(', ') || '—'} ·{' '}
              {result.tools_invoked.includes('llm_explain') ? 'Ollama wrap' : 'tools only'}
            </p>
          </details>
        </div>
      )}
    </div>
  );
}
