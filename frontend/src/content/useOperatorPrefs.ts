/**
 * Operator prefs: role + technical-details toggle (progressive disclosure).
 */

import { useCallback, useEffect, useState } from 'react';
import {
  isResearchRole,
  readOperatorRole,
  readShowTechnicalDetails,
  writeShowTechnicalDetails,
  type OperatorRole,
  ROLE_KEY,
} from './operatorCopy';

export function useOperatorPrefs() {
  const [role, setRole] = useState<OperatorRole>(() => readOperatorRole());
  const [showTech, setShowTech] = useState(() => readShowTechnicalDetails());

  useEffect(() => {
    const onStorage = () => {
      setRole(readOperatorRole());
      setShowTech(readShowTechnicalDetails());
    };
    window.addEventListener('storage', onStorage);
    window.addEventListener('tradegraph-prefs', onStorage);
    return () => {
      window.removeEventListener('storage', onStorage);
      window.removeEventListener('tradegraph-prefs', onStorage);
    };
  }, []);

  const setTechnicalDetails = useCallback((on: boolean) => {
    writeShowTechnicalDetails(on);
    setShowTech(on);
    window.dispatchEvent(new Event('tradegraph-prefs'));
  }, []);

  const persistRole = useCallback((next: OperatorRole) => {
    try {
      localStorage.setItem(ROLE_KEY, next);
    } catch {
      /* ignore */
    }
    setRole(next);
    window.dispatchEvent(new Event('tradegraph-prefs'));
  }, []);

  return {
    role,
    setRole: persistRole,
    showTech,
    setTechnicalDetails,
    showResearchLab: isResearchRole(role),
  };
}
