import { useEffect, useState } from 'react';
import { ApiError, api, type CoverageMiss, type LandedCostBreakdown } from '../services/api';
import { ContextAskButton } from '../components/ContextAskButton';
import { CoverageMissPanel } from '../components/CoverageMissPanel';
import { DataConfidenceBadge } from '../components/DataConfidenceBadge';
import { InfoTip } from '../components/InfoTip';
import { OPERATOR } from '../content/operatorCopy';
import { useOperatorPrefs } from '../content/useOperatorPrefs';

export function CalculatorView() {
  const { showTech } = useOperatorPrefs();
  const [hs, setHs] = useState('6109.10');
  const [asOf, setAsOf] = useState('2026-06-01');
  const [value, setValue] = useState('1000');
  const [incoterm, setIncoterm] = useState('CIF');
  const [freight, setFreight] = useState('');
  const [insurance, setInsurance] = useState('');
  const [result, setResult] = useState<LandedCostBreakdown | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [coverageMiss, setCoverageMiss] = useState<CoverageMiss | null>(null);

  const [customs, setCustoms] = useState<{
    available: boolean;
    hint: string;
    blockers: string[];
  } | null>(null);

  useEffect(() => {
    void api
      .getCustomsAvailability()
      .then((a) =>
        setCustoms({
          available: a.customs_mode_available,
          hint: a.customs_mode_hint,
          blockers: a.customs_mode_blockers,
        }),
      )
      .catch(() => setCustoms(null));
  }, []);

  const run = async (mode: 'estimate' | 'customs' = 'estimate') => {
    setError(null);
    setCoverageMiss(null);
    try {
      const data = await api.calculateLandedCost({
        hs_code: hs,
        origin: 'BD',
        destination: 'IN',
        as_of: asOf,
        invoice_value: value,
        currency: 'USD',
        incoterm,
        freight: freight === '' ? null : freight,
        insurance: insurance === '' ? null : insurance,
        requested_mode: mode,
      });
      setResult(data);
    } catch (err) {
      setResult(null);
      if (err instanceof ApiError && err.coverageMiss) {
        setCoverageMiss(err.coverageMiss);
      } else {
        setError(err instanceof Error ? err.message : 'Calculation failed');
      }
    }
  };

  return (
    <section className="panel-view">
      <p className="hint">{OPERATOR.calcLead}</p>
      <div className="form-grid">
        <label>
          <span className="label-with-tip">
            HS code <InfoTip id="hs_code" />
          </span>
          <input value={hs} onChange={(e) => setHs(e.target.value)} />
        </label>
        <label>
          <span className="label-with-tip">
            As of <InfoTip id="as_of" />
          </span>
          <input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} />
        </label>
        <label>
          <span className="label-with-tip">
            Invoice / CIF value (USD) <InfoTip id="invoice_value" />
          </span>
          <input value={value} onChange={(e) => setValue(e.target.value)} />
        </label>
        <label>
          Incoterm
          <select value={incoterm} onChange={(e) => setIncoterm(e.target.value)}>
            <option value="CIF">CIF</option>
            <option value="FOB">FOB</option>
            <option value="EXW">EXW</option>
          </select>
        </label>
        <label>
          Freight (optional)
          <input value={freight} onChange={(e) => setFreight(e.target.value)} placeholder="USD" />
        </label>
        <label>
          Insurance (optional)
          <input
            value={insurance}
            onChange={(e) => setInsurance(e.target.value)}
            placeholder="USD"
          />
        </label>
        <button type="button" onClick={() => void run('estimate')}>
          {OPERATOR.calcEstimate}
        </button>
        <button
          type="button"
          disabled={customs != null && !customs.available}
          title={customs?.hint}
          onClick={() => void run('customs')}
        >
          {OPERATOR.calcVerified} / {OPERATOR.calcFiling}
        </button>
      </div>
      {customs && !customs.available && (
        <div className="error-banner" role="status">
          <strong>{OPERATOR.calcFiling} unavailable.</strong> {customs.hint}
          {customs.blockers.length > 0 && (
            <ul className="warn-list">
              {customs.blockers.map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
          )}
        </div>
      )}
      {error && <p className="error-banner">{error}</p>}
      {coverageMiss && <CoverageMissPanel miss={coverageMiss} />}
      {result && (
        <div className="result-card">
          <ContextAskButton
            label="Explain my landed cost"
            focus="landed_cost"
            hsCode={hs}
            asOf={asOf}
          />
          <h3>
            {result.title || 'Estimated landed cost'} <InfoTip id="landed_cost" />
            {result.calculation_mode === 'estimate' ? (
              <span className="badge badge-illustrative" style={{ marginLeft: 8 }}>
                Rough estimate
              </span>
            ) : result.calculation_mode === 'customs' ? (
              <span className="badge badge-illustrative" style={{ marginLeft: 8 }}>
                Filing-ready
              </span>
            ) : null}
          </h3>
          {(result.assumptions || []).length > 0 && (
            <>
              <h4>Assumptions</h4>
              <ul className="warn-list">
                {result.assumptions?.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            </>
          )}
          {(result.warnings || []).length > 0 && (
            <ul className="warn-list">
              {result.warnings?.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          )}
          <dl className="kv">
            <div>
              <dt>Assessable</dt>
              <dd>
                {result.assessable_value} {result.currency}
              </dd>
            </div>
            <div>
              <dt>
                <span className="label-with-tip">
                  BCD ({result.bcd_rate_pct}%) <InfoTip id="bcd" />
                </span>
              </dt>
              <dd>{result.bcd}</dd>
            </div>
            <div>
              <dt>
                <span className="label-with-tip">
                  SWS <InfoTip id="sws" />
                </span>
              </dt>
              <dd>{result.sws}</dd>
            </div>
            <div>
              <dt>
                <span className="label-with-tip">
                  IGST ({result.igst_rate_pct}%) <InfoTip id="igst" />
                </span>
              </dt>
              <dd>{result.igst}</dd>
            </div>
            <div>
              <dt>Total duties/taxes</dt>
              <dd>{result.total_duties_taxes}</dd>
            </div>
            <div>
              <dt>
                <span className="label-with-tip">
                  Landed cost <InfoTip id="landed_cost" />
                </span>
              </dt>
              <dd>
                <strong>
                  {result.landed_cost} {result.currency}
                </strong>
              </dd>
            </div>
          </dl>
          {(result.formula_steps || []).length > 0 && (
            <>
              <h4>Formula</h4>
              <ol className="formula-steps">
                {result.formula_steps?.map((step) => (
                  <li key={step}>{step.replace(/^\d+\.\s*/, '')}</li>
                ))}
              </ol>
            </>
          )}
          <p className="muted">
            <DataConfidenceBadge dataQuality={result.data_quality} /> <InfoTip id="data_quality" />
            {showTech ? (
              <>
                {' '}
                · source {result.source_document_id} · rate id {result.tariff_rate_id}
              </>
            ) : null}
          </p>
          <p className="disclaimer-inline">{result.disclaimer}</p>
        </div>
      )}
    </section>
  );
}
