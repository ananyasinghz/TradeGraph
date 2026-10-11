import { useEffect, useState } from 'react';
import {
  api,
  type DashboardAlert,
  type DashboardOut,
  type DashboardShipmentCard,
  type SnapshotDiff,
} from '../services/api';
import { CalcDiffPanel } from '../components/CalcDiffPanel';
import { InfoTip } from '../components/InfoTip';
import type { TradeView } from '../components/Sidebar';
import { OPERATOR } from '../content/operatorCopy';

interface DashboardViewProps {
  onCreateShipment?: () => void;
  onNavigate?: (view: TradeView) => void;
  onOpenShipment?: (shipmentId: string) => void;
}

type QueueFilter = 'all' | 'blocked' | 'alerts';

export function DashboardView({
  onCreateShipment,
  onOpenShipment,
}: DashboardViewProps) {
  const [data, setData] = useState<DashboardOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [calcDiff, setCalcDiff] = useState<SnapshotDiff | null>(null);
  const [queue, setQueue] = useState<QueueFilter>('all');

  const refresh = (q: QueueFilter = queue) =>
    api
      .getDashboard({ queue: q })
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : 'Dashboard failed'));

  useEffect(() => {
    void refresh(queue);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queue]);

  const markReviewed = async (impactId: string) => {
    try {
      await api.acknowledgeImpact(impactId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Acknowledge failed');
    }
  };

  const compareCalc = async (a: DashboardAlert) => {
    if (!a.previous_calculation_id || !a.new_calculation_id) {
      setError('No previous/new calculation linked on this alert.');
      return;
    }
    try {
      const d = await api.diffCalculations(a.previous_calculation_id, a.new_calculation_id);
      setCalcDiff(d);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Compare failed');
    }
  };

  return (
    <section className="panel-view">
      <h2>Home</h2>
      <p className="hint">{OPERATOR.homeHint}</p>
      {error && <p className="error-banner">{error}</p>}

      {onCreateShipment ? (
        <div className="quick-actions">
          <button type="button" className="primary-cta" onClick={onCreateShipment}>
            {OPERATOR.homeNewCase}
          </button>
        </div>
      ) : null}

      <div className="section-title-row">
        <h3>{OPERATOR.homeActiveCases}</h3>
      </div>
      <div className="chip-row" data-testid="dashboard-queue-filter">
        {(
          [
            ['all', OPERATOR.queueAll],
            ['blocked', OPERATOR.queueBlocked],
            ['alerts', OPERATOR.queueAlerts],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            data-testid={`queue-${id}`}
            className={`chip${queue === id ? ' chip-active' : ''}`}
            onClick={() => setQueue(id)}
          >
            {label}
          </button>
        ))}
      </div>
      {!data ? (
        <p className="muted">Loading…</p>
      ) : data.shipments.length === 0 ? (
        <p className="muted">
          {OPERATOR.homeNoCases}{' '}
          {onCreateShipment && (
            <button type="button" className="linkish" onClick={onCreateShipment}>
              {OPERATOR.homeCreateFirst}
            </button>
          )}
        </p>
      ) : (
        <div className="shipment-cards">
          {data.shipments.map((s: DashboardShipmentCard) => (
            <button
              key={s.id}
              type="button"
              className="shipment-card"
              onClick={() => onOpenShipment?.(s.id)}
            >
              <strong>
                {s.origin} → {s.destination}
              </strong>
              <div>{s.title}</div>
              <div className="chip-row">
                {s.chips.map((c) => (
                  <span key={c} className="status-chip">
                    {c}
                  </span>
                ))}
              </div>
              {(s.blocked_reasons?.length ?? 0) > 0 ? (
                <ul className="blocked-reasons" data-testid="blocked-reasons">
                  {s.blocked_reasons!.slice(0, 3).map((r) => (
                    <li key={r}>{r}</li>
                  ))}
                </ul>
              ) : null}
            </button>
          ))}
        </div>
      )}

      <div className="section-title-row">
        <h3>{OPERATOR.homeAlerts}</h3>
        <InfoTip id="watchlist_change" />
      </div>
      {!data || data.alerts.length === 0 ? (
        <p className="muted">No alerts right now.</p>
      ) : (
        <ul className="list">
          {data.alerts.map((a: DashboardAlert, idx) => (
            <li key={`${a.kind}-${a.impact_id || idx}`}>
              {a.kind === 'tariff_impact' ? (
                <div className="result-card" style={{ marginBottom: 8 }}>
                  <strong>{OPERATOR.homeDutyChange}</strong>
                  {a.hs_code ? (
                    <>
                      {' '}
                      · HS {a.hs_code}
                      {a.old_rate != null && a.new_rate != null
                        ? ` · BCD ${a.old_rate}% → ${a.new_rate}%`
                        : null}
                    </>
                  ) : null}
                  <div>{a.message}</div>
                  {a.duty_delta != null && (
                    <div>
                      Impact on “{a.shipment_title || 'clearance case'}”: duty{' '}
                      {Number(a.duty_delta) >= 0 ? '+' : ''}
                      {a.duty_delta} {a.currency || 'USD'}
                    </div>
                  )}
                  {a.recommended_action && (
                    <p className="muted">Recommended: {a.recommended_action}</p>
                  )}
                  {(a.source_document_id || a.effective_from) && (
                    <p className="muted">
                      Source {a.source_document_id || '—'}
                      {a.effective_from ? ` · effective ${a.effective_from}` : ''}
                    </p>
                  )}
                  <div className="toolbar">
                    {a.shipment_id && onOpenShipment && (
                      <button
                        type="button"
                        className="linkish"
                        onClick={() => onOpenShipment(a.shipment_id!)}
                      >
                        Open clearance case
                      </button>
                    )}
                    {a.previous_calculation_id && a.new_calculation_id ? (
                      <button type="button" className="linkish" onClick={() => void compareCalc(a)}>
                        Compare previous calc
                      </button>
                    ) : null}
                    {a.impact_id ? (
                      <button
                        type="button"
                        className="linkish"
                        onClick={() => void markReviewed(a.impact_id!)}
                      >
                        Mark reviewed
                      </button>
                    ) : null}
                    {a.shipment_id && onOpenShipment ? (
                      <button
                        type="button"
                        className="linkish"
                        onClick={() => onOpenShipment(a.shipment_id!)}
                      >
                        Check missing evidence
                      </button>
                    ) : null}
                  </div>
                </div>
              ) : (
                <>
                  <strong>
                    {a.severity === 'watchlist' || String(a.severity).toLowerCase().includes('watch')
                      ? OPERATOR.homeDutyChange
                      : a.severity}
                  </strong>
                  : {a.message}
                  {a.shipment_id && onOpenShipment && (
                    <>
                      {' '}
                      <button
                        type="button"
                        className="linkish"
                        onClick={() => onOpenShipment(a.shipment_id!)}
                      >
                        Open clearance case
                      </button>
                    </>
                  )}
                </>
              )}
            </li>
          ))}
        </ul>
      )}

      {calcDiff && <CalcDiffPanel diff={calcDiff} onClose={() => setCalcDiff(null)} />}
    </section>
  );
}
