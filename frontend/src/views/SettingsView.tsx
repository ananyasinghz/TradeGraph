import { useEffect, useState } from 'react';
import { api } from '../services/api';
import { DisclaimerFooter } from '../components/DisclaimerFooter';
import { useAuth } from '../auth/AuthProvider';
import { useOperatorPrefs } from '../content/useOperatorPrefs';
import type { TradeView } from '../components/Sidebar';

interface SettingsViewProps {
  onNavigate?: (view: TradeView) => void;
}

export function SettingsView({ onNavigate }: SettingsViewProps) {
  const { whoami, refreshWhoAmI } = useAuth();
  const { showTech, setTechnicalDetails, showResearchLab, setRole, role } = useOperatorPrefs();
  const [displayName, setDisplayName] = useState(whoami?.display_name || '');
  const [watchlistEmail, setWatchlistEmail] = useState(true);
  const [inApp, setInApp] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setDisplayName(whoami?.display_name || '');
    const prefs = whoami?.notification_prefs || {};
    setWatchlistEmail(prefs.watchlist_email !== false);
    setInApp(prefs.in_app !== false);
  }, [whoami]);

  const saveProfile = async () => {
    setError(null);
    setMessage(null);
    try {
      await api.patchMe({
        display_name: displayName.trim() || undefined,
        notification_prefs: {
          watchlist_email: watchlistEmail,
          in_app: inApp,
        },
      });
      await refreshWhoAmI();
      setMessage('Profile saved.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed');
    }
  };

  return (
    <section className="panel-view" data-testid="settings-view">
      <h2>Settings</h2>
      <p className="hint">Profile, notification preferences, and legal links for this workspace.</p>
      {error && <p className="error-banner">{error}</p>}
      {message && <p className="muted">{message}</p>}

      <h3>Profile</h3>
      <div className="form-grid">
        <label>
          Display name
          <input
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            data-testid="settings-display-name"
          />
        </label>
        <p className="muted">
          Signed in as {whoami?.email || whoami?.actor || 'local demo'} · role{' '}
          {whoami?.role || '—'}
        </p>
      </div>

      <h3>Notification preferences</h3>
      <div className="form-grid">
        <label className="tech-details-toggle">
          <input
            type="checkbox"
            checked={inApp}
            onChange={(e) => setInApp(e.target.checked)}
          />{' '}
          In-app notifications
        </label>
        <label className="tech-details-toggle">
          <input
            type="checkbox"
            checked={watchlistEmail}
            onChange={(e) => setWatchlistEmail(e.target.checked)}
          />{' '}
          Watchlist email alerts
        </label>
        <button type="button" className="primary-cta" onClick={() => void saveProfile()}>
          Save profile & prefs
        </button>
      </div>

      <h3>Workspace display</h3>
      <div className="form-grid">
        <label className="tech-details-toggle">
          <input
            type="checkbox"
            checked={showTech}
            onChange={(e) => setTechnicalDetails(e.target.checked)}
          />{' '}
          Show technical details
        </label>
        {whoami?.role === 'admin' ? (
          <label className="tech-details-toggle">
            <input
              type="checkbox"
              checked={showResearchLab}
              onChange={(e) => setRole(e.target.checked ? 'student' : role === 'student' ? 'clearing_agent' : role)}
            />{' '}
            Show Research lab (admin)
          </label>
        ) : null}
      </div>

      <h3>Legal</h3>
      <div className="toolbar">
        {(
          [
            ['terms', 'Terms of use'],
            ['privacy', 'Privacy'],
            ['disclaimer', 'Disclaimer'],
            ['cookies', 'Cookies'],
          ] as const
        ).map(([page, label]) => (
          <button
            key={page}
            type="button"
            className="linkish"
            onClick={() => onNavigate?.('legal')}
            data-legal-page={page}
          >
            {label}
          </button>
        ))}
      </div>
      <DisclaimerFooter />
    </section>
  );
}
