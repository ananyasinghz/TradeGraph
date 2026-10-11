import { useEffect, useState } from 'react';
import { WelcomePanel } from './components/WelcomePanel';
import { Sidebar, type TradeView } from './components/Sidebar';
import { AdminView } from './views/AdminView';
import { AgreementsView } from './views/AgreementsView';
import { AskView } from './views/AskView';
import { CalculatorView } from './views/CalculatorView';
import { DashboardView } from './views/DashboardView';
import { DocumentsView } from './views/DocumentsView';
import { GlossaryView } from './views/GlossaryView';
import { LegalView } from './views/LegalView';
import { PublicShareView } from './views/PublicShareView';
import { ResearchLabView } from './views/ResearchLabView';
import { SettingsView } from './views/SettingsView';
import { ShipmentsView } from './views/ShipmentsView';
import { TariffsView } from './views/TariffsView';
import { WatchlistView } from './views/WatchlistView';
import { api, type NotificationItem, type SearchHit } from './services/api';
import { OPERATOR } from './content/operatorCopy';
import { useOperatorPrefs } from './content/useOperatorPrefs';
import { useAuth } from './auth/AuthProvider';
import { LoginPage } from './auth/LoginPage';
import {
  clearCaseHash,
  isCasesListHash,
  navigateToCase,
  navigateToCasesList,
  parseCaseIdFromHash,
} from './caseRoute';

const TITLES: Record<TradeView, string> = {
  dashboard: 'Home',
  shipments: 'Clearance cases',
  tariffs: 'Duty rates',
  calculator: 'Landed cost',
  agreements: 'Preferential / FTA',
  watchlist: 'Rate alerts',
  documents: 'Shipping papers',
  ask: 'Ask a question',
  glossary: 'Glossary',
  admin: 'Rate library (admin)',
  research: 'Research',
  settings: 'Settings',
  legal: 'Legal',
};

function readShareToken(): string | null {
  try {
    const params = new URLSearchParams(window.location.search);
    const token = params.get('share');
    return token && token.trim() ? token.trim() : null;
  } catch {
    return null;
  }
}

function AppShell() {
  const [currentView, setCurrentView] = useState<TradeView>(() =>
    parseCaseIdFromHash() || isCasesListHash() ? 'shipments' : 'dashboard',
  );
  const [legalPage, setLegalPage] = useState<'terms' | 'privacy' | 'disclaimer' | 'cookies'>(
    'disclaimer',
  );
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const [focusNewShipment, setFocusNewShipment] = useState(false);
  const [focusCaseId, setFocusCaseId] = useState<string | null>(() => parseCaseIdFromHash());
  const [caseTitle, setCaseTitle] = useState<string | null>(null);
  const [orgLabel, setOrgLabel] = useState<string | null>(null);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [notifOpen, setNotifOpen] = useState(false);
  const [searchQ, setSearchQ] = useState('');
  const [searchHits, setSearchHits] = useState<SearchHit[]>([]);
  const [searchOpen, setSearchOpen] = useState(false);
  const { showResearchLab } = useOperatorPrefs();
  const { whoami, logout, firebaseUser, authRequired, refreshWhoAmI } = useAuth();

  const role = whoami?.role || 'viewer';
  const showAdmin = role === 'admin' || role === 'reviewer';
  const showResearch = role === 'admin' && showResearchLab;
  const unreadCount = notifications.filter((n) => !n.is_read).length;

  useEffect(() => {
    api
      .getHealth()
      .then(() => setApiOnline(true))
      .catch(() => setApiOnline(false));
  }, []);

  useEffect(() => {
    const syncHash = () => {
      const caseId = parseCaseIdFromHash();
      if (caseId) {
        setFocusCaseId(caseId);
        setFocusNewShipment(false);
        setCurrentView('shipments');
        return;
      }
      setFocusCaseId(null);
      setCaseTitle(null);
      if (isCasesListHash()) {
        setCurrentView('shipments');
      }
    };
    syncHash();
    window.addEventListener('hashchange', syncHash);
    return () => window.removeEventListener('hashchange', syncHash);
  }, []);

  useEffect(() => {
    if (!whoami?.organization_id) {
      setOrgLabel(null);
      return;
    }
    void api
      .listOrganizations()
      .then((orgs) => {
        const match = orgs.find((o) => o.id === whoami.organization_id);
        setOrgLabel(match?.name || whoami.organization_id);
      })
      .catch(() => setOrgLabel(whoami.organization_id));
  }, [whoami?.organization_id]);

  useEffect(() => {
    void api
      .listNotifications(false)
      .then(setNotifications)
      .catch(() => setNotifications([]));
  }, [currentView]);

  useEffect(() => {
    if (!showResearch && currentView === 'research') {
      setCurrentView('dashboard');
    }
    if (!showAdmin && currentView === 'admin') {
      setCurrentView('dashboard');
    }
  }, [showResearch, showAdmin, currentView]);

  const goCasesList = () => {
    setFocusCaseId(null);
    setCaseTitle(null);
    setFocusNewShipment(false);
    setCurrentView('shipments');
    navigateToCasesList();
  };

  const goCreateShipment = () => {
    setFocusCaseId(null);
    setCaseTitle(null);
    setFocusNewShipment(true);
    setCurrentView('shipments');
    navigateToCasesList();
  };

  const goOpenShipment = (id: string) => {
    setFocusNewShipment(false);
    setFocusCaseId(id);
    setCurrentView('shipments');
    setSearchOpen(false);
    navigateToCase(id);
  };

  const changeView = (view: TradeView) => {
    if (view === 'shipments') {
      goCasesList();
      return;
    }
    if (focusCaseId || isCasesListHash()) {
      clearCaseHash();
    }
    setFocusCaseId(null);
    setCaseTitle(null);
    setFocusNewShipment(false);
    setCurrentView(view);
  };

  const runSearch = async (q: string) => {
    setSearchQ(q);
    if (q.trim().length < 2) {
      setSearchHits([]);
      setSearchOpen(false);
      return;
    }
    try {
      const res = await api.globalSearch(q.trim());
      setSearchHits(res.results);
      setSearchOpen(true);
    } catch {
      setSearchHits([]);
      setSearchOpen(true);
    }
  };

  const renderView = () => {
    switch (currentView) {
      case 'dashboard':
        return (
          <DashboardView
            onCreateShipment={goCreateShipment}
            onNavigate={changeView}
            onOpenShipment={goOpenShipment}
          />
        );
      case 'shipments':
        return (
          <ShipmentsView
            focusCreate={focusNewShipment}
            focusCaseId={focusCaseId}
            onFocused={() => setFocusNewShipment(false)}
            onOpenCase={goOpenShipment}
            onBackToList={goCasesList}
            onCaseTitle={setCaseTitle}
          />
        );
      case 'tariffs':
        return <TariffsView />;
      case 'calculator':
        return <CalculatorView />;
      case 'agreements':
        return <AgreementsView />;
      case 'watchlist':
        return <WatchlistView onOpenShipment={goOpenShipment} />;
      case 'documents':
        return <DocumentsView onOpenShipments={() => setCurrentView('shipments')} />;
      case 'ask':
        return <AskView onOpenShipment={goOpenShipment} />;
      case 'glossary':
        return <GlossaryView />;
      case 'settings':
        return <SettingsView onNavigate={changeView} />;
      case 'legal':
        return <LegalView page={legalPage} onPageChange={setLegalPage} />;
      case 'admin':
        return showAdmin ? <AdminView /> : null;
      case 'research':
        return showResearch ? <ResearchLabView /> : null;
      default:
        return null;
    }
  };

  const sessionLabel = whoami?.authenticated
    ? `${whoami.email || whoami.actor} · ${whoami.role}`
    : firebaseUser
      ? `${firebaseUser.email || 'Signed in'} · syncing…`
      : authRequired
        ? 'Not signed in'
        : 'Local demo (auth off)';

  const canLogout = Boolean(firebaseUser || whoami?.authenticated);

  return (
    <div className="app-container">
      <Sidebar
        currentView={currentView}
        onViewChange={changeView}
        showResearchLab={showResearch}
        showAdmin={showAdmin}
        sessionLabel={sessionLabel}
        orgLabel={orgLabel}
        notificationCount={unreadCount}
        onOpenNotifications={() => setNotifOpen((v) => !v)}
        onLogout={canLogout ? () => void logout() : undefined}
      />

      <main className="main-content">
        <header className="top-header">
          <h1 className="view-title">
            {focusCaseId && currentView === 'shipments'
              ? caseTitle || 'Case'
              : TITLES[currentView]}
          </h1>
          <div className="header-search" data-testid="global-search">
            <input
              type="search"
              placeholder={OPERATOR.searchPlaceholder}
              value={searchQ}
              onChange={(e) => void runSearch(e.target.value)}
              aria-label="Global search"
            />
            {searchOpen && (
              <div className="search-results" data-testid="search-results">
                {searchHits.length === 0 ? (
                  <p className="muted">No matches</p>
                ) : (
                  <ul>
                    {searchHits.map((h) => (
                      <li key={`${h.kind}-${h.id}`}>
                        <button
                          type="button"
                          className="linkish"
                          onClick={() => {
                            if (h.kind === 'shipment' || h.shipment_id) {
                              goOpenShipment(h.shipment_id || h.id);
                            } else {
                              changeView('tariffs');
                              setSearchOpen(false);
                            }
                          }}
                        >
                          {h.kind}: {h.title}
                        </button>
                        {h.snippet ? <div className="muted">{h.snippet}</div> : null}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
          <div
            className="system-status"
            title={
              apiOnline === null
                ? OPERATOR.connectionChecking
                : apiOnline
                  ? 'API online'
                  : OPERATOR.connectionOffline
            }
            aria-label={
              apiOnline === null
                ? OPERATOR.connectionChecking
                : apiOnline
                  ? 'API online'
                  : OPERATOR.connectionOffline
            }
          >
            <span
              className={`status-dot${apiOnline === false ? ' status-dot--offline' : ''}${apiOnline === null ? ' status-dot--checking' : ''}`}
            />
          </div>
        </header>

        {notifOpen ? (
          <div className="notifications-drawer" data-testid="notifications-drawer">
            <div className="section-title-row">
              <h3>Notifications</h3>
              <button type="button" className="linkish" onClick={() => setNotifOpen(false)}>
                Close
              </button>
            </div>
            {notifications.length === 0 ? (
              <p className="muted">No notifications.</p>
            ) : (
              <ul className="list">
                {notifications.map((n) => (
                  <li key={n.id} className={n.is_read ? 'muted' : ''}>
                    <strong>{n.title}</strong>
                    <div>{n.body}</div>
                    <div className="toolbar">
                      {n.shipment_id ? (
                        <button
                          type="button"
                          className="linkish"
                          onClick={() => {
                            goOpenShipment(n.shipment_id!);
                            setNotifOpen(false);
                          }}
                        >
                          Open case
                        </button>
                      ) : null}
                      {!n.is_read ? (
                        <button
                          type="button"
                          className="linkish"
                          onClick={() =>
                            void api
                              .markNotificationRead(n.id)
                              .then(() => api.listNotifications(false))
                              .then(setNotifications)
                              .catch(() => undefined)
                          }
                        >
                          Mark read
                        </button>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            )}
            <button
              type="button"
              className="linkish"
              onClick={() => {
                changeView('settings');
                setNotifOpen(false);
                void refreshWhoAmI();
              }}
            >
              Notification preferences…
            </button>
          </div>
        ) : null}

        {!focusCaseId ? (
          <WelcomePanel
            onCreateShipment={goCreateShipment}
            onOpenGlossary={() => changeView('glossary')}
          />
        ) : null}

        {renderView()}

        <p className="disclaimer">
          {OPERATOR.disclaimerShort}{' '}
          <button
            type="button"
            className="linkish"
            onClick={() => {
              setLegalPage('disclaimer');
              changeView('legal');
            }}
          >
            Legal
          </button>
        </p>
      </main>
    </div>
  );
}

function App() {
  const { loading, authRequired, whoami, firebaseUser } = useAuth();
  const shareToken = readShareToken();

  if (shareToken) {
    return <PublicShareView token={shareToken} />;
  }

  if (loading) {
    return (
      <div className="login-shell">
        <div className="login-stage" style={{ gridTemplateColumns: '1fr', maxWidth: 420 }}>
          <div className="login-card">
            <p className="login-brand">TradeGraph</p>
            <p className="muted">Loading session…</p>
          </div>
        </div>
      </div>
    );
  }

  if (authRequired && !whoami?.authenticated && !firebaseUser) {
    return <LoginPage />;
  }

  return <AppShell />;
}

export default App;
