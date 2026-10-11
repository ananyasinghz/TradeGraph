import type { SourceFeedStatus } from '../services/api';

export function FeedHealthCard({ feedStatus }: { feedStatus: SourceFeedStatus }) {
  const manual = (feedStatus.refresh_mode || 'manual_only') === 'manual_only';
  return (
    <div className="result-card" data-testid="sources-feed-health">
      <h3>Feed &amp; refresh health</h3>
      <p>
        Live government feed:{' '}
        <strong>{feedStatus.live_government_feed ? 'yes' : 'no'}</strong>
        {feedStatus.source_connection_label
          ? ` · ${feedStatus.source_connection_label}`
          : ''}
        {feedStatus.has_live_adapter ? ' · official/live adapter configured' : ''}
      </p>
      <p className="muted">{feedStatus.live_feed_reason}</p>
      <p className="muted" data-testid="sources-document-monitor-note">
        CBIC/ICEGATE document monitors archive HTML/PDF evidence; rates publish only after
        reviewer approval. Preferential ICEGATE calculator is not automated.
      </p>
      <p className="muted">
        Last attempt:{' '}
        {feedStatus.last_attempt_at
          ? new Date(feedStatus.last_attempt_at).toLocaleString()
          : 'Never'}
        {' · '}
        Last success:{' '}
        {feedStatus.last_successful_fetch_at
          ? new Date(feedStatus.last_successful_fetch_at).toLocaleString()
          : 'Never'}
      </p>
      <p className="muted" data-testid="sources-refresh-mode">
        Refresh:{' '}
        {manual ? (
          <strong>Manual only</strong>
        ) : (
          <>
            <strong>Scheduled</strong> · every {feedStatus.scheduler_interval_minutes} min
            {feedStatus.next_attempt_at
              ? ` · next ${new Date(feedStatus.next_attempt_at).toLocaleString()}`
              : ''}
            {feedStatus.fetch_overdue ? ' · overdue' : ''}
          </>
        )}
      </p>
      <p className="muted" data-testid="sources-rates-usable">
        Published rates usable:{' '}
        <strong>{feedStatus.published_rates_usable === false ? 'no' : 'yes'}</strong>
        {feedStatus.last_error
          ? ' (fetch may be unhealthy; prior published rates remain resolvable)'
          : ''}
      </p>
      {feedStatus.last_error ? (
        <p className="error-banner">{feedStatus.last_error}</p>
      ) : null}
    </div>
  );
}
