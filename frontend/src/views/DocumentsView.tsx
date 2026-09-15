import { useEffect, useState } from 'react';
import {
  api,
  type DocStatus,
  type DocWhyRequired,
  type DocumentRequirement,
  type Shipment,
} from '../services/api';
import { InfoTip } from '../components/InfoTip';

interface DocumentsViewProps {
  onOpenShipments?: () => void;
}

const STATUS_OPTIONS: DocStatus[] = ['not_started', 'draft', 'needs_review', 'ready'];

function downloadText(filename: string, text: string) {
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function DocumentsView({ onOpenShipments }: DocumentsViewProps) {
  const [templates, setTemplates] = useState<DocumentRequirement[]>([]);
  const [shipments, setShipments] = useState<Shipment[]>([]);
  const [selectedId, setSelectedId] = useState<string>('');
  const [why, setWhy] = useState<DocWhyRequired | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    const [reqs, rows] = await Promise.all([
      api.listDocumentRequirements({ origin: 'BD', destination: 'IN' }),
      api.listShipments(),
    ]);
    setTemplates(reqs);
    setShipments(rows);
    if (!selectedId && rows.length) {
      const withList = rows.find((s) => s.checklist) || rows[0];
      setSelectedId(withList.id);
    }
  };

  useEffect(() => {
    void refresh().catch((err) => setError(err instanceof Error ? err.message : 'Failed'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selected = shipments.find((s) => s.id === selectedId) || null;

  const setStatus = async (docCode: string, status: DocStatus) => {
    if (!selected) return;
    setError(null);
    try {
      await api.updateDocumentStatus(selected.id, docCode, status);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Status update failed');
    }
  };

  const showWhy = async (docCode: string) => {
    setError(null);
    try {
      setWhy(
        await api.documentWhyRequired({
          doc_code: docCode,
          origin: selected?.origin || 'BD',
          destination: selected?.destination || 'IN',
          hs: selected?.hs_code_working || undefined,
        }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Why-required lookup failed');
    }
  };

  const exportDraft = async (kind: 'commercial_invoice' | 'packing_list' | 'checklist') => {
    if (!selected) return;
    setError(null);
    try {
      const draft = await api.exportShipmentDraft(selected.id, kind);
      downloadText(draft.filename, draft.text);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Draft export failed');
    }
  };

  const withChecklist = shipments.filter((s) => s.checklist);

  return (
    <section className="panel-view">
      <p className="hint">
        Track shipping papers per clearance case, export drafts, and see why each item is listed.{' '}
        <InfoTip id="doc_templates" />
      </p>
      {error && <p className="error-banner">{error}</p>}

      <div className="section-title-row">
        <h3>Required papers</h3>
        <InfoTip id="doc_templates" />
      </div>
      <table className="data-table">
        <thead>
          <tr>
            <th>Document</th>
            <th>HS scope</th>
            <th>Required</th>
            <th>Notes</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {templates.map((t) => (
            <tr key={t.id}>
              <td>
                <strong>{t.doc_label}</strong>
                {t.doc_code === 'certificate_of_origin' && <InfoTip id="certificate_of_origin" />}
              </td>
              <td>{t.hs_code || 'All HS (corridor)'}</td>
              <td>{t.required ? 'Yes' : 'No'}</td>
              <td className="muted">{t.notes || '—'}</td>
              <td>
                <button type="button" className="linkish" onClick={() => void showWhy(t.doc_code)}>
                  Why required?
                </button>
              </td>
            </tr>
          ))}
          {templates.length === 0 && (
            <tr>
              <td colSpan={5} className="muted">
                No templates found for this trade lane.
              </td>
            </tr>
          )}
        </tbody>
      </table>

      {why && (
        <div className="drawer">
          <h3>
            Why: {why.doc_label} <InfoTip id="shipment_checklists" />
          </h3>
          <p>{why.why}</p>
          {why.source_tip && <p className="muted">{why.source_tip}</p>}
          {why.retrieval_excerpt && (
            <blockquote className="muted">{why.retrieval_excerpt}</blockquote>
          )}
          <button type="button" className="linkish" onClick={() => setWhy(null)}>
            Close
          </button>
        </div>
      )}

      <div className="section-title-row">
        <h3>Papers by clearance case</h3>
        <InfoTip id="shipment_checklists" />
      </div>
      {withChecklist.length === 0 ? (
        <p className="muted">
          No papers checklists yet. Open Clearance cases, create a case, then build the papers
          checklist.{' '}
          {onOpenShipments && (
            <button type="button" className="linkish" onClick={onOpenShipments}>
              Go to clearance cases
            </button>
          )}
        </p>
      ) : (
        <>
          <div className="toolbar">
            <label>
              Clearance case
              <select value={selectedId} onChange={(e) => setSelectedId(e.target.value)}>
                {shipments.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.title}
                    {s.checklist ? ` (${s.checklist.progress})` : ''}
                  </option>
                ))}
              </select>
            </label>
            {selected && (
              <>
                <button type="button" onClick={() => void exportDraft('commercial_invoice')}>
                  Export invoice draft
                </button>
                <button type="button" onClick={() => void exportDraft('packing_list')}>
                  Export packing list
                </button>
                <button
                  type="button"
                  onClick={() => void exportDraft('checklist')}
                  disabled={!selected.checklist}
                >
                  Export checklist
                </button>
              </>
            )}
          </div>
          {selected?.checklist ? (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Document</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {selected.checklist.items.map((i) => (
                  <tr key={i.doc_code}>
                    <td>
                      <strong>{i.doc_label}</strong>
                      {i.required ? ' *' : ''}
                      {i.notes ? <div className="muted">{i.notes}</div> : null}
                    </td>
                    <td>
                      <select
                        value={i.status || (i.done ? 'ready' : 'not_started')}
                        onChange={(e) => void setStatus(i.doc_code, e.target.value as DocStatus)}
                      >
                        {STATUS_OPTIONS.map((s) => (
                          <option key={s} value={s}>
                            {s === 'needs_review'
                              ? 'needs broker review'
                              : s.replaceAll('_', ' ')}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <button
                        type="button"
                        className="linkish"
                        onClick={() => void showWhy(i.doc_code)}
                      >
                        Why required?
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="muted">Selected clearance case has no papers checklist yet.</p>
          )}
        </>
      )}
    </section>
  );
}
