import type { SourceConnection } from '../services/api';

export type AcquisitionClass =
  | 'curated_fixture'
  | 'official_document'
  | 'live_http'
  | 'local_archive'
  | 'published_verified';

export function acquisitionClass(c: SourceConnection): AcquisitionClass {
  if (c.lane === 'demo_fixture') return 'curated_fixture';
  if (c.lane === 'live_official') return 'official_document';
  if (c.lane === 'local_archive') return 'local_archive';
  const adapter = (c.adapter || '').toLowerCase();
  const mode = (c.fetch_mode || '').toLowerCase();
  if (
    adapter.includes('official_document') ||
    adapter.includes('cbic_document') ||
    adapter.includes('icegate_document') ||
    mode === 'official_document'
  ) {
    return 'official_document';
  }
  if (adapter.includes('live') || mode === 'http_get') return 'live_http';
  if (adapter.includes('pdf') || mode === 'local_archive') return 'local_archive';
  return 'curated_fixture';
}

export function acquisitionMethodLabel(c: SourceConnection): string {
  const cls = acquisitionClass(c);
  if (cls === 'official_document') return 'official_document_http';
  if (cls === 'live_http') return 'live_http_api';
  if (cls === 'local_archive') return 'local_archive';
  return 'curated_mirror';
}

export function fetchStage(c: SourceConnection): string {
  const stage = (c.pipeline_stage || 'configured').toLowerCase();
  if (c.last_error && (stage === 'error' || !c.last_success_at)) return 'error';
  if (
    ['fetch_success', 'parsed', 'pending_review', 'quarantined', 'unchanged', 'published'].includes(
      stage,
    )
  ) {
    return stage === 'published' ||
      stage === 'pending_review' ||
      stage === 'quarantined' ||
      stage === 'unchanged'
      ? 'fetch_success'
      : stage;
  }
  return stage || 'configured';
}

export function publicationStage(c: SourceConnection): string {
  if (c.last_published_at || c.pipeline_stage === 'published') return 'published';
  if (c.pipeline_stage === 'pending_review') return 'pending_review';
  return 'none';
}

export function sourceClassBadge(
  key: string,
  connections: SourceConnection[],
  published = false,
): AcquisitionClass | string {
  if (published) {
    const conn = connections.find((c) => c.key === key || `src_${c.key}` === key);
    if (
      conn &&
      (acquisitionClass(conn) === 'live_http' || acquisitionClass(conn) === 'official_document')
    ) {
      return 'published_verified';
    }
  }
  const conn = connections.find((c) => c.key === key);
  if (!conn) {
    if (key.includes('cbic_taxinfo') || key.includes('cbic_customs') || key.includes('cbic_ch61') || key.includes('icegate')) {
      return 'official_document';
    }
    if (key.includes('live')) return 'live_http';
    if (key.includes('pdf') || key.includes('itc') || key.includes('hs_code')) return 'local_archive';
    return 'curated_fixture';
  }
  return acquisitionClass(conn);
}

export const VALIDATION_LABELS: Record<string, string> = {
  unknown_hs_code: 'Unknown HS code',
  invalid_corridor: 'Invalid corridor',
  invalid_rate: 'Invalid rate',
  missing_hs_code: 'Missing HS code',
  chapter_lock: 'Outside allowed chapter',
  corridor_lock: 'Outside allowed corridor',
};

export function validationLabel(code: string): string {
  return VALIDATION_LABELS[code] || code.replace(/_/g, ' ');
}

export const VERIFIED_CBIC_CH61_KEY = 'cbic_ch61_igst_notif_9_2025';
export const DEMO_FIXTURE_KEY = 'cbic_notification_2026_q3';
