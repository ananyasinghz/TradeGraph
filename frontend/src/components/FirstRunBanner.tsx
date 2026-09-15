import { useState } from 'react';

const STORAGE_KEY = 'tradegraph.firstRunBanner.dismissed';

interface FirstRunBannerProps {
  onOpenGlossary?: () => void;
}

export function FirstRunBanner({ onOpenGlossary }: FirstRunBannerProps) {
  const [visible, setVisible] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) !== '1';
    } catch {
      return true;
    }
  });

  if (!visible) return null;

  const dismiss = () => {
    try {
      localStorage.setItem(STORAGE_KEY, '1');
    } catch {
      /* ignore */
    }
    setVisible(false);
  };

  return (
    <div className="first-run-banner" role="status">
      <div>
        <p>
          <strong>New here?</strong> Hover any ⓘ for plain-English help — start with{' '}
          <strong>Tariff browser</strong>.
        </p>
        <p className="muted">
          Or open the Glossary for every term in one place.{' '}
          {onOpenGlossary && (
            <button type="button" className="linkish" onClick={onOpenGlossary}>
              Open Glossary
            </button>
          )}
        </p>
      </div>
      <button type="button" onClick={dismiss}>
        Dismiss
      </button>
    </div>
  );
}
