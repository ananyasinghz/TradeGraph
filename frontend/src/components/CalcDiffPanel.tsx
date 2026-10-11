import type { SnapshotDiff } from '../services/api';

interface CalcDiffPanelProps {
  diff: SnapshotDiff;
  onClose: () => void;
}

export function CalcDiffPanel({ diff, onClose }: CalcDiffPanelProps) {
  const entries = Object.entries(diff.fields ?? {});

  return (
    <aside
      className="calc-diff-panel"
      data-testid="calc-diff-panel"
      role="dialog"
      aria-label="Calculation compare"
    >
      <div className="section-title-row">
        <h3>Compare calculations</h3>
        <button type="button" className="linkish" onClick={onClose}>
          Close
        </button>
      </div>
      <p data-testid="calc-diff-summary">{diff.summary}</p>
      {entries.length === 0 ? (
        <p className="muted">No field-level differences returned.</p>
      ) : (
        <table className="data-table" data-testid="calc-diff-table">
          <thead>
            <tr>
              <th>Field</th>
              <th>Before</th>
              <th>After</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([key, value]) => (
              <tr key={key}>
                <td>{key}</td>
                <td>{String(value.left ?? '—')}</td>
                <td>{String(value.right ?? '—')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </aside>
  );
}
