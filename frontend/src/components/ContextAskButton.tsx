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
