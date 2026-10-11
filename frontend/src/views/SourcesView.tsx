import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  api,
  type DataVersion,
  type IngestBatchDiff,
  type IngestionBatchDetail,
  type IngestionBatchOut,
  type SourceConnection,
  type SourceDocument,
  type SourceFeedStatus,
} from '../services/api';
import { InfoTip } from '../components/InfoTip';
import { requestStatusRefresh } from '../components/EnvironmentBanner';
import { useOperatorPrefs } from '../content/useOperatorPrefs';
import { useAuth } from '../auth/AuthProvider';
import { ConnectionCard } from '../sources/ConnectionCard';
import { DemoFixturePanel } from '../sources/DemoFixturePanel';
import { DutyCoveragePanel } from '../sources/DutyCoveragePanel';
import { FeedHealthCard } from '../sources/FeedHealthCard';
import { ImpactsPanel } from '../sources/ImpactsPanel';
import { QuarantineSummary } from '../sources/QuarantineSummary';
import {
  DEMO_FIXTURE_KEY,
  sourceClassBadge,
  validationLabel,
  VERIFIED_CBIC_CH61_KEY,
} from '../sources/sourceHelpers';

interface SourcesViewProps {
  pendingOnlyDefault?: boolean;
}

function eligibilityForChange(
  change: Record<string, unknown>,
  quarantinedIds: Set<string>,
): 'Eligible' | 'Quarantined' | 'Unchanged' {
  const id = String(change.proposal_id || '');
  if (quarantinedIds.has(id)) return 'Quarantined';
  if (String(change.change_type) === 'unchanged') return 'Unchanged';
  return 'Eligible';
}

export function SourcesView({ pendingOnlyDefault = false }: SourcesViewProps) {
  const { whoami } = useAuth();
  const roleOk = whoami?.role === 'reviewer' || whoami?.role === 'admin';
  const canPublish =
    roleOk &&
    (whoami?.authenticated === true ||
      (whoami?.auth_enabled === false && whoami?.allow_anonymous_publish === true));
  const demoSession = whoami != null && whoami.auth_enabled === false;
  const anonymousPublishBlocked =
    demoSession && whoami?.allow_anonymous_publish !== true;

  const [rows, setRows] = useState<SourceDocument[]>([]);
  const [batches, setBatches] = useState<IngestionBatchOut[]>([]);
  const [versions, setVersions] = useState<DataVersion[]>([]);
  const [connections, setConnections] = useState<SourceConnection[]>([]);
  const [feedStatus, setFeedStatus] = useState<SourceFeedStatus | null>(null);
  const [selected, setSelected] = useState<IngestionBatchDetail | null>(null);
  const [batchDiff, setBatchDiff] = useState<IngestBatchDiff | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pendingOnly, setPendingOnly] = useState(pendingOnlyDefault);
  const { showTech } = useOperatorPrefs();
  const visibleBatches = pendingOnly
    ? batches.filter((b) => b.status === 'pending_review')
    : batches;

  const liveOfficial = connections.filter((c) => c.lane === 'live_official');
  const otherConnections = connections.filter((c) => c.lane !== 'live_official' && c.lane !== 'demo_fixture');

  const okCount = Number(selected?.validation_summary?.ok ?? 0);
  const errCount = Number(selected?.validation_summary?.error ?? 0);
  const canMakeLive =
    canPublish &&
    selected?.status === 'pending_review' &&
    okCount > 0 &&
    !busy;

  const refresh = useCallback(async () => {
    const [sources, batchList, versionList, connectionList, feed] = await Promise.all([
      api.listSources(),
      api.listIngestBatches(),
      api.listDataVersions(),
      api.listSourceConnections(),
      api.getSourceFeedStatus(),
    ]);
    setRows(sources);
    setBatches(batchList);
    setVersions(versionList);
    setConnections(connectionList);
    setFeedStatus(feed);
  }, []);

  useEffect(() => {
    void refresh().catch((err) => setError(err instanceof Error ? err.message : 'Failed'));
  }, [refresh]);

  const runIngest = async () => {
    setBusy(true);
    setError(null);
    try {
      const batch = await api.runIngest({ source_key: DEMO_FIXTURE_KEY, force: true });
      setSelected(batch);
      setBatchDiff(await api.getIngestBatchDiff(batch.id));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Load notice failed');
    } finally {
      setBusy(false);
    }
  };

  const fetchConnection = async (key: string) => {
    setBusy(true);
    setError(null);
    try {
      const result = await api.fetchSourceConnection(key);
      await refresh();
      if (result.ingest_batch_id) {
        setSelected(await api.getIngestBatch(result.ingest_batch_id));
        setBatchDiff(await api.getIngestBatchDiff(result.ingest_batch_id));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Fetch failed');
    } finally {
      setBusy(false);
    }
  };

  const openBatch = async (id: string) => {
    setError(null);
    try {
      setSelected(await api.getIngestBatch(id));
      setBatchDiff(await api.getIngestBatchDiff(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Load failed');
    }
  };

  const approve = async () => {
    if (!selected || !canMakeLive) return;
    setBusy(true);
    try {
      const next = await api.approveIngestBatch(selected.id, 'Approved in UI');
      setSelected(next);
      setBatchDiff(await api.getIngestBatchDiff(next.id));
      await refresh();
      requestStatusRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Make rates live failed');
    } finally {
      setBusy(false);
    }
  };

  const reject = async () => {
    if (!selected || !canPublish) return;
    setBusy(true);
    try {
      const next = await api.rejectIngestBatch(selected.id, 'Rejected in UI');
      setSelected(next);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Reject failed');
    } finally {
      setBusy(false);
    }
  };

  const promote = async () => {
    if (!canPublish) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.promoteCbic('Approved via demo fixture promote');
      await refresh();
      if (result.batch_id) {
        setSelected(await api.getIngestBatch(result.batch_id));
        setBatchDiff(await api.getIngestBatchDiff(result.batch_id));
      }
      requestStatusRefresh();
      window.alert(result.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Promote failed');
    } finally {
      setBusy(false);
    }
  };

  const quarantinedIds = useMemo(() => {
    const ids = new Set<string>();
    for (const q of batchDiff?.quarantined || []) {
      ids.add(String(q.proposal_id || ''));
    }
    return ids;
  }, [batchDiff]);

  const reviewRows = useMemo(() => {
    if (!batchDiff) return [];
    const fromChanges = batchDiff.changes.map((c) => ({
      kind: 'change' as const,
      hs: String(c.hs_code || ''),
      corridor: `${String(c.origin || '')}→${String(c.destination || '')}`,
      oldRate: c.previous ? (c.previous as { rate?: number }).rate : undefined,
      proposedRate: c.proposed ? (c.proposed as { rate?: number }).rate : undefined,
      components: c.proposed
        ? JSON.stringify((c.proposed as { duty_components?: unknown }).duty_components || {})
        : '—',
      effective: batchDiff.effective_from || '—',
      validation: 'ok',
      eligibility: eligibilityForChange(c, quarantinedIds),
      errors: [] as string[],
      changeType: String(c.change_type || ''),
    }));
    const fromQuarantine = (batchDiff.quarantined || []).map((q) => ({
      kind: 'quarantine' as const,
      hs: String(q.hs_code || ''),
      corridor: '—',
      oldRate: undefined as number | undefined,
      proposedRate: (q.payload as { rate?: number } | undefined)?.rate,
      components: JSON.stringify(
        (q.payload as { duty_components?: unknown } | undefined)?.duty_components || {},
      ),
      effective: batchDiff.effective_from || '—',
      validation: 'error',
      eligibility: 'Quarantined' as const,
      errors: Array.isArray(q.errors) ? (q.errors as string[]) : [],
      changeType: 'quarantined',
    }));
    return [...fromChanges, ...fromQuarantine];
  }, [batchDiff, quarantinedIds]);

  const eligiblePublishCount = reviewRows.filter((r) => r.eligibility === 'Eligible').length;
  const quarantineErrors = reviewRows.flatMap((r) => r.errors);

  return (
    <section className="panel-view">
      <p className="hint">
        Official sources first: refresh the verified CBIC Chapter 61 IGST document, review the
        batch, then make rates live. Demo fixtures are collapsed below — they are not a live
        government feed. <InfoTip id="ingest_run" />
      </p>
      {demoSession ? (
        <p className="muted" data-testid="sources-demo-session">
          {anonymousPublishBlocked
            ? 'Demo session (auth off) — publishing disabled. Sign in as reviewer or set TRADE_ALLOW_ANONYMOUS_PUBLISH=true for local demo only.'
            : 'Local demo publish enabled (auth off + anonymous publish flag) — not for shared environments.'}
        </p>
      ) : null}
      {error && <p className="error-banner">{error}</p>}

      {feedStatus ? <FeedHealthCard feedStatus={feedStatus} /> : null}

      <div className="section-title-row">
        <h3>Live / official sources</h3>
      </div>
      <p className="muted" data-testid="sources-fetch-honesty">
        Refresh on an official document connection fetches the remote URL (allowlisted host),
        archives bytes, and opens a review batch — it does not reread the curated Q3 JSON fixture.
      </p>
      <div data-testid="live-official-connections">
        {liveOfficial.map((c) => (
          <ConnectionCard
            key={c.id}
            connection={c}
            feedStatus={feedStatus}
            busy={busy}
            onRefresh={(key) => void fetchConnection(key)}
          />
        ))}
        {liveOfficial.length === 0 ? (
          <p className="muted">
            Verified CBIC connection ({VERIFIED_CBIC_CH61_KEY}) should appear after service start.
          </p>
        ) : null}
      </div>

      {otherConnections.length > 0 ? (
        <>
          <div className="section-title-row">
            <h3>Other archives</h3>
          </div>
          {otherConnections.map((c) => (
            <ConnectionCard
              key={c.id}
              connection={c}
              feedStatus={feedStatus}
              busy={busy}
              onRefresh={(key) => void fetchConnection(key)}
            />
          ))}
        </>
      ) : null}

      <DemoFixturePanel
        canPublish={canPublish}
        busy={busy}
        onPromote={() => void promote()}
        onLoadOnly={() => void runIngest()}
      />

      <DutyCoveragePanel />
      <ImpactsPanel />

      <div className="section-title-row">
        <h3>Rate update batches</h3>
        <InfoTip id="ingest_approve" />
      </div>
      <div className="chip-row" data-testid="ingest-pending-filter">
        <button
          type="button"
          className={`chip${!pendingOnly ? ' chip-active' : ''}`}
          onClick={() => setPendingOnly(false)}
        >
          All batches
        </button>
        <button
          type="button"
          className={`chip${pendingOnly ? ' chip-active' : ''}`}
          data-testid="ingest-pending-only"
          onClick={() => setPendingOnly(true)}
        >
          Pending review only
        </button>
      </div>
      <table className="data-table">
        <thead>
          <tr>
            <th>Source</th>
            <th>Status</th>
            <th>
              <span className="label-with-tip">
                Checks <InfoTip id="validation_error" />
              </span>
            </th>
            {showTech ? (
              <th>
                <span className="label-with-tip">
                  Fingerprint <InfoTip id="checksum" />
                </span>
              </th>
            ) : null}
            <th />
          </tr>
        </thead>
        <tbody>
          {visibleBatches.map((b) => (
            <tr key={b.id}>
              <td>
                {b.source_key}{' '}
                <span className="chip">{sourceClassBadge(b.source_key, connections)}</span>
              </td>
              <td>{b.status}</td>
              <td>
                ok {String(b.validation_summary?.ok ?? '—')} / err{' '}
                {String(b.validation_summary?.error ?? '—')}
              </td>
              {showTech ? <td className="muted">{b.checksum.slice(0, 12)}…</td> : null}
              <td>
                <button type="button" className="chip" onClick={() => void openBatch(b.id)}>
                  Review rates
                </button>
              </td>
            </tr>
          ))}
          {visibleBatches.length === 0 && (
            <tr>
              <td colSpan={showTech ? 5 : 4} className="muted">
                {pendingOnly
                  ? 'No pending batches — switch to All batches or refresh an official source.'
                  : 'No batches yet — refresh a live/official source first.'}
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {selected && (
        <div className="result-card" data-testid="ingest-review-panel">
          <p>
            <strong>{selected.title}</strong> · {selected.status} · effective{' '}
            {selected.effective_from || '—'}{' '}
            <span className="chip">{sourceClassBadge(selected.source_key, connections)}</span>
          </p>
          <p className="muted">{selected.publisher}</p>
          {(() => {
            const cls = sourceClassBadge(selected.source_key, connections);
            const conn = connections.find((c) => c.key === selected.source_key);
            if (cls === 'curated_fixture') {
              return (
                <p className="muted" data-testid="curated-illustrative-notice">
                  Illustrative curated fixture — not legal advice; rate deltas are not an official
                  CBIC amendment.
                </p>
              );
            }
            if (cls === 'official_document' || cls === 'live_http' || cls === 'published_verified') {
              return (
                <div className="result-card" data-testid="official-evidence-panel">
                  <h4>Official evidence</h4>
                  <p className="muted">
                    URL: {conn?.last_final_url || conn?.document_url || conn?.source_url || '—'}
                  </p>
                  <p className="muted">
                    Retrieved:{' '}
                    {conn?.last_success_at
                      ? new Date(conn.last_success_at).toLocaleString()
                      : '—'}
                  </p>
                  <p className="muted">
                    Checksum:{' '}
                    {conn?.last_checksum ? `${conn.last_checksum.slice(0, 16)}…` : '—'}
                  </p>
                  <p className="muted">Archive: {conn?.last_archive_path || '—'}</p>
                  {conn?.honesty_label ? <p className="muted">{conn.honesty_label}</p> : null}
                </div>
              );
            }
            return null;
          })()}
          {selected.status === 'pending_review' && (
            <>
              <QuarantineSummary
                okCount={okCount}
                errCount={errCount}
                eligibleCount={eligiblePublishCount}
                quarantineErrors={quarantineErrors}
              />
              <div className="toolbar">
                {canPublish ? (
                  <button
                    type="button"
                    disabled={!canMakeLive}
                    onClick={() => void approve()}
                    data-testid="make-rates-live"
                  >
                    Make rates live
                  </button>
                ) : (
                  <p className="muted" data-testid="make-rates-live-denied">
                    Sign in as reviewer to publish.
                  </p>
                )}
                <InfoTip id="ingest_approve" />
                {canPublish ? (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void reject()}
                    data-testid="reject-batch"
                  >
                    Reject
                  </button>
                ) : null}
              </div>
            </>
          )}
          {batchDiff && (
            <div className="result-card" data-testid="ingest-batch-diff">
              <h4>Proposed changes</h4>
              <p className="muted">
                Affected HS: {batchDiff.affected_hs_codes.join(', ') || '—'}
                {showTech ? ` · checksum ${batchDiff.checksum.slice(0, 12)}…` : ''}
              </p>
              <table className="data-table" data-testid="review-eligibility-table">
                <thead>
                  <tr>
                    <th>HS</th>
                    <th>Corridor</th>
                    <th>Old rate</th>
                    <th>Proposed rate</th>
                    <th>Duty components</th>
                    <th>Effective</th>
                    <th>Validation</th>
                    <th>Eligibility</th>
                  </tr>
                </thead>
                <tbody>
                  {reviewRows.map((r, idx) => (
                    <tr key={`${r.hs}-${r.eligibility}-${idx}`}>
                      <td>{r.hs || '—'}</td>
                      <td>{r.corridor}</td>
                      <td>{r.oldRate != null ? `${r.oldRate}%` : '—'}</td>
                      <td>{r.proposedRate != null ? `${r.proposedRate}%` : '—'}</td>
                      <td className="muted">{r.components.slice(0, 80)}</td>
                      <td>{r.effective}</td>
                      <td>
                        {r.validation}
                        {r.errors.length > 0 ? (
                          <div className="muted">
                            {r.errors.map(validationLabel).join('; ')}
                          </div>
                        ) : null}
                      </td>
                      <td>
                        <span
                          className="chip"
                          data-testid={`eligibility-${r.eligibility.toLowerCase()}`}
                        >
                          {r.eligibility}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {reviewRows.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="muted">
                        No tariff proposals in this batch.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          )}
          {showTech ? (
            <details className="tech-log">
              <summary>Proposal payloads</summary>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Kind</th>
                    <th>Checks</th>
                    <th>Publish</th>
                    <th>Payload</th>
                  </tr>
                </thead>
                <tbody>
                  {selected.proposals.map((p) => (
                    <tr key={p.id}>
                      <td>{p.kind}</td>
                      <td>
                        {p.validation_status}
                        {p.validation_errors.length > 0 && (
                          <div className="muted">
                            {p.validation_errors.map(validationLabel).join(', ')}
                          </div>
                        )}
                      </td>
                      <td>{p.publish_status}</td>
                      <td>
                        <code>{JSON.stringify(p.payload).slice(0, 120)}</code>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          ) : null}
        </div>
      )}

      <h3>Published sources</h3>
      <table className="data-table">
        <thead>
          <tr>
            {showTech ? <th>ID</th> : null}
            <th>Title</th>
            <th>Status</th>
            {showTech ? <th>Fingerprint</th> : null}
            <th>Class</th>
            <th>Effective</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const keyGuess = (r.id || '').replace(/^src_/, '');
            const cls = sourceClassBadge(keyGuess, connections, true);
            return (
              <tr key={r.id}>
                {showTech ? <td>{r.id}</td> : null}
                <td>
                  {r.title}
                  {r.notes && <div className="muted">{r.notes}</div>}
                  {r.honesty_notice && <div className="muted">{r.honesty_notice}</div>}
                  {cls === 'curated_fixture' ? (
                    <div className="muted">Illustrative / not legal advice</div>
                  ) : null}
                </td>
                <td>{r.status}</td>
                {showTech ? (
                  <td className="muted">{r.checksum ? `${r.checksum.slice(0, 12)}…` : '—'}</td>
                ) : null}
                <td>
                  <span className="chip">{cls}</span>
                  {r.live_government_feed ? '' : ' · not a live feed'}
                </td>
                <td>{r.effective_from}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <div className="section-title-row">
        <h3>Data versions</h3>
        <InfoTip id="data_version" />
      </div>
      <ul className="list" data-testid="data-versions-timeline">
        {versions.map((v) => {
          const linkedBatch = batches.find((b) => b.id === v.batch_id);
          const counts = v.record_counts || {};
          const rates = Number(counts.rates ?? counts.tariff_rates ?? 0);
          return (
            <li key={v.id} className="result-card">
              <strong>{v.label}</strong>
              <ol className="list">
                <li>
                  Retrieved / archived
                  {linkedBatch?.created_at
                    ? ` · ${new Date(linkedBatch.created_at).toLocaleString()}`
                    : ''}
                </li>
                <li>
                  Batch created
                  {v.batch_id ? ` · ${v.batch_id.slice(0, 12)}…` : ' · —'}
                  {linkedBatch ? ` (${linkedBatch.source_key})` : ''}
                </li>
                <li>
                  Approved → published · {new Date(v.published_at).toLocaleString()}
                </li>
                <li>
                  Rate changes summary: {rates || '—'} rate record
                  {rates === 1 ? '' : 's'}
                  {linkedBatch?.source_key
                    ? ` · class ${sourceClassBadge(linkedBatch.source_key, connections, true)}`
                    : ''}
                </li>
              </ol>
              {showTech ? (
                <details className="tech-log">
                  <summary>Tech details</summary>
                  <p className="muted">Fingerprint: {v.fingerprint}</p>
                  <p className="muted">Counts: {JSON.stringify(v.record_counts)}</p>
                  {v.notes ? <p className="muted">{v.notes}</p> : null}
                </details>
              ) : null}
            </li>
          );
        })}
        {versions.length === 0 && (
          <li className="muted">No published rate versions yet.</li>
        )}
      </ul>
    </section>
  );
}
