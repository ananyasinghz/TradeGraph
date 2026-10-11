import { useCallback, useEffect, useState } from 'react';
import { api, type SystemStatus } from '../services/api';
import {
  OPERATOR,
  productModeTitle,
  sourceStatusOperator,
} from '../content/operatorCopy';
import { useOperatorPrefs } from '../content/useOperatorPrefs';

export const STATUS_REFRESH_EVENT = 'tradegraph-status-refresh';

export function requestStatusRefresh(): void {
  window.dispatchEvent(new Event(STATUS_REFRESH_EVENT));
}

function formatApprovedAt(iso: string | null): string {
  if (!iso) return 'None yet';
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  } catch {
    return iso;
  }
}

export function EnvironmentBanner() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [whyOpen, setWhyOpen] = useState(false);
  const { showTech } = useOperatorPrefs();

  const load = useCallback(() => {
    void api
      .getSystemStatus()
      .then(setStatus)
      .catch((err) => setError(err instanceof Error ? err.message : 'Status unavailable'));
  }, []);

  useEffect(() => {
    load();
    const onRefresh = () => load();
    window.addEventListener(STATUS_REFRESH_EVENT, onRefresh);
    return () => window.removeEventListener(STATUS_REFRESH_EVENT, onRefresh);
  }, [load]);

  if (error) {
    return (
      <aside className="environment-banner environment-banner--error" role="status">
        <strong>{OPERATOR.bannerError}</strong> {error}
      </aside>
    );
  }

  if (!status) {
    return (
      <aside className="environment-banner environment-banner--loading" role="status">
        {OPERATOR.bannerLoading}
      </aside>
    );
  }

  const chapters = status.hs_chapters?.length
    ? status.hs_chapters.map((c) => `Chapter ${c}`).join(', ')
    : `Chapter ${status.hs_chapter}`;
  const rules = status.active_rules || {
    total: status.active_tariff_rule_count,
    approved: status.approved_tariff_rule_count,
    illustrative: status.illustrative_tariff_rule_count,
  };

  return (
    <aside
      className={`environment-banner environment-banner--${status.product_mode}`}
      role="status"
      aria-live="polite"
      data-source-kind={status.source_connection_kind || 'none'}
      data-effective-status={status.effective_product_status || 'illustrative'}
    >
      <div className="environment-banner__title">
        {productModeTitle(status.product_mode)}
        {status.mode_forced ? OPERATOR.bannerForced : null}
        {status.effective_product_status ? (
          <span className="muted">
            {' '}
            ·{' '}
            {status.effective_product_status === 'verified'
              ? 'Checked rates'
              : status.effective_product_status === 'mixed'
                ? 'Mixed rates'
                : 'Sample rates'}
          </span>
        ) : null}
      </div>
      <ul className="environment-banner__grid">
        <li>
          <span className="muted">{OPERATOR.bannerCorridor}</span>
          <strong>{status.corridor}</strong>
        </li>
        <li>
          <span className="muted">{OPERATOR.bannerProducts}</span>
          <strong>{chapters}</strong>
        </li>
        <li>
          <span className="muted">{OPERATOR.bannerDutyRates}</span>
          <strong>
            {OPERATOR.bannerDutyRatesValue(rules.approved, rules.illustrative, rules.total)}
          </strong>
        </li>
        <li>
          <span className="muted">{OPERATOR.bannerLastUpdate}</span>
          <strong>
            {formatApprovedAt(status.last_approved_at)}
            {status.last_approved_label ? ` · ${status.last_approved_label}` : ''}
          </strong>
          {status.latest_source_batch?.label && !status.last_approved_at ? (
            <div className="muted">
              Latest batch: {status.latest_source_batch.label} (
              {status.latest_source_batch.status || 'unknown'})
            </div>
          ) : null}
        </li>
        <li>
          <span className="muted">{OPERATOR.bannerSourceStatus}</span>
          <strong data-testid="source-connection-label">
            {sourceStatusOperator(status.source_connection_label)}
          </strong>
        </li>
        <li data-testid="filing-calc-status">
          <span className="muted">{OPERATOR.bannerFilingCalc}</span>
          <strong data-testid="filing-calc-available">
            {status.customs_mode_available ? OPERATOR.bannerFilingYes : OPERATOR.bannerFilingNo}
          </strong>
          {status.customs_mode_hint ? (
            <div className="muted" data-testid="filing-calc-hint">
              {status.customs_mode_hint}
            </div>
          ) : null}
          {!status.customs_mode_available && (status.customs_mode_blockers?.length ?? 0) > 0 ? (
            <ul className="muted" data-testid="filing-calc-blockers">
              {status.customs_mode_blockers!.map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
          ) : null}
        </li>
      </ul>

      {status.trust_notice ? (
        <p className="environment-banner__notices" data-testid="trust-notice">
          {status.trust_notice}
        </p>
      ) : null}

      <button
        type="button"
        className="linkish environment-banner__why"
        onClick={() => setWhyOpen((v) => !v)}
        aria-expanded={whyOpen}
      >
        {whyOpen ? 'Hide' : OPERATOR.bannerWhyRates}
      </button>
      {whyOpen || showTech ? (
        <div className="environment-banner__why-body muted">
          <p>
            Connection detail: {status.official_source_connection}
            {status.live_feed_reason ? ` · ${status.live_feed_reason}` : ''}
          </p>
          {status.latest_source_batch ? (
            <p>
              Latest source batch: {status.latest_source_batch.label || status.latest_source_batch.id}{' '}
              · {status.latest_source_batch.status}
            </p>
          ) : null}
          {status.notices.length > 0 && <p>{status.notices.join(' · ')}</p>}
          {status.mode_lock_reason && <p>{status.mode_lock_reason}</p>}
          {showTech && <p>{status.disclaimer}</p>}
        </div>
      ) : null}

      {!showTech && !status.trust_notice && status.notices.length > 0 && !whyOpen ? (
        <p className="environment-banner__notices">{status.notices.join(' · ')}</p>
      ) : null}
      {!showTech && !whyOpen && (
        <p className="environment-banner__disclaimer muted">{OPERATOR.disclaimerShort}</p>
      )}
    </aside>
  );
}
