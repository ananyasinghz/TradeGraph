/** Friendly Ask mode labels for operators; research baselines live under Admin → Research. */

export type OrchestrationMode = 'adaptive' | 'direct_lookup' | 'fixed_multi' | 'always_llm';

export const ASK_USER_MODE_OPTIONS: {
  id: OrchestrationMode;
  label: string;
  hint: string;
}[] = [
  {
    id: 'adaptive',
    label: 'Quick answer',
    hint: 'Uses the minimum tools needed for a grounded reply.',
  },
  {
    id: 'direct_lookup',
    label: 'Verified lookup',
    hint: 'Structured tariff lookup only.',
  },
  {
    id: 'fixed_multi',
    label: 'Detailed explanation',
    hint: 'Runs the full multi-tool workflow with citations where available.',
  },
];

/** @deprecated use ASK_USER_MODE_OPTIONS in Ask; research uses RESEARCH_MODE_OPTIONS */
export const ASK_MODE_OPTIONS = [
  ...ASK_USER_MODE_OPTIONS,
  {
    id: 'always_llm' as const,
    label: 'LLM explanation (research)',
    hint: 'Full tools + LLM token proxy; duties stay code-based.',
  },
];

export const RESEARCH_MODE_OPTIONS = ASK_MODE_OPTIONS;

export function askModeLabel(mode: string | undefined): string {
  const found = ASK_MODE_OPTIONS.find((o) => o.id === mode);
  return found?.label || mode || 'Quick answer';
}
