/** Hash routes for clearance case focus: `#/case/:id` and list `#/cases`. */

const CASE_RE = /^\/?case\/([^/?#]+)/i;

export function parseCaseIdFromHash(hash = window.location.hash): string | null {
  const raw = hash.replace(/^#/, '').trim();
  const m = raw.match(CASE_RE);
  if (!m?.[1]) return null;
  try {
    return decodeURIComponent(m[1]);
  } catch {
    return m[1];
  }
}

export function isCasesListHash(hash = window.location.hash): boolean {
  const raw = hash.replace(/^#/, '').trim().replace(/^\//, '');
  return raw === 'cases';
}

export function navigateToCase(id: string) {
  const next = `#/case/${encodeURIComponent(id)}`;
  if (window.location.hash !== next) {
    window.location.hash = next;
  }
}

export function navigateToCasesList() {
  const next = '#/cases';
  if (window.location.hash !== next) {
    window.location.hash = next;
  }
}

export function clearCaseHash() {
  if (!window.location.hash) return;
  const id = parseCaseIdFromHash();
  if (id || isCasesListHash()) {
    const { pathname, search } = window.location;
    window.history.replaceState(null, '', `${pathname}${search}`);
  }
}
