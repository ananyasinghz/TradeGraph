/**
 * Admin / developer area: sources + ingestion (moved out of primary nav).
 */
import { SourcesView } from './SourcesView';
import { InfoTip } from '../components/InfoTip';

export function AdminView() {
  return (
    <section className="panel-view">
      <p className="hint">
        Admin tools: load official notices, review proposed rates, make them live. Day-to-day
        clearance work happens under Clearance cases. <InfoTip id="nav_sources" />
      </p>
      <SourcesView />
    </section>
  );
}
