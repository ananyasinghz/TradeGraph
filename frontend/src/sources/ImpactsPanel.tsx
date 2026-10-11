import { useCallback, useEffect, useState } from 'react';
import { api, type ScenarioImpact } from '../services/api';

export function ImpactsPanel({ compact = false }: { compact?: boolean }) {
  const [rows, setRows] = useState<ScenarioImpact[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const list = await api.listImpacts();
    setRows(list.filter((r) => !r.acknowledged_at));
  }, []);

  useEffect(() => {
    void refresh().catch((err) =>
      setError(err instanceof Error ? err.message : 'Failed to load impacts'),
    );
  }, [refresh]);

  const acknowledge = async (id: string) => {
    setBusy(true);
    try {
      await api.acknowledgeImpact(id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Acknowledge failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="result-card" data-testid="impacts-panel">
      <h3>{compact ? 'Rate-change impacts' : 'Shipment impacts from published rate changes'}</h3>
      {error ? <p className="error-banner">{error}</p> : null}
      {rows.length === 0 ? (
        <p className="muted" data-testid="impacts-empty">
          No applicable-rate changes — provenance-only refreshes do not alert.
        </p>
      ) : (
        <ul className="list">
          {rows.map((r) => (
            <li key={r.id} data-testid={`impact-row-${r.id}`}>
              <strong>
                HS {r.hs_code}
              </strong>{' '}
              · BCD {String(r.old_rate)}% → {String(r.new_rate)}%
              {r.duty_delta != null ? ` · duty Δ ${String(r.duty_delta)} ${r.currency}` : ''}
              {r.landed_delta != null
                ? ` · landed Δ ${String(r.landed_delta)} ${r.currency}`
                : ''}
              <div className="muted">{r.summary}</div>
              <div className="muted">Action: {r.recommended_action}</div>
              {r.component_deltas && Object.keys(r.component_deltas).length > 0 ? (
                <div className="muted">
                  Components:{' '}
                  {Object.entries(r.component_deltas)
                    .map(([k, v]) => {
                      const d = v as { old?: number; new?: number };
                      return `${k} ${d.old}→${d.new}`;
                    })
                    .join(', ')}
                </div>
              ) : null}
              <div className="toolbar">
                <a className="chip" href={`#/shipments?focus=${r.shipment_id}`}>
                  Open case
                </a>
                <button
                  type="button"
                  className="chip"
                  disabled={busy}
                  onClick={() => void acknowledge(r.id)}
                >
                  Mark reviewed
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
