import { DisclaimerFooter } from '../components/DisclaimerFooter';

type LegalPage = 'terms' | 'privacy' | 'disclaimer' | 'cookies';

const PAGES: Record<LegalPage, { title: string; body: string[] }> = {
  terms: {
    title: 'Terms of use',
    body: [
      'TradeGraph is a decision-support workspace for trade clearance research. It does not file entries with customs authorities.',
      'You are responsible for verifying rates, classifications, and documents against official government sources before filing.',
      'Demo and sample rates are for training and evaluation unless an administrator has published checked rates in your organization.',
    ],
  },
  privacy: {
    title: 'Privacy',
    body: [
      'Account identifiers, organization membership, and case metadata are stored to operate the clearance workspace.',
      'Uploaded shipping papers are retained for the case lifecycle and organizational retention policy.',
      'Ask queries may be logged with shipment context for audit and product improvement within your organization.',
    ],
  },
  disclaimer: {
    title: 'Disclaimer',
    body: [
      'TradeGraph is not a licensed customs broker and does not provide legal advice.',
      'Duty estimates, preferential eligibility, and readiness scores are illustrative until confirmed against official sources and your broker’s determination.',
      'Coverage gaps and sample rates are disclosed in the workspace honesty banner.',
    ],
  },
  cookies: {
    title: 'Cookies & local storage',
    body: [
      'This app uses local browser storage for operator preferences (technical details, role display).',
      'Authentication uses session tokens from your identity provider when auth is enabled.',
      'No third-party advertising cookies are used by the TradeGraph operator UI.',
    ],
  },
};

interface LegalViewProps {
  page?: LegalPage;
  onPageChange?: (page: LegalPage) => void;
}

export function LegalView({ page = 'disclaimer', onPageChange }: LegalViewProps) {
  const current = PAGES[page] || PAGES.disclaimer;

  return (
    <section className="panel-view" data-testid="legal-view">
      <div className="chip-row" style={{ marginBottom: 16 }}>
        {(Object.keys(PAGES) as LegalPage[]).map((id) => (
          <button
            key={id}
            type="button"
            className={`chip${page === id ? ' chip-active' : ''}`}
            data-testid={`legal-${id}`}
            onClick={() => onPageChange?.(id)}
          >
            {PAGES[id].title}
          </button>
        ))}
      </div>
      <h2>{current.title}</h2>
      {current.body.map((p) => (
        <p key={p}>{p}</p>
      ))}
      <DisclaimerFooter />
    </section>
  );
}
