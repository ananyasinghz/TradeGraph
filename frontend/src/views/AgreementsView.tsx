import { useEffect, useState } from 'react';
import {
  ApiError,
  api,
  type CoverageMiss,
  type FtaCheckResult,
  type TradeAgreement,
} from '../services/api';
import { ContextAskButton } from '../components/ContextAskButton';
import { CoverageMissPanel } from '../components/CoverageMissPanel';
import { InfoTip } from '../components/InfoTip';

export function AgreementsView() {
  const [agreements, setAgreements] = useState<TradeAgreement[]>([]);
  const [hs, setHs] = useState('6109.10');
  const [asOf, setAsOf] = useState('2026-06-01');
  const [result, setResult] = useState<FtaCheckResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [coverageMiss, setCoverageMiss] = useState<CoverageMiss | null>(null);

  useEffect(() => {
    void api.listAgreements().then(setAgreements).catch((err) => setError(String(err)));
  }, []);

  const run = async () => {
    setError(null);
    setCoverageMiss(null);
    try {
      setResult(
        await api.checkFta({
          hs_code: hs,
          origin: 'BD',
          destination: 'IN',
          as_of: asOf,
        }),
      );
    } catch (err) {
      setResult(null);
      if (err instanceof ApiError && err.coverageMiss) {
        setCoverageMiss(err.coverageMiss);
      } else {
        setError(err instanceof Error ? err.message : 'FTA check failed');
      }
    }
  };

  return (
    <section className="panel-view">
      <div className="section-title-row">
        <h3>Agreements</h3>
        <InfoTip id="fta" />
      </div>
      <ul className="list">
        {agreements.map((a) => (
          <li key={a.id}>
            <strong>{a.name}</strong> <span className="badge badge-illustrative">{a.status}</span>
            <div className="muted">{a.notes}</div>
          </li>
        ))}
      </ul>
      <div className="section-title-row">
        <h3>FTA check</h3>
        <InfoTip id="preferential_vs_mfn" />
      </div>
      <div className="toolbar">
        <label>
          <span className="label-with-tip">
            HS <InfoTip id="hs_code" />
          </span>
          <input value={hs} onChange={(e) => setHs(e.target.value)} />
        </label>
        <label>
          <span className="label-with-tip">
            As of <InfoTip id="as_of" />
          </span>
          <input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} />
        </label>
        <button type="button" onClick={() => void run()}>
          Check eligibility
        </button>
      </div>
      {error && <p className="error-banner">{error}</p>}
      {coverageMiss && <CoverageMissPanel miss={coverageMiss} />}
      {result && (
        <div className="result-card">
          <ContextAskButton
            label="Why is this not (or only potentially) preferential?"
            focus="fta"
            hsCode={hs}
            asOf={asOf}
          />
          <p>
            Status: <strong>{result.status.replaceAll('_', ' ')}</strong> ·{' '}
            <span className="label-with-tip">
              MFN <InfoTip id="mfn" />
            </span>{' '}
            {result.mfn_rate_pct}% → preferential {result.preferential_rate_pct}%
          </p>
          {(result.reasons || []).length > 0 && (
            <>
              <h4>Why this status</h4>
              <ul>
                {result.reasons?.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </>
          )}
          <p>
            Agreement: {result.agreement_name} · Certificate:{' '}
            <span className="label-with-tip">
              {result.certificate_doc_code} <InfoTip id="certificate_of_origin" />
            </span>
          </p>
          <p className="muted">
            <span className="label-with-tip">
              RoO <InfoTip id="roo" />
            </span>
            : {result.roo_summary}
          </p>
          <p className="disclaimer-inline">{result.disclaimer}</p>
          <details>
            <summary>Graph path (technical)</summary>
            <pre>{JSON.stringify(result.graph_path, null, 2)}</pre>
          </details>
        </div>
      )}
    </section>
  );
}
