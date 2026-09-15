import { useEffect, useId, useRef, useState, type MouseEvent } from 'react';
import { HELP_COPY, HELP_TITLE, type HelpKey } from '../content/helpCopy';

interface InfoTipProps {
  id: HelpKey;
  className?: string;
}

export function InfoTip({ id, className }: InfoTipProps) {
  const tipId = useId();
  const rootRef = useRef<HTMLSpanElement>(null);
  const [open, setOpen] = useState(false);
  const title = HELP_TITLE[id];
  const body = HELP_COPY[id];

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    const onPointer = (event: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('pointerdown', onPointer);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('pointerdown', onPointer);
    };
  }, [open]);

  const stopNav = (event: MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();
  };

  return (
    <span
      ref={rootRef}
      className={`info-tip ${className || ''}`.trim()}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        type="button"
        className="info-tip-btn"
        aria-label={`About ${title}`}
        aria-expanded={open}
        aria-describedby={open ? tipId : undefined}
        onClick={(event) => {
          stopNav(event);
          setOpen((v) => !v);
        }}
        onMouseDown={stopNav}
      >
        i
      </button>
      {open && (
        <span id={tipId} role="tooltip" className="info-tip-popover">
          <strong className="info-tip-title">{title}</strong>
          <span className="info-tip-body">{body}</span>
        </span>
      )}
    </span>
  );
}
