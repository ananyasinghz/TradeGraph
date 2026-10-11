import { useEffect, useState } from 'react';
import { api, type PublicShare } from '../services/api';
import { DisclaimerFooter } from '../components/DisclaimerFooter';
import { docLabel } from '../content/operatorCopy';

interface PublicShareViewProps {
  token: string;
}

export function PublicShareView({ token }: PublicShareViewProps) {
  const [data, setData] = useState<PublicShare | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api
      .getPublicShare(token)
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : 'Share unavailable'));
  }, [token]);

  return (
    <div className="public-share-shell" data-testid="public-share-view">
      <header className="public-share-header">
        <strong>TRADEGRAPH</strong>
        <span className="muted">Client share (read-only)</span>
      </header>
      <main className="panel-view">
        {error && <p className="error-banner">{error}</p>}
        {!data && !error ? <p className="muted">Loading share…</p> : null}
        {data ? (
          <>
            <h2>{data.title}</h2>
            <p className="hint">
              Readiness {data.readiness.score}/100 · {data.readiness.band}
            </p>
            {(data.readiness.blocked_reasons?.length ?? 0) > 0 ? (
              <ul className="list">
                {data.readiness.blocked_reasons!.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            ) : null}
            <h3>Shipping papers</h3>
            {data.papers.length === 0 ? (
              <p className="muted">No papers checklist on this share.</p>
            ) : (
              <ul className="list">
                {data.papers.map((p) => (
                  <li key={p.doc_code}>
                    {p.doc_label || docLabel(p.doc_code)}
                    {p.required ? ' *' : ''} · {p.status || (p.done ? 'ready' : 'not started')}
                  </li>
                ))}
              </ul>
            )}
            <DisclaimerFooter />
          </>
        ) : null}
      </main>
    </div>
  );
}
