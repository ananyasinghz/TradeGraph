import { useEffect, useRef, useState } from 'react';
import { api, type Shipment, type ShipmentWorkspace } from '../services/api';
import { ContextAskButton } from '../components/ContextAskButton';
import { DataConfidenceBadge } from '../components/DataConfidenceBadge';
import { InfoTip } from '../components/InfoTip';
import { docLabel, OPERATOR } from '../content/operatorCopy';
import { useOperatorPrefs } from '../content/useOperatorPrefs';

interface ShipmentsViewProps {
  focusCreate?: boolean;
  openShipmentId?: string | null;
  onFocused?: () => void;
  onOpened?: () => void;
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
  openShipmentId,
  onFocused,
  onOpened,
  onChanged,
}: ShipmentsViewProps) {
  const [list, setList] = useState<Shipment[]>([]);
  const [workspace, setWorkspace] = useState<ShipmentWorkspace | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState('Cotton T-shirts BD→IN');
  const [product, setProduct] = useState('100% cotton knitted T-shirts');
  const [hs, setHs] = useState('6109.10');
  const [asOf, setAsOf] = useState('2026-06-01');
  const [value, setValue] = useState('5000');
  const [freight, setFreight] = useState('100');
  const [insurance, setInsurance] = useState('50');
  const [tab, setTab] = useState<
    'overview' | 'classify' | 'tariff' | 'fta' | 'cost' | 'docs' | 'readiness' | 'timeline'
  >('overview');
  const [timeline, setTimeline] = useState<
    { id: string; event_type: string; summary: string; created_at: string; snapshot_id?: string | null }[]
  >([]);
  const createRef = useRef<HTMLDivElement>(null);
  const { showTech } = useOperatorPrefs();

  const refresh = async () => {
    const rows = await api.listShipments();
    setList(rows);
    onChanged?.();
  };

  const loadWorkspace = async (id: string) => {
    const ws = await api.getShipmentWorkspace(id);
    setWorkspace(ws);
    setFreight(ws.shipment.freight != null ? String(ws.shipment.freight) : '');
    setInsurance(ws.shipment.insurance != null ? String(ws.shipment.insurance) : '');
    setValue(String(ws.shipment.invoice_value));
    try {
      const tl = await api.getScenarioTimeline(id);
      setTimeline(tl.events);
    } catch {
      setTimeline([]);
    }
  };

  useEffect(() => {
    void refresh().catch((err) => setError(err instanceof Error ? err.message : 'Load failed'));
  }, []);

  useEffect(() => {
    if (focusCreate) {
      createRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      onFocused?.();
    }
  }, [focusCreate, onFocused]);

  useEffect(() => {
    if (openShipmentId) {
      void loadWorkspace(openShipmentId)
        .then(() => onOpened?.())
        .catch((err) => setError(err instanceof Error ? err.message : 'Open failed'));
    }
  }, [openShipmentId, onOpened]);

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
      await refresh();
      await loadWorkspace(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Create failed');
    }
  };

  const open = async (id: string) => {
    setError(null);
    try {
      await loadWorkspace(id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Open failed');
    }
  };

  const calculate = async (mode?: 'estimate' | 'customs') => {
    if (!workspace) return;
    setError(null);
    try {
      await api.calculateShipment(workspace.shipment.id, {
        requested_mode: mode ?? 'estimate',
      });
      await loadWorkspace(workspace.shipment.id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Calculate failed');
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

  const selected = workspace?.shipment;
  const tabs = OPERATOR.caseTabs;

  return (
    <section className="panel-view split">
      <div>
        <div ref={createRef} className="section-title-row">
          <h3>{OPERATOR.caseCreateTitle}</h3>
          <InfoTip id="shipment_workspace" />
        </div>
        {focusCreate && (
          <p className="shipment-focus-hint">
            Start here — create a clearance case to open the workspace.
          </p>
        )}
        <div className="form-grid">
          <label>
            {OPERATOR.caseTitle}
            <input value={title} onChange={(e) => setTitle(e.target.value)} />
          </label>
          <label>
            {OPERATOR.caseProduct}
            <input value={product} onChange={(e) => setProduct(e.target.value)} />
          </label>
          <label>
            <span className="label-with-tip">
              {OPERATOR.caseHs} <InfoTip id="working_hs" />
            </span>
            <input value={hs} onChange={(e) => setHs(e.target.value)} />
          </label>
          <label>
            <span className="label-with-tip">
              {OPERATOR.caseAsOf} <InfoTip id="as_of" />
            </span>
            <input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} />
          </label>
          <label>
            <span className="label-with-tip">
              {OPERATOR.caseInvoice} <InfoTip id="invoice_value" />
            </span>
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
        {error && <p className="error-banner">{error}</p>}
        <h3>{OPERATOR.caseListTitle}</h3>
        <ul className="list">
          {list.map((s) => (
            <li key={s.id}>
              <button type="button" className="linkish" onClick={() => void open(s.id)}>
                {s.title}
              </button>
              <span className="muted">
                {' '}
                {s.origin}→{s.destination} · {s.hs_code_working || 'no HS'} · {s.status}
              </span>
            </li>
          ))}
        </ul>
      </div>
      <div>
        {workspace && selected ? (
          <div>
            <div className="section-title-row">
              <h3>{selected.title}</h3>
              {workspace.readiness && (
                <span className="muted">
                  Ready {workspace.readiness.score}/100 · {workspace.readiness.band}
                </span>
              )}
            </div>
            <StepStrip selected={selected} workspace={workspace} />
            <div className="case-file-tabs">
              {(
                [
                  ['overview', tabs.overview],
                  ['classify', tabs.classify],
                  ['tariff', tabs.tariff],
                  ['fta', tabs.fta],
                  ['cost', tabs.cost],
                  ['docs', tabs.docs],
                  ['readiness', tabs.readiness],
                  ['timeline', 'Timeline'],
                ] as const
              ).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
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
                  {workspace.overview ? (
                    <div data-testid="scenario-overview">
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
                      <h4>Next actions</h4>
                      <div className="toolbar">
                        {workspace.overview.next_action_buttons.map((b) => (
                          <button
                            key={b.id}
                            type="button"
                            onClick={() =>
                              setTab(
                                b.tab as
                                  | 'overview'
                                  | 'classify'
                                  | 'tariff'
                                  | 'fta'
                                  | 'cost'
                                  | 'docs'
                                  | 'readiness'
                                  | 'timeline',
                              )
                            }
                          >
                            {b.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : (
                    <>
                      <p>
                        <strong>{selected.title}</strong> · {selected.origin}→
                        {selected.destination}
                      </p>
                      <p>{workspace.summary}</p>
                    </>
                  )}
                  <div className="toolbar" style={{ marginTop: 12 }}>
                    <button type="button" onClick={() => void watchShipment()}>
                      Watch for duty changes
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
                    Duty <InfoTip id="hs_code" />
                  </h4>
                  {workspace.tariff ? (
                    <p>
                      Rate {workspace.tariff.rate}% ·{' '}
                      <DataConfidenceBadge dataQuality={workspace.tariff.data_quality} />
                      {showTech ? (
                        <span className="muted">
                          {' '}
                          · source {workspace.tariff.source_document_id}
                        </span>
                      ) : null}
                    </p>
                  ) : (
                    <p className="muted">No duty rate resolved yet.</p>
                  )}
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
                              .then((d) =>
                                window.alert(`${d.summary}\n${JSON.stringify(d.fields, null, 2)}`),
                              )
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
                    <label className="chip">
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

              {tab === 'timeline' && (
                <>
                  <h4>Decision timeline</h4>
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
                          .then((d) =>
                            window.alert(`${d.summary}\n${JSON.stringify(d.fields, null, 2)}`),
                          )
                          .catch((err) =>
                            setError(err instanceof Error ? err.message : 'Diff failed'),
                          );
                      }}
                    >
                      Compare latest two calcs
                    </button>
                  )}
                </>
              )}

              {tab === 'readiness' && (
                <>
                  <h4>Ready to clear?</h4>
                  {workspace.readiness ? (
                    <>
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
                      {(workspace.readiness.complete_items?.length ?? 0) > 0 && (
                        <>
                          <h4>Complete</h4>
                          <ul className="list">
                            {workspace.readiness.complete_items!.map((i) => (
                              <li key={i.code}>✓ {readinessLabel(i.label)}</li>
                            ))}
                          </ul>
                        </>
                      )}
                      {(workspace.readiness.missing_items?.length ?? 0) > 0 && (
                        <>
                          <h4>Missing</h4>
                          <ul className="list">
                            {workspace.readiness.missing_items!.map((i) => (
                              <li key={i.code}>✗ {readinessLabel(i.label)}</li>
                            ))}
                          </ul>
                        </>
                      )}
                      {showTech && (
                        <ul className="list">
                          {workspace.readiness.factors.map((f) => (
                            <li key={f.code}>
                              {f.label}: {f.score}/{f.weight} — {f.detail}
                            </li>
                          ))}
                        </ul>
                      )}
                    </>
                  ) : (
                    <p className="muted">Readiness not available.</p>
                  )}
                  <h4 style={{ marginTop: 12 }}>Next</h4>
                  <ul className="list">
                    {workspace.next_actions.map((a) => (
                      <li key={a}>{a}</li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          </div>
        ) : (
          <p className="muted">{OPERATOR.caseEmpty}</p>
        )}
      </div>
    </section>
  );
}
