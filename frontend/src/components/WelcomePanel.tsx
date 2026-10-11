import { useState } from 'react';
import { OPERATOR, ROLE_KEY, type OperatorRole } from '../content/operatorCopy';

const DISMISS_KEY = 'tradegraph.welcome.dismissed';

export type UserRole = OperatorRole;

const ROLES: { id: UserRole; label: string }[] = [
  { id: 'importer', label: 'Importer' },
  { id: 'exporter', label: 'Exporter' },
  { id: 'clearing_agent', label: 'Clearing agent' },
  { id: 'student', label: 'Student / researcher' },
];

interface WelcomePanelProps {
  onCreateShipment: () => void;
  onOpenGlossary?: () => void;
}

export function WelcomePanel({ onCreateShipment, onOpenGlossary }: WelcomePanelProps) {
  const [visible, setVisible] = useState(() => {
    try {
      return localStorage.getItem(DISMISS_KEY) !== '1';
    } catch {
      return true;
    }
  });
  const [role, setRole] = useState<UserRole>(() => {
    try {
      const saved = localStorage.getItem(ROLE_KEY) as UserRole | null;
      return saved && ROLES.some((r) => r.id === saved) ? saved : 'clearing_agent';
    } catch {
      return 'clearing_agent';
    }
  });

  if (!visible) return null;

  const persistRole = (next: UserRole) => {
    setRole(next);
    try {
      localStorage.setItem(ROLE_KEY, next);
      window.dispatchEvent(new Event('tradegraph-prefs'));
    } catch {
      /* ignore */
    }
  };

  const dismiss = () => {
    try {
      localStorage.setItem(DISMISS_KEY, '1');
      localStorage.setItem(ROLE_KEY, role);
      window.dispatchEvent(new Event('tradegraph-prefs'));
    } catch {
      /* ignore */
    }
    setVisible(false);
  };

  const start = () => {
    try {
      localStorage.setItem(ROLE_KEY, role);
      localStorage.setItem(DISMISS_KEY, '1');
      window.dispatchEvent(new Event('tradegraph-prefs'));
    } catch {
      /* ignore */
    }
    setVisible(false);
    onCreateShipment();
  };

  const isStudent = role === 'student';
  const caps = isStudent ? OPERATOR.welcomeCapsStudent : OPERATOR.welcomeCapsClearing;
  const blurb = isStudent ? OPERATOR.welcomeStudent : OPERATOR.welcomeClearing;

  return (
    <section className="welcome-panel" role="dialog" aria-label="Welcome to TradeGraph">
      <h2>{OPERATOR.welcomeTitle}</h2>
      <p className="muted">{blurb}</p>
      <p className="muted welcome-role-note" data-testid="welcome-role-note">
        {OPERATOR.welcomePersonaLabel}. {OPERATOR.welcomeServerRole}
      </p>
      {!isStudent ? (
        <ul className="welcome-list">
          {caps.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <ul className="welcome-list">
          {caps.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}

      <label className="welcome-role">
        I am a…
        <select value={role} onChange={(e) => persistRole(e.target.value as UserRole)}>
          {ROLES.map((r) => (
            <option key={r.id} value={r.id}>
              {r.label}
            </option>
          ))}
        </select>
      </label>

      <p className="muted">
        {OPERATOR.welcomeRoute} <strong>Bangladesh → India</strong>
      </p>

      <div className="toolbar">
        <button type="button" className="primary-cta" onClick={start}>
          {OPERATOR.welcomeCta}
        </button>
        {onOpenGlossary && (
          <button type="button" className="linkish" onClick={onOpenGlossary}>
            Browse glossary
          </button>
        )}
        <button type="button" className="linkish" onClick={dismiss}>
          Skip for now
        </button>
      </div>
    </section>
  );
}
