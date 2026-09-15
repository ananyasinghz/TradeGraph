import { useEffect, useState } from 'react';
import { WelcomePanel } from './components/WelcomePanel';
import { EnvironmentBanner } from './components/EnvironmentBanner';
import { InfoTip } from './components/InfoTip';
import { Sidebar, type TradeView } from './components/Sidebar';
import { AdminView } from './views/AdminView';
import { AgreementsView } from './views/AgreementsView';
import { AskView } from './views/AskView';
import { CalculatorView } from './views/CalculatorView';
import { DashboardView } from './views/DashboardView';
import { DocumentsView } from './views/DocumentsView';
import { GlossaryView } from './views/GlossaryView';
import { ResearchLabView } from './views/ResearchLabView';
import { ShipmentsView } from './views/ShipmentsView';
import { TariffsView } from './views/TariffsView';
import { WatchlistView } from './views/WatchlistView';
import { api } from './services/api';
import { OPERATOR } from './content/operatorCopy';
import { useOperatorPrefs } from './content/useOperatorPrefs';

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
};

function App() {
  const [currentView, setCurrentView] = useState<TradeView>('dashboard');
  const [apiLabel, setApiLabel] = useState(OPERATOR.connectionChecking);
  const [focusNewShipment, setFocusNewShipment] = useState(false);
  const [openShipmentId, setOpenShipmentId] = useState<string | null>(null);
  const { showTech, setTechnicalDetails, showResearchLab } = useOperatorPrefs();

  useEffect(() => {
    api
      .getHealth()
      .then((h) =>
        setApiLabel(
          OPERATOR.connectionOnline(h.prototype_corridor || 'Bangladesh → India (knitwear)'),
        ),
      )
      .catch(() => setApiLabel(OPERATOR.connectionOffline));
  }, []);

  useEffect(() => {
    if (!showResearchLab && currentView === 'research') {
      setCurrentView('dashboard');
    }
  }, [showResearchLab, currentView]);

  const goCreateShipment = () => {
    setOpenShipmentId(null);
    setFocusNewShipment(true);
    setCurrentView('shipments');
  };

  const goOpenShipment = (id: string) => {
    setFocusNewShipment(false);
    setOpenShipmentId(id);
    setCurrentView('shipments');
  };

  const renderView = () => {
    switch (currentView) {
      case 'dashboard':
        return (
          <DashboardView
            onCreateShipment={goCreateShipment}
            onNavigate={setCurrentView}
            onOpenShipment={goOpenShipment}
          />
        );
      case 'shipments':
        return (
          <ShipmentsView
            focusCreate={focusNewShipment}
            openShipmentId={openShipmentId}
            onFocused={() => setFocusNewShipment(false)}
            onOpened={() => setOpenShipmentId(null)}
          />
        );
      case 'tariffs':
        return <TariffsView />;
      case 'calculator':
        return <CalculatorView />;
      case 'agreements':
        return <AgreementsView />;
      case 'watchlist':
        return <WatchlistView />;
      case 'documents':
        return <DocumentsView onOpenShipments={() => setCurrentView('shipments')} />;
      case 'ask':
        return <AskView />;
      case 'glossary':
        return <GlossaryView />;
      case 'admin':
        return <AdminView />;
      case 'research':
        return showResearchLab ? <ResearchLabView /> : null;
      default:
        return null;
    }
  };

  return (
    <div className="app-container">
      <Sidebar
        currentView={currentView}
        onViewChange={setCurrentView}
        showResearchLab={showResearchLab}
      />

      <main className="main-content">
        <EnvironmentBanner />

        <header className="top-header">
          <h1 className="view-title">{TITLES[currentView]}</h1>
          <div className="system-status">
            <span className="status-dot"></span>
            <span className="label-with-tip">
              {apiLabel} <InfoTip id="api_status" />
            </span>
            <label className="tech-details-toggle muted">
              <input
                type="checkbox"
                checked={showTech}
                onChange={(e) => setTechnicalDetails(e.target.checked)}
              />{' '}
              {OPERATOR.footerTechToggle}
            </label>
          </div>
        </header>

        <WelcomePanel
          onCreateShipment={goCreateShipment}
          onOpenGlossary={() => setCurrentView('glossary')}
        />

        {renderView()}

        <p className="disclaimer">
          {OPERATOR.disclaimerShort}{' '}
          <button type="button" className="linkish" onClick={() => setCurrentView('glossary')}>
            Glossary
          </button>{' '}
          <InfoTip id="disclaimer" />
        </p>
      </main>
    </div>
  );
}

export default App;
