import { useEffect, useState } from 'react';
import { api, type CoverageMiss, type FtaCheckResult, type TariffRate } from '../services/api';
import { ContextAskButton } from '../components/ContextAskButton';
import { CoverageMissPanel } from '../components/CoverageMissPanel';
import { DataConfidenceBadge } from '../components/DataConfidenceBadge';
import { DisclaimerFooter } from '../components/DisclaimerFooter';
import { InfoTip } from '../components/InfoTip';
import { OPERATOR } from '../content/operatorCopy';
import { useOperatorPrefs } from '../content/useOperatorPrefs';

export function TariffsView() {
  const [hs, setHs] = useState('');
  const [asOf, setAsOf] = useState('2026-06-01');
  const [agreementId, setAgreementId] = useState('');
  const [rows, setRows] = useState<TariffRate[]>([]);
  const [selected, setSelected] = useState<TariffRate | null>(null);
  const [history, setHistory] = useState<TariffRate[] | null>(null);
  const [fta, setFta] = useState<FtaCheckResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [emptyMiss, setEmptyMiss] = useState<CoverageMiss | null>(null);
  const [loading, setLoading] = useState(false);
  const [sourceOpen, setSourceOpen] = useState(false);
  const { showTech } = useOperatorPrefs();

  const load = async () => {
    setLoading(true);
    setError(null);
    setEmptyMiss(null);
    try {
      const data = await api.listTariffs({
        hs: hs || undefined,
        origin: 'BD',
        destination: 'IN',
        as_of: asOf,
        agreement_id: agreementId || undefined,
      });
      setRows(data);
      setHistory(null);
      if (selected) {
        const still = data.find((r) => r.id === selected.id) || data[0] || null;
        setSelected(still);
      }
      if (data.length === 0 && hs) {
        setEmptyMiss({
          message: `No tariff rows for HS ${hs} BD→IN as of ${asOf}.`,
          origin: 'BD',
          destination: 'IN',
          hs_code: hs,
          as_of: asOf,
          possible_reasons: [
            'This HS code may be outside the current dataset',
            'The selected date may be outside rule validity',
            'The rule may not have been imported yet',
          ],
          next_actions: [
            'Try a known HS such as 6109.10 (cotton T-shirts)',
            'Change the as-of date',
            'Ask admin to update duty rates from an official notice',
          ],
          dataset_coverage: {
            corridor: 'BD->IN',
            hs_chapters: ['61'],
          },
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load tariffs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openDetail = async (row: TariffRate) => {
    setSelected(row);
    setError(null);
    try {
      const [hist, ftaResult] = await Promise.all([
        api.tariffHistory(row.id),
        api.checkFta({
          hs_code: row.hs_code,
          origin: row.origin,
          destination: row.destination,
          as_of: asOf,
        }),
      ]);
      setHistory(hist);
      setFta(ftaResult);
    } catch (err) {
      setHistory(null);
      setFta(null);
      setError(err instanceof Error ? err.message : 'Detail load failed');
    }
  };

  return (
    <section className="panel-view">
      <div className="toolbar">
        <label>
          <span className="label-with-tip">
            HS <InfoTip id="hs_code" />
          </span>
          <input
            data-testid="tariff-hs-input"
            value={hs}
            onChange={(e) => setHs(e.target.value)}
            placeholder="6109.10"
          />
        </label>
        <label>
          <span className="label-with-tip">
            As of <InfoTip id="as_of" />
          </span>
          <input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} />
        </label>
        <label>
          Agreement filter
          <input
            value={agreementId}
            onChange={(e) => setAgreementId(e.target.value)}
            placeholder="optional id"
          />
        </label>
        <button type="button" onClick={() => void load()} disabled={loading}>
          {loading ? 'Loading…' : 'Search'}
        </button>
        <button
          type="button"
          onClick={() => {
            setAsOf('2025-06-01');
            void (async () => {
              setLoading(true);
              try {
                const data = await api.listTariffs({
                  hs: hs || '6109.10',
                  origin: 'BD',
                  destination: 'IN',
                  as_of: '2025-06-01',
                });
                setRows(data);
              } catch (err) {
                setError(err instanceof Error ? err.message : 'Failed');
              } finally {
                setLoading(false);
              }
            })();
          }}
        >
          Demo 2025 as-of
        </button>
      </div>
      {error && <p className="error-banner">{error}</p>}
      <p className="hint">
        {OPERATOR.tariffHint} <InfoTip id="illustrative" />
      </p>
      {emptyMiss && <CoverageMissPanel miss={emptyMiss} />}
      <table className="data-table">
        <thead>
          <tr>
            <th>
              <span className="label-with-tip">
                HS <InfoTip id="hs_code" />
              </span>
            </th>
            <th>Rate %</th>
            <th>
              <span className="label-with-tip">
                {OPERATOR.tariffQuality} <InfoTip id="data_quality" />
              </span>
            </th>
            <th>Effective</th>
            <th>Source</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className={selected?.id === r.id ? 'selected-row' : undefined}>
              <td>
                <strong>{r.hs_code}</strong>
                <div className="muted">{r.hs_description}</div>
              </td>
              <td>{r.rate}</td>
              <td>
                <DataConfidenceBadge dataQuality={r.data_quality} />
              </td>
              <td>
                {r.effective_from}
                {r.effective_to ? ` → ${r.effective_to}` : ' → open'}
              </td>
              <td>
                {r.source_document_id}
                {r.source_stale ? <div className="muted">Stale source</div> : null}
                {r.evidence?.verified === false ? (
                  <div className="muted">Source not verified</div>
                ) : null}
              </td>
              <td>
                <button type="button" className="linkish" onClick={() => void openDetail(r)}>
                  Details
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {selected && (
        <div className="drawer tariff-detail">
          <h3>
            Duty rate · {selected.hs_code} <InfoTip id="hs_code" />
          </h3>
          <p>{selected.hs_description || 'No product description on this rate row.'}</p>
          <dl className="kv">
            <div>
              <dt>MFN / listed rate</dt>
              <dd>{selected.rate}%</dd>
            </div>
            <div>
              <dt>Evidence</dt>
              <dd>
                {selected.evidence?.verified
                  ? `${selected.evidence.title || selected.source_document_id} · ${selected.evidence.status || ''}`
                  : selected.evidence?.message || 'Source not verified'}
                {selected.confidence ? (
                  <div className="muted">confidence: {selected.confidence}</div>
                ) : null}
              </dd>
            </div>
            <div>
              <dt>Preferential (FTA check)</dt>
              <dd>
                {fta
                  ? `${fta.status} · ${fta.preferential_rate_pct ?? '—'}% (${fta.agreement_name || 'n/a'})`
                  : '—'}
              </dd>
            </div>
            <div>
              <dt>Validity</dt>
              <dd>
                {selected.effective_from}
                {selected.effective_to ? ` → ${selected.effective_to}` : ' → open'} · {selected.status}
              </dd>
            </div>
            <div>
              <dt>Rate status</dt>
              <dd>
                <DataConfidenceBadge dataQuality={selected.data_quality} />
              </dd>
            </div>
          </dl>
          <button
            type="button"
            className="linkish"
            onClick={() => setSourceOpen((v) => !v)}
            aria-expanded={sourceOpen || showTech}
          >
            {sourceOpen || showTech ? 'Hide source details' : OPERATOR.tariffSourceDetails}
          </button>
          {(sourceOpen || showTech) && (
            <dl className="kv">
              <div>
                <dt>Duty components</dt>
                <dd>
                  <code>{JSON.stringify(selected.duty_components)}</code>
                </dd>
              </div>
              <div>
                <dt>Source</dt>
                <dd>
                  {selected.source_document_id}
                  {selected.source?.published_at ? (
                    <div className="muted">
                      published {new Date(selected.source.published_at).toLocaleString()}
                    </div>
                  ) : null}
                  {selected.evidence?.published_at ? (
                    <div className="muted">
                      evidence published{' '}
                      {new Date(String(selected.evidence.published_at)).toLocaleString()}
                    </div>
                  ) : null}
                  <div className="muted">
                    version {selected.version}
                    {selected.evidence?.checksum
                      ? ` · file fingerprint ${String(selected.evidence.checksum).slice(0, 12)}…`
                      : ''}
                  </div>
                </dd>
              </div>
            </dl>
          )}
          <ContextAskButton
            label="Explain this duty rate"
            focus="tariff"
            hsCode={selected.hs_code}
            asOf={asOf}
            origin={selected.origin}
            destination={selected.destination}
          />
          {history && history.length > 0 && (
            <>
              <h4>
                Rate history <InfoTip id="supersession" />
              </h4>
              <ul>
                {history.map((h) => (
                  <li key={h.id}>
                    {h.rate}% ({h.status}) {h.effective_from}
                    {h.effective_to ? `–${h.effective_to}` : '+'}{' '}
                    <DataConfidenceBadge dataQuality={h.data_quality} />
                    {showTech ? <span className="muted"> · v{h.version}</span> : null}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
      <DisclaimerFooter compact />
    </section>
  );
}
