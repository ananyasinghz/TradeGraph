import { useEffect, useRef, useState } from 'react';
import {
  api,
  type AskHistoryItem,
  type CaseComment,
  type DutyStructure,
  type Shipment,
  type ShipmentWorkspace,
  type SnapshotDiff,
} from '../services/api';
import { CalcDiffPanel } from '../components/CalcDiffPanel';
import { CaseAskPanel, ContextAskButton } from '../components/ContextAskButton';
import { ComponentQualityBadge } from '../components/ComponentQualityBadge';
import { DataConfidenceBadge } from '../components/DataConfidenceBadge';
import { InfoTip } from '../components/InfoTip';
import { DutyCoveragePanel } from '../sources/DutyCoveragePanel';
import { ImpactsPanel } from '../sources/ImpactsPanel';
import { docLabel, OPERATOR } from '../content/operatorCopy';
import { useOperatorPrefs } from '../content/useOperatorPrefs';

type CaseTab =
  | 'overview'
  | 'product'
  | 'classify'
  | 'tariff'
  | 'fta'
  | 'cost'
  | 'docs'
  | 'evidence'
  | 'ask'
  | 'activity';

interface ShipmentsViewProps {
  focusCreate?: boolean;
  /** When set, render full-width case workspace for this id (`#/case/:id`). */
  focusCaseId?: string | null;
  onFocused?: () => void;
  onOpenCase?: (shipmentId: string) => void;
  onBackToList?: () => void;
  onCaseTitle?: (title: string | null) => void;
  onChanged?: () => void;
}

function readinessLabel(label: string): string {
  if (/human review/i.test(label)) return OPERATOR.caseReadyBroker;
  return label;
}

function StepStrip({
  selected,
  workspace,
}: {
  selected: Shipment;
  workspace: ShipmentWorkspace;
}) {
  const steps = OPERATOR.caseSteps;
  const done = [
    Boolean(selected.hs_confirmed_at || selected.hs_code_working),
    Boolean(workspace.tariff),
    Boolean(workspace.calculation),
    Boolean(workspace.checklist),
    Boolean(workspace.fta),
  ];
  return (
    <p className="hint" data-testid="scenario-progress">
      {OPERATOR.caseProgress}:{' '}
      {steps.map((label, i) => (
        <span key={label}>
          {i > 0 ? ' · ' : null}
          {done[i] ? '✓ ' : ''}
          {label}
        </span>
      ))}
      {selected.hs_confirmed_at ? ' · HS confirmed' : ' · HS not confirmed'}
      {selected.freight != null && selected.insurance != null
        ? ' · freight & insurance set'
        : ' · freight & insurance incomplete'}
    </p>
  );
}

export function ShipmentsView({
  focusCreate,
  focusCaseId = null,
  onFocused,
  onOpenCase,
  onBackToList,
  onCaseTitle,
  onChanged,
}: ShipmentsViewProps) {
  const [list, setList] = useState<Shipment[]>([]);
  const [workspace, setWorkspace] = useState<ShipmentWorkspace | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [calcDiff, setCalcDiff] = useState<SnapshotDiff | null>(null);
  const [title, setTitle] = useState('Cotton T-shirts BD→IN');
  const [product, setProduct] = useState('100% cotton knitted T-shirts');
  const [hs, setHs] = useState('6109.10');
  const [asOf, setAsOf] = useState('2026-06-01');
  const [value, setValue] = useState('5000');
  const [freight, setFreight] = useState('100');
  const [insurance, setInsurance] = useState('50');
  const [tab, setTab] = useState<CaseTab>('overview');
  const [timeline, setTimeline] = useState<
    { id: string; event_type: string; summary: string; created_at: string; snapshot_id?: string | null }[]
  >([]);
  const [askHistory, setAskHistory] = useState<AskHistoryItem[]>([]);
  const [comments, setComments] = useState<CaseComment[]>([]);
  const [commentBody, setCommentBody] = useState('');
  const [evidenceLabel, setEvidenceLabel] = useState('');
  const [evidenceExcerpt, setEvidenceExcerpt] = useState('');
  const [listFilter, setListFilter] = useState<'open' | 'closed' | 'all'>('open');
  const [dutyStructure, setDutyStructure] = useState<DutyStructure | null>(null);
  const [selectedExemptionId, setSelectedExemptionId] = useState<string>('');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const createRef = useRef<HTMLDivElement>(null);
  const { showTech } = useOperatorPrefs();

  const refresh = async (filter: 'open' | 'closed' | 'all' = listFilter) => {
    const rows = await api.listShipments(filter);
    setList(rows);
    onChanged?.();
  };

  const loadWorkspace = async (id: string): Promise<ShipmentWorkspace> => {
    const ws = await api.getShipmentWorkspace(id);
    setWorkspace(ws);
    onCaseTitle?.(ws.shipment.title);
    setFreight(ws.shipment.freight != null ? String(ws.shipment.freight) : '');
    setInsurance(ws.shipment.insurance != null ? String(ws.shipment.insurance) : '');
    setValue(String(ws.shipment.invoice_value));
    try {
      const tl = await api.getShipmentTimeline(id);
      setTimeline(tl.events);
    } catch {
      try {
        const tl = await api.getScenarioTimeline(id);
        setTimeline(tl.events);
      } catch {
        setTimeline([]);
      }
    }
    try {
      setAskHistory(await api.getAskHistory(id));
    } catch {
      setAskHistory([]);
    }
    try {
      setComments(await api.listComments(id));
    } catch {
      setComments([]);
    }
    return ws;
  };

  const loadDutyStructure = async (
    ws: ShipmentWorkspace,
    exemptionId?: string | null,
  ) => {
    const hsCode = ws.shipment.hs_code_working;
    if (!hsCode) {
      setDutyStructure(null);
      return;
    }
    const av =
      Number(ws.shipment.invoice_value) +
      Number(ws.shipment.freight ?? 0) +
      Number(ws.shipment.insurance ?? 0);
    const body = await api.getDutyStructure({
      hs: hsCode,
      origin: ws.shipment.origin,
      destination: ws.shipment.destination,
      as_of: ws.shipment.as_of_date,
      assessable_value: av > 0 ? av : ws.shipment.invoice_value,
      currency: ws.shipment.currency,
      selected_exemption_id: exemptionId || null,
      shipment_id: ws.shipment.id,
    });
    setDutyStructure(body);
    setSelectedExemptionId(body.selected_exemption_id || '');
  };

  useEffect(() => {
    if (focusCaseId) return;
    void refresh(listFilter).catch((err) => setError(err instanceof Error ? err.message : 'Load failed'));
  }, [listFilter, focusCaseId]);

  useEffect(() => {
    if (focusCreate && !focusCaseId) {
      setShowCreateForm(true);
      requestAnimationFrame(() => {
        createRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
      onFocused?.();
    }
  }, [focusCreate, focusCaseId, onFocused]);

  useEffect(() => {
    if (!focusCaseId) {
      setWorkspace(null);
      onCaseTitle?.(null);
      return;
    }
    setError(null);
    void loadWorkspace(focusCaseId)
      .then((ws) => {
        onCaseTitle?.(ws?.shipment.title ?? null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Open failed'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusCaseId]);

  const selected = workspace?.shipment ?? null;
  const caseClosed = (selected?.lifecycle || selected?.status) === 'closed';
  const caseDiscarded = (selected?.lifecycle || selected?.status) === 'discarded';
  const caseReadOnly = caseClosed || caseDiscarded;

  const closeCase = async () => {
    if (!selected) return;
    if (!window.confirm('Close this case? You can reopen it later.')) return;
    try {
      await api.closeShipment(selected.id);
      await loadWorkspace(selected.id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Close failed');
    }
  };

  const reopenCase = async () => {
    if (!selected) return;
    try {
      await api.reopenShipment(selected.id);
      await loadWorkspace(selected.id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Reopen failed');
    }
  };

  const discardCase = async () => {
    if (!selected) return;
    if (
      !window.confirm(
        'Discard this case? It will be removed from Open/Closed lists (soft-delete).',
      )
    ) {
      return;
    }
    try {
      await api.discardShipment(selected.id);
      setWorkspace(null);
      onCaseTitle?.(null);
      onBackToList?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Discard failed');
    }
  };

  const create = async () => {
    setError(null);
    try {
      const created = await api.createShipment({
        title,
        product_text: product,
        origin: 'BD',
        destination: 'IN',
        hs_code_working: hs,
        as_of_date: asOf,
        invoice_value: value,
        currency: 'USD',
        incoterm: 'CIF',
        qty: 1,
        freight: freight === '' ? null : freight,
        insurance: insurance === '' ? null : insurance,
      });
      setTab('overview');
      setShowCreateForm(false);
      if (onOpenCase) {
        onOpenCase(created.id);
        return;
      }
      await loadWorkspace(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Create failed');
    }
  };

  const open = (id: string) => {
    if (onOpenCase) {
      onOpenCase(id);
      return;
    }
    setError(null);
    void loadWorkspace(id).catch((err) =>
      setError(err instanceof Error ? err.message : 'Open failed'),
    );
  };

  useEffect(() => {
    if (!workspace || tab !== 'tariff') return;
    void loadDutyStructure(workspace, selectedExemptionId || null).catch((err) =>
      setError(err instanceof Error ? err.message : 'Duty structure failed'),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refresh on tab / HS / case id
  }, [tab, workspace?.shipment.id, workspace?.shipment.hs_code_working]);

  const calculate = async (mode?: 'estimate' | 'customs') => {
    if (!workspace) return;
    setError(null);
    try {
      await api.calculateShipment(workspace.shipment.id, {
        requested_mode: mode ?? 'estimate',
        selected_exemption_id: selectedExemptionId || null,
      });
      await loadWorkspace(workspace.shipment.id);
      await refresh();
      if (tab === 'tariff') {
        await loadDutyStructure(workspace, selectedExemptionId || null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Calculate failed');
    }
  };

  const applyExemption = async (exemptionId: string) => {
    if (!workspace) return;
    setSelectedExemptionId(exemptionId);
    setError(null);
    try {
      await loadDutyStructure(workspace, exemptionId || null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Exemption apply failed');
    }
  };

  const confirmHs = async (hsCode: string) => {
    if (!workspace) return;
    setError(null);
    try {
      await api.confirmClassification(workspace.shipment.id, hsCode);
      await loadWorkspace(workspace.shipment.id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Classification confirm failed');
    }
  };

  const checklist = async () => {
    if (!workspace) return;
    setError(null);
    try {
      await api.checklistShipment(workspace.shipment.id);
      await loadWorkspace(workspace.shipment.id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Checklist failed');
    }
  };

  const saveScenarioInputs = async () => {
    if (!workspace) return;
    setError(null);
    try {
      await api.updateShipment(workspace.shipment.id, {
        freight: freight === '' ? null : freight,
        insurance: insurance === '' ? null : insurance,
        invoice_value: value,
      });
      await loadWorkspace(workspace.shipment.id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Update failed');
    }
  };

  const watchShipment = async () => {
    if (!workspace) return;
    setError(null);
    try {
      await api.addWatchlist({ shipment_id: workspace.shipment.id });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Watch failed');
    }
  };

  const setDocStatus = async (
    docCode: string,
    status: 'not_started' | 'draft' | 'needs_review' | 'ready',
  ) => {
    if (!workspace) return;
    setError(null);
    try {
      await api.updateDocumentStatus(workspace.shipment.id, docCode, status);
      await loadWorkspace(workspace.shipment.id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Document status failed');
    }
  };

  const exportDraft = async (
    kind: 'commercial_invoice' | 'packing_list' | 'checklist',
    asPdf = false,
  ) => {
    if (!workspace) return;
    setError(null);
    try {
      const draft = await api.exportShipmentDraft(workspace.shipment.id, kind, asPdf);
      if (asPdf && draft.pdf_base64) {
        const bin = atob(draft.pdf_base64);
        const bytes = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i += 1) bytes[i] = bin.charCodeAt(i);
        const blob = new Blob([bytes], { type: 'application/pdf' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = draft.filename;
        a.click();
        URL.revokeObjectURL(url);
        return;
      }
      const blob = new Blob([draft.text], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = draft.filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Draft export failed');
    }
  };

  const uploadCoo = async (file: File | null) => {
    if (!workspace || !file) return;
    setError(null);
    try {
      await api.uploadShipmentDocument(workspace.shipment.id, 'certificate_of_origin', file);
      await loadWorkspace(workspace.shipment.id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    }
  };

  const downloadPack = async () => {
    if (!workspace) return;
    setError(null);
    try {
      await api.downloadShipmentPack(workspace.shipment.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Pack download failed');
    }
  };

  const addEvidenceItem = async () => {
    if (!workspace || !evidenceLabel.trim()) return;
    setError(null);
    try {
      await api.addEvidence(workspace.shipment.id, {
        kind: 'citation',
        label: evidenceLabel.trim(),
        excerpt: evidenceExcerpt.trim() || null,
      });
      setEvidenceLabel('');
      setEvidenceExcerpt('');
      await loadWorkspace(workspace.shipment.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Add evidence failed');
    }
  };

  const postComment = async () => {
    if (!workspace || !commentBody.trim()) return;
    setError(null);
    try {
      await api.addComment(workspace.shipment.id, commentBody.trim());
      setCommentBody('');
      setComments(await api.listComments(workspace.shipment.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Comment failed');
    }
  };

  const mapOverviewTab = (raw: string): CaseTab => {
    const t = raw.toLowerCase();
    if (t.includes('classif') || t === 'classify') return 'classify';
    if (t.includes('duty') || t === 'tariff') return 'tariff';
    if (t.includes('fta') || t.includes('prefer')) return 'fta';
    if (t.includes('cost') || t.includes('freight')) return 'cost';
    if (t.includes('paper') || t.includes('doc') || t.includes('coo')) return 'docs';
    if (t.includes('evidence')) return 'evidence';
    if (t.includes('ask')) return 'ask';
    if (t.includes('activ') || t.includes('timeline')) return 'activity';
    if (t.includes('product')) return 'product';
    return 'overview';
  };

  const tabs = OPERATOR.caseTabs;
  const blockedReasons = workspace?.readiness?.blocked_reasons || [];
  const nextActions = workspace?.next_actions || [];

  if (!focusCaseId) {
    return (
      <section className="panel-view case-list" data-testid="case-list">
        <div className="section-title-row">
          <h3>{OPERATOR.caseListTitle}</h3>
          <div className="chip-row">
            {(['open', 'closed', 'all'] as const).map((f) => (
              <button
                key={f}
                type="button"
                className={`chip${listFilter === f ? ' chip-active' : ''}`}
                onClick={() => setListFilter(f)}
              >
                {f === 'open' ? 'Open' : f === 'closed' ? 'Closed' : 'All'}
              </button>
            ))}
          </div>
        </div>
        {!showCreateForm ? (
          <div className="quick-actions" style={{ marginTop: 8, marginBottom: 12 }}>
            <button
              type="button"
              className="primary-cta"
              data-testid="case-new-btn"
              onClick={() => setShowCreateForm(true)}
            >
              {OPERATOR.homeNewCase}
            </button>
          </div>
        ) : (
          <div ref={createRef} className="case-create-block">
            <div className="section-title-row">
              <h3>{OPERATOR.caseCreateTitle}</h3>
              <button
                type="button"
                className="linkish"
                onClick={() => setShowCreateForm(false)}
              >
                Cancel
              </button>
            </div>
            <div className="form-grid" data-testid="case-create-form">
              <label>
                {OPERATOR.caseTitle}
                <input
                  data-testid="case-title-input"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </label>
              <label>
                {OPERATOR.caseProduct}
                <input
                  data-testid="case-product-input"
                  value={product}
                  onChange={(e) => setProduct(e.target.value)}
                />
              </label>
              <label>
                {OPERATOR.caseHs}
                <input value={hs} onChange={(e) => setHs(e.target.value)} />
              </label>
              <label>
                {OPERATOR.caseAsOf}
                <input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} />
              </label>
              <label>
                {OPERATOR.caseInvoice}
                <input value={value} onChange={(e) => setValue(e.target.value)} />
              </label>
              <label>
                {OPERATOR.caseFreight} (USD)
                <input value={freight} onChange={(e) => setFreight(e.target.value)} />
              </label>
              <label>
                {OPERATOR.caseInsurance} (USD)
                <input value={insurance} onChange={(e) => setInsurance(e.target.value)} />
              </label>
              <button type="button" className="primary-cta" onClick={() => void create()}>
                {OPERATOR.caseCreateCta}
              </button>
            </div>
          </div>
        )}
        {error && <p className="error-banner">{error}</p>}
        <ul className="list">
          {list.map((s) => {
            const life = s.lifecycle || (s.status === 'closed' ? 'closed' : 'open');
            return (
              <li key={s.id}>
                <button
                  type="button"
                  className="linkish"
                  data-testid={`case-row-${s.id}`}
                  data-case-title={s.title}
                  onClick={() => open(s.id)}
                >
                  {s.title}
                </button>
                <span className={`status-chip${life === 'closed' ? '' : ' status-chip--active'}`}>
                  {life === 'closed' ? 'Closed' : 'Open'}
                </span>
                <span className="muted">
                  {' '}
                  {s.origin}→{s.destination} · {s.hs_code_working || 'no HS'}
                </span>
              </li>
            );
          })}
        </ul>
        {list.length === 0 ? <p className="muted">{OPERATOR.caseEmpty}</p> : null}
      </section>
    );
  }

  return (
    <section className="panel-view case-focus" data-testid="case-focus">
      <div className="case-focus-bar">
        <button
          type="button"
          className="linkish"
          data-testid="case-back-all"
          onClick={() => onBackToList?.()}
        >
          ← {OPERATOR.queueAll}
        </button>
      </div>
      {error && <p className="error-banner">{error}</p>}
      {workspace && selected ? (
          <div data-testid="case-workspace">
            <div className="section-title-row">
              <h3>
                {selected.title}{' '}
                <span className={`status-chip${caseClosed ? '' : ' status-chip--active'}`}>
                  {caseDiscarded ? 'Discarded' : caseClosed ? 'Closed' : 'Open'}
                </span>
              </h3>
              {workspace.readiness && (
                <span className="muted">
                  Ready {workspace.readiness.score}/100 · {workspace.readiness.band}
                </span>
              )}
            </div>
            <div className="toolbar" style={{ marginBottom: 8 }}>
              {!caseReadOnly && (
                <>
                  <button type="button" className="btn-secondary" onClick={() => void closeCase()}>
                    Close case
                  </button>
                  <button type="button" className="btn-secondary" onClick={() => void discardCase()}>
                    Discard case
                  </button>
                </>
              )}
              {caseClosed && !caseDiscarded && (
                <button type="button" className="primary-cta" onClick={() => void reopenCase()}>
                  Reopen case
                </button>
              )}
            </div>
            {caseReadOnly && (
              <p className="hint">
                {caseDiscarded
                  ? 'This case was discarded. Create a new case to continue.'
                  : 'This case is closed. Reopen it to edit classification, costs, or documents.'}
              </p>
            )}
            <StepStrip selected={selected} workspace={workspace} />
            <div className="next-action-bar" data-testid="next-action-bar">
              <strong>{OPERATOR.nextActionBar}</strong>
              {blockedReasons.length > 0 ? (
                <ul className="next-action-bar__blocked">
                  {blockedReasons.map((r) => (
                    <li key={r}>{r}</li>
                  ))}
                </ul>
              ) : null}
              {nextActions.length > 0 ? (
                <div className="chip-row">
                  {nextActions.slice(0, 4).map((a) => (
                    <span key={a} className="status-chip status-chip--active">
                      {a}
                    </span>
                  ))}
                </div>
              ) : (
                <span className="muted">No blocked actions — review readiness on Overview.</span>
              )}
              {workspace.overview?.next_action_buttons?.length ? (
                <div className="toolbar">
                  {workspace.overview.next_action_buttons.map((b) => (
                    <button
                      key={b.id}
                      type="button"
                      className="chip"
                      onClick={() => setTab(mapOverviewTab(b.tab || b.id))}
                    >
                      {b.label}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
            <div className="case-file-tabs" data-testid="case-file-tabs">
              {(
                [
                  ['overview', tabs.overview],
                  ['product', tabs.product],
                  ['classify', tabs.classify],
                  ['tariff', tabs.tariff],
                  ['fta', tabs.fta],
                  ['cost', tabs.cost],
                  ['docs', tabs.docs],
                  ['evidence', tabs.evidence],
                  ['ask', tabs.ask],
                  ['activity', tabs.activity],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  data-testid={`case-tab-${id}`}
                  className={`case-file-tab${tab === id ? ' active' : ''}`}
                  onClick={() => setTab(id)}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="case-file-tab-panel workspace-step">
              {tab === 'overview' && (
                <>
                  <div data-testid="scenario-overview">
                  {workspace.overview ? (
                    <>
                      <div className="chip-row" style={{ marginBottom: 12 }}>
                        {workspace.overview.status_chips.map((c) => (
                          <span key={c} className="status-chip status-chip--active">
                            {c}
                          </span>
                        ))}
                      </div>
                      <h4>Trade summary</h4>
                      <ul className="list">
                        <li>Origin: {String(workspace.overview.trade_summary.origin)}</li>
                        <li>Destination: {String(workspace.overview.trade_summary.destination)}</li>
                        <li>
                          Working HS: {String(workspace.overview.trade_summary.working_hs || '—')}
                        </li>
                        <li>Regime: {String(workspace.overview.trade_summary.regime)}</li>
                        <li>
                          Customs value: {String(workspace.overview.trade_summary.customs_value)}{' '}
                          {String(workspace.overview.trade_summary.currency)}
                        </li>
                      </ul>
                      <h4>Decision result</h4>
                      <ul className="list">
                        <li>
                          Estimated duty:{' '}
                          {String(workspace.overview.decision_result.estimated_duty ?? '—')}{' '}
                          {String(workspace.overview.decision_result.currency || '')}
                        </li>
                        <li>
                          Landed cost:{' '}
                          {String(workspace.overview.decision_result.landed_cost ?? '—')}{' '}
                          {String(workspace.overview.decision_result.currency || '')}
                        </li>
                        <li>
                          Tariff source:{' '}
                          {String(workspace.overview.decision_result.tariff_source ?? '—')}
                        </li>
                        <li>
                          Source date:{' '}
                          {String(workspace.overview.decision_result.source_date ?? '—')}
                        </li>
                        {showTech ? (
                          <li>
                            Calculation snapshot:{' '}
                            {String(
                              workspace.overview.decision_result.calculation_snapshot_id ?? '—',
                            )}
                          </li>
                        ) : null}
                      </ul>
                      <h4>Why this result?</h4>
                      <ul className="list">
                        {workspace.overview.why_this_result.map((w) => (
                          <li key={w}>{w}</li>
                        ))}
                      </ul>
                      <h4>Missing evidence</h4>
                      {workspace.overview.missing_evidence.length === 0 ? (
                        <p className="muted">No missing evidence items.</p>
                      ) : (
                        <ul className="list">
                          {workspace.overview.missing_evidence.map((m) => (
                            <li key={m}>✗ {m}</li>
                          ))}
                        </ul>
                      )}
                      {(workspace.overview.recent_changes?.length ?? 0) > 0 && (
                        <>
                          <h4>Recent changes</h4>
                          <ul className="list">
                            {workspace.overview.recent_changes.map((r, idx) => (
                              <li key={String(r.impact_id || idx)}>{String(r.summary)}</li>
                            ))}
                          </ul>
                        </>
                      )}
                    </>
                  ) : (
                    <>
                      <p>
                        <strong>{selected.title}</strong> · {selected.origin}→
                        {selected.destination}
                      </p>
                      <p>{workspace.summary}</p>
                    </>
                  )}
                  </div>
                  {workspace.readiness ? (
                    <div style={{ marginTop: 12 }}>
                      <h4>Ready to clear?</h4>
                      <p>
                        <strong>{workspace.readiness.score}/100</strong> ·{' '}
                        {workspace.readiness.band}
                      </p>
                      {(workspace.readiness.statuses?.length ?? 0) > 0 && (
                        <div className="chip-row" data-testid="readiness-statuses">
                          {workspace.readiness.statuses!.map((s) => (
                            <span
                              key={s.code}
                              className={`status-chip${s.active ? ' status-chip--active' : ''}`}
                              title={s.detail}
                            >
                              {s.active ? '●' : '○'} {readinessLabel(s.label)}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ) : null}
                  <div className="toolbar" style={{ marginTop: 12 }}>
                    <button type="button" onClick={() => void watchShipment()}>
                      Watch for duty changes
                    </button>
                    <button
                      type="button"
                      className="chip"
                      onClick={() =>
                        void api
                          .createShareLink(selected.id)
                          .then((link) => {
                            const url = `${window.location.origin}/?share=${link.token}`;
                            void navigator.clipboard?.writeText(url);
                            window.alert(`Client share link copied:\n${url}`);
                          })
                          .catch((err) =>
                            setError(err instanceof Error ? err.message : 'Share failed'),
                          )
                      }
                    >
                      Create client share link
                    </button>
                  </div>
                  <ContextAskButton
                    label="What is missing from this clearance case?"
                    focus="shipment_gaps"
                    shipmentId={selected.id}
                    hsCode={selected.hs_code_working || undefined}
                    asOf={selected.as_of_date}
                  />
                  <ul className="risk-list">
                    {workspace.risks.map((r) => (
                      <li
                        key={r.code}
                        className={r.severity === 'info' && r.code === 'ok' ? 'ok' : ''}
                      >
                        <strong>{r.severity}</strong>: {r.message}
                      </li>
                    ))}
                  </ul>
                </>
              )}

              {tab === 'product' && (
                <>
                  <h4>Product</h4>
                  <p>{selected.product_text}</p>
                  <p className="muted">
                    Working HS {selected.hs_code_working || '—'} · qty {selected.qty} · invoice{' '}
                    {selected.invoice_value} {selected.currency}
                  </p>
                  <h4>Line items</h4>
                  {(selected.line_items?.length ?? 0) === 0 ? (
                    <p className="muted">No separate line items — product text is the case line.</p>
                  ) : (
                    <ul className="list" data-testid="line-items">
                      {selected.line_items!.map((li) => (
                        <li key={li.id}>
                          #{li.line_number} {li.description}
                          {li.hs_code ? ` · HS ${li.hs_code}` : ''} · qty {li.qty}
                          {!caseReadOnly ? (
                            <button
                              type="button"
                              className="linkish"
                              style={{ marginLeft: 8 }}
                              onClick={() =>
                                void api
                                  .deleteLineItem(selected.id, li.id)
                                  .then(() => loadWorkspace(selected.id))
                                  .catch((err) =>
                                    setError(err instanceof Error ? err.message : 'Delete failed'),
                                  )
                              }
                            >
                              Remove
                            </button>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  )}
                </>
              )}

              {tab === 'classify' && (
                <>
                  <h4>
                    Classify product <InfoTip id="working_hs" />
                  </h4>
                  <p>
                    Working HS: <strong>{selected.hs_code_working || 'pending'}</strong> · as of{' '}
                    {selected.as_of_date}
                  </p>
                  {(workspace.classification_candidates?.length ?? 0) > 0 ? (
                    <ul className="list">
                      {workspace.classification_candidates!.map((c) => (
                        <li key={c.hs_code}>
                          <strong>{c.hs_code}</strong> · {c.confidence_label} · score {c.score}
                          <div className="muted">{c.description}</div>
                          <button
                            type="button"
                            className="chip"
                            disabled={caseReadOnly}
                            onClick={() => void confirmHs(c.hs_code)}
                          >
                            Confirm HS
                          </button>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="muted">
                      No HS suggestions for this product text (no FTS / synonym hits). Try richer
                      wording: material (cotton, linen), knit or woven, and garment type
                      (T-shirt, trousers, screws). Confirm a code manually only if it is in the
                      catalog.
                    </p>
                  )}
                </>
              )}

              {tab === 'tariff' && (
                <>
                  <h4>
                    Duty structure <InfoTip id="hs_code" />
                  </h4>
                  {workspace.tariff ? (
                    <p>
                      MFN BCD {workspace.tariff.rate}% ·{' '}
                      <DataConfidenceBadge dataQuality={workspace.tariff.data_quality} />
                      {showTech ? (
                        <span className="muted">
                          {' '}
                          · source {workspace.tariff.source_document_id}
                        </span>
                      ) : null}
                    </p>
                  ) : (
                    <p className="muted">No duty rate resolved yet — confirm an HS with a seeded rate.</p>
                  )}
                  {dutyStructure ? (
                    <>
                      <p className="muted">{dutyStructure.honesty_note}</p>
                      {dutyStructure.preferential_blocked_reason ? (
                        <p className="muted" data-testid="preferential-blocked">
                          {dutyStructure.preferential_blocked_reason}
                        </p>
                      ) : null}
                      <div className="table-wrap">
                        <table className="data-table" data-testid="duty-stack-table">
                          <thead>
                            <tr>
                              <th>Component</th>
                              <th>Tariff %</th>
                              <th>Effective %</th>
                              <th>Amount</th>
                              <th>Source quality</th>
                              <th>Notification / Sl.</th>
                            </tr>
                          </thead>
                          <tbody>
                            {dutyStructure.stack.map((row) => (
                              <tr key={row.code}>
                                <td>{row.display_name}</td>
                                <td>{row.tariff_rate_pct}</td>
                                <td>{row.effective_rate_pct}</td>
                                <td>
                                  {row.amount} {dutyStructure.currency}
                                </td>
                                <td>
                                  <ComponentQualityBadge
                                    quality={row.data_quality}
                                    testId={`component-quality-${row.code}`}
                                    title={row.provenance_notes || row.source_key || undefined}
                                  />
                                </td>
                                <td>{row.notification_sl || '—'}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      {(dutyStructure.component_sources?.length ?? 0) > 0 && (
                        <ul className="list" data-testid="component-sources">
                          {dutyStructure.component_sources!.map((src) => (
                            <li key={src.component_key}>
                              <strong>{src.component_key}</strong> ·{' '}
                              {src.value != null ? `${src.value}%` : 'missing'} ·{' '}
                              <ComponentQualityBadge quality={src.data_quality} />
                              {src.source_key ? (
                                <span className="muted"> · {src.source_key}</span>
                              ) : null}
                            </li>
                          ))}
                        </ul>
                      )}
                      <p>
                        Total duties <strong>{dutyStructure.total_duties}</strong>{' '}
                        {dutyStructure.currency}
                        {Number(dutyStructure.duty_savings) > 0 ? (
                          <>
                            {' '}
                            · Savings vs MFN{' '}
                            <strong>{dutyStructure.duty_savings}</strong>{' '}
                            {dutyStructure.currency}
                          </>
                        ) : null}
                      </p>
                      <h4>Select exemption Notn. (if any)</h4>
                      <p className="muted">
                        Only seeded Sl. Nos. appear here — never invented by Ask/LLM.
                      </p>
                      <label>
                        Exemption Sl. No.
                        <select
                          value={selectedExemptionId}
                          disabled={caseReadOnly}
                          onChange={(e) => void applyExemption(e.target.value)}
                        >
                          <option value="">MFN (no exemption)</option>
                          {dutyStructure.exemptions.map((ex) => (
                            <option
                              key={ex.id}
                              value={ex.id}
                              disabled={ex.eligibility === 'not_eligible'}
                            >
                              {ex.notification_id} Sl. {ex.serial_no} — {ex.eligibility.replaceAll('_', ' ')}
                            </option>
                          ))}
                        </select>
                      </label>
                      {(dutyStructure.exemptions.length ?? 0) > 0 && (
                        <ul className="list" data-testid="exemption-list">
                          {dutyStructure.exemptions.map((ex) => (
                            <li key={ex.id}>
                              <strong>
                                {ex.notification_id} Sl. {ex.serial_no}
                              </strong>{' '}
                              · {ex.eligibility.replaceAll('_', ' ')} — {ex.condition_detail || ex.label}
                              {ex.eligibility_reason ? (
                                <span className="muted"> ({ex.eligibility_reason})</span>
                              ) : null}
                            </li>
                          ))}
                        </ul>
                      )}
                      <div className="toolbar">
                        <button
                          type="button"
                          disabled={caseReadOnly}
                          onClick={() => void calculate('estimate')}
                        >
                          Recalculate landed cost with selection
                        </button>
                      </div>
                      <DutyCoveragePanel
                        origin={workspace.shipment.origin}
                        destination={workspace.shipment.destination}
                      />
                      <ImpactsPanel compact />
                    </>
                  ) : workspace.shipment.hs_code_working ? (
                    <p className="muted">Loading duty structure…</p>
                  ) : null}
                </>
              )}

              {tab === 'fta' && (
                <>
                  <h4>
                    Preferential / FTA <InfoTip id="preferential_vs_mfn" />
                  </h4>
                  {workspace.fta ? (
                    <>
                      <p>
                        Status <strong>{workspace.fta.status}</strong> · MFN{' '}
                        {workspace.fta.mfn_rate_pct}% → preferential{' '}
                        {workspace.fta.preferential_rate_pct}% · {workspace.fta.agreement_name}
                      </p>
                      <p className="muted">{workspace.fta.roo_summary}</p>
                      {(workspace.fta.conditions?.length ?? 0) > 0 && (
                        <ul className="list">
                          {workspace.fta.conditions!.map((c) => (
                            <li key={c.id}>
                              <strong>{c.status}</strong>: {c.label} — {c.detail}
                            </li>
                          ))}
                        </ul>
                      )}
                      <div className="toolbar">
                        <button
                          type="button"
                          className="chip"
                          onClick={() =>
                            void api
                              .compareFta(selected.id)
                              .then((cmp) => setCalcDiff(cmp.diff))
                              .catch((err) =>
                                setError(err instanceof Error ? err.message : 'FTA compare failed'),
                              )
                          }
                        >
                          Compare MFN vs preferential
                        </button>
                      </div>
                    </>
                  ) : (
                    <p className="muted">Preferential check unavailable for this case.</p>
                  )}
                </>
              )}

              {tab === 'cost' && (
                <>
                  <h4>
                    Landed cost <InfoTip id="landed_cost" />
                  </h4>
                  <p className="muted">
                    Save freight and insurance below. Invoice {selected.invoice_value}{' '}
                    {selected.currency}.
                  </p>
                  <div className="form-grid">
                    <label>
                      {OPERATOR.caseFreight}
                      <input value={freight} onChange={(e) => setFreight(e.target.value)} />
                    </label>
                    <label>
                      {OPERATOR.caseInsurance}
                      <input value={insurance} onChange={(e) => setInsurance(e.target.value)} />
                    </label>
                    <button type="button" onClick={() => void saveScenarioInputs()}>
                      {OPERATOR.caseSaveInputs}
                    </button>
                  </div>
                  <div className="toolbar">
                    <button type="button" onClick={() => void calculate('estimate')}>
                      {OPERATOR.caseEstimate}
                    </button>
                    <button
                      type="button"
                      disabled={!workspace.customs_mode_available}
                      title={workspace.customs_mode_hint || undefined}
                      onClick={() => void calculate('customs')}
                    >
                      {workspace.tariff?.data_quality === 'demo_verified' ||
                      workspace.tariff?.data_quality === 'source_verified'
                        ? OPERATOR.caseVerified
                        : OPERATOR.caseFiling}
                    </button>
                  </div>
                  {!workspace.customs_mode_available && (
                    <div className="error-banner" role="status">
                      <strong>{OPERATOR.caseFiling} unavailable.</strong>{' '}
                      {workspace.customs_mode_hint || OPERATOR.caseFilingBlocked}
                      {(workspace.customs_mode_blockers?.length ?? 0) > 0 && (
                        <ul className="warn-list">
                          {workspace.customs_mode_blockers!.map((b) => (
                            <li key={b}>{b}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                  {workspace.calculation ? (
                    <p>
                      <strong>{workspace.calculation.title || 'Landed cost'}</strong> ·{' '}
                      {workspace.calculation.calculation_mode === 'customs'
                        ? OPERATOR.caseFiling
                        : OPERATOR.caseEstimate}{' '}
                      · <strong>{workspace.calculation.landed_cost}</strong>{' '}
                      {workspace.calculation.currency}
                    </p>
                  ) : (
                    <p className="muted">Not calculated yet.</p>
                  )}
                  {(workspace.calculation_snapshots?.length ?? 0) > 0 && (
                    <>
                      <h4>{OPERATOR.caseHistory}</h4>
                      <ul className="list" data-testid="calc-history">
                        {workspace.calculation_snapshots!.slice(0, 8).map((s) => (
                          <li key={s.id}>
                            Saved calc · {new Date(s.created_at).toLocaleDateString()} ·{' '}
                            {s.outputs.landed_cost} {s.outputs.currency} ·{' '}
                            {s.calculation_mode === 'customs'
                              ? OPERATOR.caseFiling
                              : OPERATOR.caseEstimate}{' '}
                            ·{' '}
                            <DataConfidenceBadge dataQuality={s.data_quality} />
                            {showTech ? (
                              <span className="muted">
                                {' '}
                                · engine {s.calculation_engine_version || 'in_duty.v1'} · id{' '}
                                <code>{s.id.slice(0, 8)}</code>
                              </span>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                      {workspace.calculation_snapshots!.length >= 2 && (
                        <button
                          type="button"
                          className="chip"
                          onClick={() => {
                            const [a, b] = workspace.calculation_snapshots!;
                            void api
                              .diffCalculations(b.id, a.id)
                              .then((d) => setCalcDiff(d))
                              .catch((err) =>
                                setError(err instanceof Error ? err.message : 'Diff failed'),
                              );
                          }}
                        >
                          {OPERATOR.caseDiff}
                        </button>
                      )}
                    </>
                  )}
                </>
              )}

              {tab === 'docs' && (
                <>
                  <h4>
                    Shipping papers <InfoTip id="checklist_build" />
                  </h4>
                  <div className="toolbar">
                    <button type="button" onClick={() => void checklist()}>
                      {OPERATOR.caseBuildChecklist}
                    </button>
                    <button
                      type="button"
                      className="primary-cta"
                      data-testid="download-pack"
                      onClick={() => void downloadPack()}
                    >
                      {OPERATOR.downloadPack}
                    </button>
                    <button type="button" onClick={() => void exportDraft('commercial_invoice')}>
                      Commercial invoice .txt
                    </button>
                    <button
                      type="button"
                      onClick={() => void exportDraft('commercial_invoice', true)}
                    >
                      Commercial invoice PDF
                    </button>
                    <button type="button" onClick={() => void exportDraft('packing_list', true)}>
                      Packing list PDF
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        void api
                          .exportSummaryPdf(selected.id)
                          .catch((err) =>
                            setError(err instanceof Error ? err.message : 'PDF export failed'),
                          )
                      }
                    >
                      Summary PDF
                    </button>
                    <button
                      type="button"
                      onClick={() =>
                        void api
                          .exportCostCsv(selected.id)
                          .catch((err) =>
                            setError(err instanceof Error ? err.message : 'CSV export failed'),
                          )
                      }
                    >
                      Cost CSV
                    </button>
                    <label className="chip" data-testid="upload-coo">
                      Upload CoO
                      <input
                        type="file"
                        style={{ display: 'none' }}
                        onChange={(e) => void uploadCoo(e.target.files?.[0] || null)}
                      />
                    </label>
                  </div>
                  {(workspace.uploads?.length ?? 0) > 0 && (
                    <ul className="list">
                      {workspace.uploads!.map((u) => (
                        <li key={u.id}>
                          {docLabel(u.doc_code)} · {u.filename}
                          {showTech ? (
                            <span className="muted"> · {u.checksum.slice(0, 12)}…</span>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  )}
                  {workspace.checklist ? (
                    <>
                      <p>Progress {workspace.checklist.progress}</p>
                      <ul>
                        {workspace.checklist.items.map((i) => (
                          <li key={i.doc_code}>
                            {i.doc_label || docLabel(i.doc_code)}
                            {i.required ? ' *' : ''}
                            <select
                              style={{ marginLeft: 8 }}
                              value={i.status || (i.done ? 'ready' : 'not_started')}
                              onChange={(e) =>
                                void setDocStatus(
                                  i.doc_code,
                                  e.target.value as
                                    | 'not_started'
                                    | 'draft'
                                    | 'needs_review'
                                    | 'ready',
                                )
                              }
                            >
                              <option value="not_started">not started</option>
                              <option value="draft">draft</option>
                              <option value="needs_review">needs broker review</option>
                              <option value="ready">ready</option>
                            </select>
                          </li>
                        ))}
                      </ul>
                    </>
                  ) : (
                    <p className="muted">Papers checklist not built yet.</p>
                  )}
                </>
              )}

              {tab === 'evidence' && (
                <>
                  <h4>Evidence</h4>
                  <p className="muted">Citations and supporting excerpts attached to this case.</p>
                  {(selected.evidence?.length ?? 0) === 0 ? (
                    <p className="muted">No evidence items yet.</p>
                  ) : (
                    <ul className="list" data-testid="evidence-list">
                      {selected.evidence!.map((e) => (
                        <li key={e.id}>
                          <strong>{e.label}</strong> · {e.kind} · {e.status}
                          {e.excerpt ? <div className="muted">{e.excerpt}</div> : null}
                        </li>
                      ))}
                    </ul>
                  )}
                  {!caseReadOnly && (
                    <div className="form-grid" data-testid="evidence-add">
                      <label>
                        Label
                        <input
                          value={evidenceLabel}
                          onChange={(e) => setEvidenceLabel(e.target.value)}
                          placeholder="e.g. CoO scan reference"
                        />
                      </label>
                      <label>
                        Excerpt / note
                        <input
                          value={evidenceExcerpt}
                          onChange={(e) => setEvidenceExcerpt(e.target.value)}
                        />
                      </label>
                      <button type="button" onClick={() => void addEvidenceItem()}>
                        Add evidence
                      </button>
                    </div>
                  )}
                </>
              )}

              {tab === 'ask' && (
                <>
                  <CaseAskPanel
                    shipmentId={selected.id}
                    hsCode={selected.hs_code_working || undefined}
                    asOf={selected.as_of_date}
                    origin={selected.origin}
                    destination={selected.destination}
                  />
                  <h4 style={{ marginTop: 16 }}>Ask history</h4>
                  {askHistory.length === 0 ? (
                    <p className="muted">No prior Ask runs on this case.</p>
                  ) : (
                    <ul className="list" data-testid="ask-history">
                      {askHistory.map((h) => (
                        <li key={h.ask_run_id}>
                          <strong>{new Date(h.created_at).toLocaleString()}</strong> · {h.query}
                          {h.answer ? <div>{h.answer}</div> : null}
                          {h.next_action ? (
                            <div className="muted">Next: {h.next_action}</div>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  )}
                </>
              )}

              {tab === 'activity' && (
                <>
                  <h4>Activity / timeline</h4>
                  {!caseReadOnly && (
                    <div className="toolbar" style={{ marginBottom: 8 }}>
                      <button type="button" className="btn-secondary" onClick={() => void closeCase()}>
                        Mark case closed
                      </button>
                    </div>
                  )}
                  {caseClosed && !caseDiscarded && (
                    <div className="toolbar" style={{ marginBottom: 8 }}>
                      <button type="button" className="primary-cta" onClick={() => void reopenCase()}>
                        Reopen case
                      </button>
                    </div>
                  )}
                  {timeline.length === 0 ? (
                    <p className="muted">No timeline events yet.</p>
                  ) : (
                    <ul className="list" data-testid="scenario-timeline">
                      {timeline.map((e) => (
                        <li key={e.id}>
                          <strong>{new Date(e.created_at).toLocaleString()}</strong> · {e.event_type}
                          <div>{e.summary}</div>
                        </li>
                      ))}
                    </ul>
                  )}
                  {timeline.filter((e) => e.snapshot_id).length >= 2 && (
                    <button
                      type="button"
                      className="chip"
                      onClick={() => {
                        const snaps = timeline.filter((e) => e.snapshot_id);
                        const [a, b] = snaps;
                        void api
                          .diffCalculations(b.snapshot_id!, a.snapshot_id!)
                          .then((d) => setCalcDiff(d))
                          .catch((err) =>
                            setError(err instanceof Error ? err.message : 'Diff failed'),
                          );
                      }}
                    >
                      Compare latest two calcs
                    </button>
                  )}
                  <h4 style={{ marginTop: 16 }}>Comments</h4>
                  {comments.length === 0 ? (
                    <p className="muted">No comments yet.</p>
                  ) : (
                    <ul className="list" data-testid="case-comments">
                      {comments.map((c) => (
                        <li key={c.id}>
                          <strong>{c.author_actor}</strong> ·{' '}
                          {new Date(c.created_at).toLocaleString()}
                          <div>{c.body}</div>
                        </li>
                      ))}
                    </ul>
                  )}
                  {!caseReadOnly && (
                    <div className="toolbar">
                      <input
                        value={commentBody}
                        onChange={(e) => setCommentBody(e.target.value)}
                        placeholder="Add a case comment…"
                        style={{ flex: 1, minWidth: 200 }}
                      />
                      <button type="button" onClick={() => void postComment()}>
                        Post comment
                      </button>
                    </div>
                  )}
                </>
              )}

            </div>
          </div>
      ) : (
        <p className="muted">Loading case…</p>
      )}
      {calcDiff && <CalcDiffPanel diff={calcDiff} onClose={() => setCalcDiff(null)} />}
    </section>
  );
}
