import { useState, type FC } from 'react';
import {
  Bell,
  BookOpen,
  Calculator,
  ChevronDown,
  FileText,
  FlaskConical,
  Handshake,
  LayoutDashboard,
  MessageSquare,
  Package,
  Scale,
  Settings,
  SlidersHorizontal,
  Table2,
} from 'lucide-react';
import { InfoTip } from './InfoTip';
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
  | 'research'
  | 'settings'
  | 'legal';

interface SidebarProps {
  currentView: TradeView;
  onViewChange: (view: TradeView) => void;
  showResearchLab?: boolean;
  showAdmin?: boolean;
  sessionLabel?: string;
  orgLabel?: string | null;
  notificationCount?: number;
  onOpenNotifications?: () => void;
  onLogout?: () => void;
}

type NavItem = { id: TradeView; label: string; icon: typeof LayoutDashboard };

const PRIMARY: NavItem[] = [
  { id: 'dashboard', label: OPERATOR.nav.home, icon: LayoutDashboard },
  { id: 'shipments', label: OPERATOR.nav.cases, icon: Package },
  { id: 'tariffs', label: OPERATOR.nav.duty, icon: Table2 },
  { id: 'calculator', label: OPERATOR.nav.landed, icon: Calculator },
  { id: 'agreements', label: OPERATOR.nav.fta, icon: Handshake },
  { id: 'documents', label: OPERATOR.nav.papers, icon: FileText },
  { id: 'watchlist', label: OPERATOR.nav.alerts, icon: Bell },
  { id: 'ask', label: OPERATOR.nav.ask, icon: MessageSquare },
];

const MORE: NavItem[] = [
  { id: 'glossary', label: OPERATOR.nav.glossary, icon: BookOpen },
  { id: 'settings', label: OPERATOR.navSettings, icon: SlidersHorizontal },
  { id: 'legal', label: OPERATOR.navLegal, icon: Scale },
];

const ADMIN_ITEM: NavItem = {
  id: 'admin',
  label: OPERATOR.nav.admin,
  icon: Settings,
};

const RESEARCH_ITEM: NavItem = {
  id: 'research',
  label: OPERATOR.nav.research,
  icon: FlaskConical,
};

export const Sidebar: FC<SidebarProps> = ({
  currentView,
  onViewChange,
  showResearchLab = false,
  showAdmin = false,
  sessionLabel,
  orgLabel,
  notificationCount = 0,
  onOpenNotifications,
  onLogout,
}) => {
  const moreActive = MORE.some((i) => i.id === currentView);
  const [moreOpen, setMoreOpen] = useState(moreActive);

  const adminItems = [
    ...(showAdmin ? [ADMIN_ITEM] : []),
    ...(showAdmin && showResearchLab ? [RESEARCH_ITEM] : []),
  ];

  const renderNav = (items: NavItem[]) =>
    items.map(({ id, label, icon: Icon }) => (
      <button
        key={id}
        type="button"
        data-testid={`nav-${id}`}
        onClick={() => onViewChange(id)}
        className={`nav-item nav-item-btn ${currentView === id ? 'active' : ''}`}
      >
        <span className="nav-item-label">
          <Icon size={15} />
          <span className="nav-item-text">{label}</span>
        </span>
      </button>
    ));

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true" />
          <span className="brand-word">TradeGraph</span>
        </div>
        <InfoTip id="corridor_scope" />
      </div>
      {orgLabel ? (
        <div className="sidebar-org" data-testid="org-label">
          {orgLabel}
        </div>
      ) : null}
      <nav className="sidebar-nav">
        {renderNav(PRIMARY)}
        <div className="nav-more">
          <button
            type="button"
            className={`nav-more-toggle${moreOpen || moreActive ? ' open' : ''}`}
            aria-expanded={moreOpen || moreActive}
            onClick={() => setMoreOpen((v) => !v)}
            data-testid="nav-more-toggle"
          >
            More
            <ChevronDown size={14} />
          </button>
          {(moreOpen || moreActive) && (
            <div className="nav-more-items" data-testid="nav-more-items">
              {renderNav(MORE)}
            </div>
          )}
        </div>
        {adminItems.length > 0 ? (
          <>
            <div className="nav-section-label">{OPERATOR.nav.adminSection}</div>
            {renderNav(adminItems)}
          </>
        ) : null}
      </nav>
      <div className="sidebar-footer">
        {onOpenNotifications ? (
          <button
            type="button"
            className="sidebar-notifications"
            data-testid="notifications-toggle"
            onClick={onOpenNotifications}
          >
            Notifications
            {notificationCount > 0 ? (
              <span className="notif-badge" data-testid="notif-badge">
                {notificationCount}
              </span>
            ) : null}
          </button>
        ) : null}
        {sessionLabel ? <small className="sidebar-session">{sessionLabel}</small> : null}
        {onLogout ? (
          <button type="button" className="sidebar-logout" onClick={onLogout}>
            Log out
          </button>
        ) : null}
        <small className="sidebar-corridor">BD→IN · knitwear</small>
      </div>
    </aside>
  );
};
