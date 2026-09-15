import { useCallback, useEffect, useState } from 'react';
import {
  api,
  type DataVersion,
  type IngestionBatchDetail,
  type IngestionBatchOut,
  type SourceConnection,
  type SourceDocument,
} from '../services/api';
import { InfoTip } from '../components/InfoTip';
import { requestStatusRefresh } from '../components/EnvironmentBanner';
import { OPERATOR } from '../content/operatorCopy';
import { useOperatorPrefs } from '../content/useOperatorPrefs';

export function SourcesView() {
  const [rows, setRows] = useState<SourceDocument[]>([]);
  const [batches, setBatches] = useState<IngestionBatchOut[]>([]);
  const [versions, setVersions] = useState<DataVersion[]>([]);
  const [connections, setConnections] = useState<SourceConnection[]>([]);
  const [selected, setSelected] = useState<IngestionBatchDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { showTech } = useOperatorPrefs();

  const refresh = useCallback(async () => {
    const [sources, batchList, versionList, connectionList] = await Promise.all([
      api.listSources(),
      api.listIngestBatches(),
      api.listDataVersions(),
      api.listSourceConnections(),
    ]);
    setRows(sources);
    setBatches(batchList);
    setVersions(versionList);
    setConnections(connectionList);
  }, []);

  useEffect(() => {
    void refresh().catch((err) => setError(err instanceof Error ? err.message : 'Failed'));
  }, [refresh]);

  const runIngest = async () => {
    setBusy(true);
    setError(null);
    try {
      const batch = await api.runIngest({ source_key: 'cbic_notification_2026_q3', force: true });
      setSelected(batch);
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
      await api.fetchSourceConnection(key, false);
      await refresh();
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
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Load failed');
    }
  };

  const approve = async () => {
    if (!selected) return;
    setBusy(true);
    try {
      const next = await api.approveIngestBatch(selected.id, 'Approved in UI');
      setSelected(next);
      await refresh();
      requestStatusRefresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Make rates live failed');
    } finally {
      setBusy(false);
    }
  };

  const reject = async () => {
    if (!selected) return;
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
    setBusy(true);
    setError(null);
    try {
      const result = await api.promoteCbic('Approved via Promote CBIC button');
      await refresh();
      if (result.batch_id) {
        setSelected(await api.getIngestBatch(result.batch_id));
      }
      setError(null);
      requestStatusRefresh();
      window.alert(result.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Promote failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel-view">
      <p className="hint">
        Duty rate library for admins: load an official notice, review proposed rates, then make
        them live. Sample archives are never a live government feed. <InfoTip id="ingest_run" />
      </p>
      {error && <p className="error-banner">{error}</p>}

      <div className="result-card" data-testid="promote-wizard">
        <h3>{OPERATOR.sourcesWizardTitle}</h3>
        <ol className="list">
          {OPERATOR.sourcesWizardSteps.map((step, i) => (
            <li key={step}>
              <strong>
                {i + 1}. {step}
              </strong>
            </li>
          ))}
        </ol>
        <div className="toolbar">
          <button
            type="button"
            className="primary-cta"
            disabled={busy}
            onClick={() => void promote()}
          >
            {OPERATOR.sourcesPromote}
          </button>
          <button type="button" disabled={busy} onClick={() => void runIngest()}>
            {OPERATOR.sourcesLoadOnly}
          </button>
        </div>
        <p className="muted">{OPERATOR.sourcesAfter}</p>
      </div>

      <div className="section-title-row">
        <h3>Duty rate sources</h3>
      </div>
      <table className="data-table">
        <thead>
          <tr>
            <th>Source</th>
            <th>Mode</th>
            <th>Status</th>
            <th>Last success</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {connections.map((c) => (
            <tr key={c.id}>
              <td>
                {c.title}
                {showTech ? <div className="muted">{c.key}</div> : null}
              </td>
              <td>
                {c.fetch_mode}
                {showTech ? ` · ${c.adapter}` : ''}
              </td>
              <td className="muted">{c.honesty_label}</td>
              <td className="muted">
                {c.last_success_at
                  ? new Date(c.last_success_at).toLocaleString()
                  : 'Never'}
                {c.last_error ? <div className="error-banner">{c.last_error}</div> : null}
              </td>
              <td>
                <button
                  type="button"
                  className="chip"
                  disabled={busy || !c.enabled}
                  onClick={() => void fetchConnection(c.key)}
                >
                  Refresh
                </button>
              </td>
            </tr>
          ))}
          {connections.length === 0 && (
            <tr>
              <td colSpan={5} className="muted">
                No duty rate sources yet — they appear after the service starts.
              </td>
            </tr>
          )}
        </tbody>
      </table>

      <div className="toolbar">
        <button type="button" disabled={busy} onClick={() => void runIngest()}>
          Load CBIC Q3 notice <InfoTip id="ingest_run" />
        </button>
      </div>

      <div className="section-title-row">
        <h3>Rate update batches</h3>
        <InfoTip id="ingest_approve" />
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
          {batches.map((b) => (
            <tr key={b.id}>
              <td>{b.source_key}</td>
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
          {batches.length === 0 && (
            <tr>
              <td colSpan={showTech ? 5 : 4} className="muted">
                No batches yet — load a notice first.
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {selected && (
        <div className="result-card">
          <p>
            <strong>{selected.title}</strong> · {selected.status} · effective{' '}
            {selected.effective_from || '—'}
          </p>
          <p className="muted">{selected.publisher}</p>
          {selected.status === 'pending_review' && (
            <div className="toolbar">
              <button type="button" disabled={busy} onClick={() => void approve()}>
                Make rates live <InfoTip id="ingest_approve" />
              </button>
              <button type="button" disabled={busy} onClick={() => void reject()}>
                Reject
              </button>
            </div>
          )}
          <table className="data-table">
            <thead>
              <tr>
                <th>Kind</th>
                <th>
                  <span className="label-with-tip">
                    Checks <InfoTip id="validation_error" />
                  </span>
                </th>
                <th>Publish</th>
                {showTech ? <th>Payload</th> : null}
              </tr>
            </thead>
            <tbody>
              {selected.proposals.map((p) => (
                <tr key={p.id}>
                  <td>{p.kind}</td>
                  <td>
                    {p.validation_status}
                    {p.validation_errors.length > 0 && (
                      <div className="muted">{p.validation_errors.join(', ')}</div>
                    )}
                  </td>
                  <td>{p.publish_status}</td>
                  {showTech ? (
                    <td>
                      <code>{JSON.stringify(p.payload).slice(0, 120)}</code>
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
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
            <th>Kind</th>
            <th>Effective</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              {showTech ? <td>{r.id}</td> : null}
              <td>
                {r.title}
                {r.notes && <div className="muted">{r.notes}</div>}
                {r.honesty_notice && <div className="muted">{r.honesty_notice}</div>}
              </td>
              <td>{r.status}</td>
              {showTech ? (
                <td className="muted">{r.checksum ? `${r.checksum.slice(0, 12)}…` : '—'}</td>
              ) : null}
              <td>
                {r.source_kind || 'sample archive'}
                {r.live_government_feed ? '' : ' · not a live feed'}
              </td>
              <td>{r.effective_from}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <details className="tech-log" open={showTech}>
        <summary>{OPERATOR.sourcesTechLog}</summary>
        <div className="section-title-row">
          <h3>Data versions</h3>
          <InfoTip id="data_version" />
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Label</th>
              <th>Fingerprint</th>
              <th>Counts</th>
              <th>Published</th>
            </tr>
          </thead>
          <tbody>
            {versions.map((v) => (
              <tr key={v.id}>
                <td>{v.label}</td>
                <td className="muted">{v.fingerprint}</td>
                <td>{JSON.stringify(v.record_counts)}</td>
                <td>{v.published_at}</td>
              </tr>
            ))}
            {versions.length === 0 && (
              <tr>
                <td colSpan={4} className="muted">
                  No published rate versions yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </details>
    </section>
  );
}
