import type { SourceConnection, SourceFeedStatus } from '../services/api';
import {
  acquisitionClass,
  acquisitionMethodLabel,
  fetchStage,
  publicationStage,
} from './sourceHelpers';

export function ConnectionCard({
  connection,
  feedStatus,
  busy,
  onRefresh,
}: {
  connection: SourceConnection;
  feedStatus: SourceFeedStatus | null;
  busy: boolean;
  onRefresh: (key: string) => void;
}) {
  const c = connection;
  const cls = acquisitionClass(c);
  const showScheduler =
    c.lane === 'live_official' || c.refresh_mode === 'scheduled';
  return (
    <article className="result-card" data-testid={`source-conn-${c.key}`}>
      <h4>
        {c.title}{' '}
        <span className="chip" data-testid={`source-class-${c.key}`}>
          {cls}
        </span>
        {c.lane === 'live_official' ? (
          <span className="chip" data-testid={`source-lane-${c.key}`}>
            live / official
          </span>
        ) : null}
      </h4>
      <p className="muted">{c.key}</p>
      <p className="muted" data-testid={`source-honesty-${c.key}`}>
        {c.honesty_label}
      </p>
      <p className="muted">
        Portal: {c.source_url || '—'}
        {c.document_url ? (
          <>
            <br />
            Document: {c.document_url}
          </>
        ) : null}
        {c.last_final_url ? (
          <>
            <br />
            Last URL: {c.last_final_url}
          </>
        ) : null}
      </p>
      <p className="muted">
        Acquisition: {acquisitionMethodLabel(c)} · Fetch: {fetchStage(c)} · Publication:{' '}
        {publicationStage(c)}
      </p>
      <p className="muted">
        Attempt:{' '}
        {c.last_checked_at ? new Date(c.last_checked_at).toLocaleString() : '—'}
        {' · '}
        Success:{' '}
        {c.last_success_at ? new Date(c.last_success_at).toLocaleString() : 'Never'}
      </p>
      {c.last_checksum ? (
        <p className="muted">Checksum: {c.last_checksum.slice(0, 16)}…</p>
      ) : null}
      {c.last_archive_path ? (
        <p className="muted">Archive: {c.last_archive_path}</p>
      ) : null}
      {c.last_published_at ? (
        <p className="muted">
          Published: {new Date(c.last_published_at).toLocaleString()}
          {c.last_published_version_id
            ? ` · ${c.last_published_version_id.slice(0, 12)}…`
            : ''}
        </p>
      ) : null}
      {c.last_error ? <p className="error-banner">{c.last_error}</p> : null}
      {showScheduler ? (
        <p className="muted">
          {c.refresh_mode === 'scheduled'
            ? c.next_attempt_at
              ? `Next scheduled ${new Date(c.next_attempt_at).toLocaleString()}`
              : `Scheduled · ${feedStatus?.scheduler_interval_minutes ?? '—'}m`
            : 'Manual refresh only'}
          {c.fetch_overdue ? ' · overdue' : ''}
        </p>
      ) : (
        <p className="muted">Manual refresh only (not a scheduled monitor)</p>
      )}
      <div className="toolbar">
        <button
          type="button"
          className="chip"
          disabled={busy || !c.enabled}
          onClick={() => onRefresh(c.key)}
          data-testid={`source-refresh-${c.key}`}
        >
          Refresh
        </button>
      </div>
    </article>
  );
}
