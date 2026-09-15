import type { FC } from 'react';
import {
  Bell,
  BookOpen,
  Calculator,
  FileText,
  FlaskConical,
  Handshake,
  LayoutDashboard,
  MessageSquare,
  Package,
  Settings,
  Table2,
} from 'lucide-react';
import { InfoTip } from './InfoTip';
import type { HelpKey } from '../content/helpCopy';
import { OPERATOR } from '../content/operatorCopy';

export type TradeView =
  | 'dashboard'
  | 'shipments'
  | 'tariffs'
  | 'calculator'
  | 'agreements'
  | 'watchlist'
  | 'documents'
  | 'ask'
  | 'glossary'
  | 'admin'
  | 'research';

interface SidebarProps {
  currentView: TradeView;
  onViewChange: (view: TradeView) => void;
  showResearchLab?: boolean;
}

const PRIMARY: { id: TradeView; label: string; tip: HelpKey; icon: typeof LayoutDashboard }[] = [
  { id: 'dashboard', label: OPERATOR.nav.home, tip: 'nav_dashboard', icon: LayoutDashboard },
  { id: 'shipments', label: OPERATOR.nav.cases, tip: 'nav_shipments', icon: Package },
  { id: 'tariffs', label: OPERATOR.nav.duty, tip: 'nav_tariffs', icon: Table2 },
  { id: 'calculator', label: OPERATOR.nav.landed, tip: 'nav_calculator', icon: Calculator },
  { id: 'agreements', label: OPERATOR.nav.fta, tip: 'nav_agreements', icon: Handshake },
  { id: 'documents', label: OPERATOR.nav.papers, tip: 'nav_documents', icon: FileText },
  { id: 'watchlist', label: OPERATOR.nav.alerts, tip: 'nav_watchlist', icon: Bell },
  { id: 'ask', label: OPERATOR.nav.ask, tip: 'nav_ask', icon: MessageSquare },
  { id: 'glossary', label: OPERATOR.nav.glossary, tip: 'nav_glossary', icon: BookOpen },
];

const ADMIN_BASE: { id: TradeView; label: string; tip: HelpKey; icon: typeof LayoutDashboard }[] = [
  { id: 'admin', label: OPERATOR.nav.admin, tip: 'nav_sources', icon: Settings },
];

const RESEARCH_ITEM = {
  id: 'research' as TradeView,
  label: OPERATOR.nav.research,
  tip: 'nav_research' as HelpKey,
  icon: FlaskConical,
};

export const Sidebar: FC<SidebarProps> = ({
  currentView,
  onViewChange,
  showResearchLab = false,
}) => {
  const adminItems = showResearchLab ? [...ADMIN_BASE, RESEARCH_ITEM] : ADMIN_BASE;

  const renderNav = (items: typeof PRIMARY) =>
    items.map(({ id, label, tip, icon: Icon }) => (
      <button
        key={id}
        type="button"
        onClick={() => onViewChange(id)}
        className={`nav-item ${currentView === id ? 'active' : ''}`}
        style={{
          background: 'none',
          border: 'none',
          width: '100%',
          cursor: 'pointer',
          textAlign: 'left',
        }}
      >
        <span className="nav-item-label">
          <Icon size={14} />
          <span className="nav-item-text">
            {label}
            <InfoTip id={tip} />
          </span>
        </span>
      </button>
    ));

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        TRADEGRAPH
        <InfoTip id="corridor_scope" />
      </div>
      <nav className="sidebar-nav">
        {renderNav(PRIMARY)}
        <div className="nav-section-label">{OPERATOR.nav.adminSection}</div>
        {renderNav(adminItems)}
      </nav>
      <div className="sidebar-footer">
        <small>
          BD→IN · knitwear <InfoTip id="corridor_scope" />
        </small>
      </div>
    </aside>
  );
};
