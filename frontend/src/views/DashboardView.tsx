import { useEffect, useState } from 'react';
import {
  api,
  type DashboardAlert,
  type DashboardOut,
  type DashboardShipmentCard,
} from '../services/api';
import { InfoTip } from '../components/InfoTip';
import type { TradeView } from '../components/Sidebar';
import { OPERATOR } from '../content/operatorCopy';

interface DashboardViewProps {
  onCreateShipment?: () => void;
  onNavigate?: (view: TradeView) => void;
  onOpenShipment?: (shipmentId: string) => void;
}

export function DashboardView({
  onCreateShipment,
  onNavigate,
  onOpenShipment,
}: DashboardViewProps) {
  const [data, setData] = useState<DashboardOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = () =>
    api
      .getDashboard()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : 'Dashboard failed'));

  useEffect(() => {
    void refresh();
  }, []);

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
      window.alert(`${d.summary}\n${JSON.stringify(d.fields, null, 2)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Compare failed');
    }
  };

  return (
    <section className="panel-view">
      <h2>Home</h2>
      <p className="hint">
        {OPERATOR.homeHint} <InfoTip id="shipment_workspace" />
      </p>
      {error && <p className="error-banner">{error}</p>}

      <div className="section-title-row">
        <h3>Quick actions</h3>
      </div>
      <div className="quick-actions">
        {onCreateShipment && (
          <button type="button" className="primary-cta" onClick={onCreateShipment}>
            {OPERATOR.homeNewCase}
          </button>
        )}
        <button type="button" onClick={() => onNavigate?.('tariffs')}>
          {OPERATOR.homeLookupDuty}
        </button>
        <button type="button" onClick={() => onNavigate?.('calculator')}>
          {OPERATOR.homeLanded}
        </button>
        <button type="button" onClick={() => onNavigate?.('ask')}>
          {OPERATOR.homeAsk}
        </button>
        <button type="button" onClick={() => onNavigate?.('documents')}>
          {OPERATOR.homePapers}
        </button>
      </div>

      <div className="section-title-row">
        <h3>{OPERATOR.homeActiveCases}</h3>
        <InfoTip id="shipment_workspace" />
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

      <div className="section-title-row">
        <h3>{OPERATOR.homeDataStatus}</h3>
        <InfoTip id="corridor_scope" />
      </div>
      {data && (
        <div className="data-status-block" data-testid="home-data-status">
          <p>
            <strong>Trade lane:</strong> {data.data_status.corridor}, HS chapter{' '}
            {data.data_status.hs_chapter}
          </p>
          <p>
            <strong>Rates:</strong> {data.data_status.dataset_type}
          </p>
          {data.data_status.active_rules ? (
            <p>
              <strong>Active duty rates:</strong>{' '}
              {data.data_status.active_rules.total} total (
              {data.data_status.active_rules.approved} checked ·{' '}
              {data.data_status.active_rules.illustrative} sample)
            </p>
          ) : null}
          <p>
            <strong>Last checked-rate update:</strong>{' '}
            {data.data_status.last_approved_at
              ? `${data.data_status.last_approved_label} · ${data.data_status.last_approved_at}`
              : 'None yet (sample data only)'}
          </p>
          {data.data_status.latest_source_batch?.label ? (
            <p>
              <strong>Latest source batch:</strong> {data.data_status.latest_source_batch.label} ·{' '}
              {data.data_status.latest_source_batch.status || '—'}
            </p>
          ) : null}
          <p className="muted">{data.data_status.trust_notice || data.data_status.note}</p>
        </div>
      )}
    </section>
  );
}
