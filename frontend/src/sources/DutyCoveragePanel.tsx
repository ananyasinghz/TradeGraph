import { useEffect, useState } from 'react';
import { api, type TariffCoverage } from '../services/api';
import { ComponentQualityBadge } from '../components/ComponentQualityBadge';

export function DutyCoveragePanel({
  origin = 'BD',
  destination = 'IN',
}: {
  origin?: string;
  destination?: string;
}) {
  const [coverage, setCoverage] = useState<TariffCoverage | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api
      .getDutyCoverage({ origin, destination })
      .then(setCoverage)
      .catch((err) => setError(err instanceof Error ? err.message : 'Coverage failed'));
  }, [origin, destination]);

  if (error) return <p className="error-banner">{error}</p>;
  if (!coverage) return <p className="muted">Loading coverage…</p>;

  return (
    <div className="result-card" data-testid="duty-coverage-panel">
      <h3>
        Duty coverage ({coverage.origin}→{coverage.destination})
      </h3>
      <p className="muted">{coverage.honesty_note}</p>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Chapter</th>
              <th>Classification</th>
              <th>BCD</th>
              <th>SWS</th>
              <th>IGST</th>
              <th>Exemptions</th>
              <th>Preferential</th>
            </tr>
          </thead>
          <tbody>
            {coverage.chapters.map((ch) => (
              <tr key={ch.chapter}>
                <td>{ch.chapter}</td>
                <td>
                  {ch.classification_codes}{' '}
                  <ComponentQualityBadge quality={ch.classification_status} />
                </td>
                <td>
                  {ch.bcd_rates} <ComponentQualityBadge quality={ch.bcd_status} />
                </td>
                <td>
                  {ch.sws_rates ?? 0} <ComponentQualityBadge quality={ch.sws_status} />
                </td>
                <td>
                  {ch.igst_rates} <ComponentQualityBadge quality={ch.igst_status} />
                </td>
                <td>
                  {ch.exemption_rules}{' '}
                  <ComponentQualityBadge quality={ch.exemption_status} />
                </td>
                <td>
                  {ch.preferential_rules}{' '}
                  <ComponentQualityBadge quality={ch.preferential_status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
