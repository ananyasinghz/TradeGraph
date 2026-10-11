import { useEffect, useState } from 'react';
import { api, type WatchlistChange, type WatchlistItem } from '../services/api';
import { InfoTip } from '../components/InfoTip';
import { OPERATOR } from '../content/operatorCopy';

interface WatchlistViewProps {
  onOpenShipment?: (shipmentId: string) => void;
}

export function WatchlistView({ onOpenShipment }: WatchlistViewProps) {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [changes, setChanges] = useState<WatchlistChange[]>([]);
  const [hs, setHs] = useState('6109.10');
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    setItems(await api.listWatchlist());
    setChanges(await api.watchlistChanges());
  };

  useEffect(() => {
    void refresh().catch((err) => setError(err instanceof Error ? err.message : 'Failed'));
  }, []);

  const add = async () => {
    setError(null);
    try {
      await api.addWatchlist({ hs_code: hs, origin: 'BD', destination: 'IN' });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Add failed');
    }
  };

  return (
    <section className="panel-view">
      <p className="hint">
        Track HS codes and get alerts when duty rates change for this trade lane.{' '}
        <InfoTip id="watchlist_change" />
      </p>
      <div className="toolbar">
        <label>
          <span className="label-with-tip">
            HS to watch <InfoTip id="hs_code" />
          </span>
          <input value={hs} onChange={(e) => setHs(e.target.value)} />
        </label>
        <button type="button" onClick={() => void add()}>
          Add BD→IN alert
        </button>
      </div>
      {error && <p className="error-banner">{error}</p>}
      <h3>Watched products</h3>
      <ul className="list">
        {items.map((i) => (
          <li key={i.id}>
            {i.hs_code} {i.origin}→{i.destination}
            {i.shipment_title ? (
              <span className="muted"> · case “{i.shipment_title}”</span>
            ) : null}
            {i.shipment_id && onOpenShipment ? (
              <>
                {' '}
                <button
                  type="button"
                  className="linkish"
                  onClick={() => onOpenShipment(i.shipment_id!)}
                >
                  {OPERATOR.openCase}
                </button>
              </>
            ) : null}
          </li>
        ))}
      </ul>
      <div className="section-title-row">
        <h3>Duty changes</h3>
        <InfoTip id="supersession" />
      </div>
      {changes.length === 0 ? (
        <p className="muted">No duty changes on watched products yet.</p>
      ) : (
        <ul className="list">
          {changes.map((c) => (
            <li key={`${c.watchlist_item_id}-${c.new_version}`}>
              <strong>Duty change · {c.summary}</strong>
              <div className="muted">Source {c.source_document_id}</div>
              {(c.affected_shipment_titles || []).length > 0 && (
                <div className="muted">
                  Affects: {(c.affected_shipment_titles || []).join(', ')}
                </div>
              )}
              {(c.affected_shipment_ids || []).length > 0 && onOpenShipment ? (
                <div className="toolbar">
                  {c.affected_shipment_ids!.map((id, idx) => (
                    <button
                      key={id}
                      type="button"
                      className="linkish"
                      data-testid="open-affected-case"
                      onClick={() => onOpenShipment(id)}
                    >
                      {OPERATOR.openCase}
                      {(c.affected_shipment_titles || [])[idx]
                        ? ` · ${c.affected_shipment_titles![idx]}`
                        : ''}
                    </button>
                  ))}
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
