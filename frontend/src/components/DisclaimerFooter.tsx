import { OPERATOR } from '../content/operatorCopy';

interface DisclaimerFooterProps {
  compact?: boolean;
}

export function DisclaimerFooter({ compact = false }: DisclaimerFooterProps) {
  return (
    <footer className="disclaimer-footer" data-testid="disclaimer-footer" role="note">
      {compact ? OPERATOR.disclaimerShort : OPERATOR.disclaimerLong || OPERATOR.disclaimerShort}
    </footer>
  );
}
