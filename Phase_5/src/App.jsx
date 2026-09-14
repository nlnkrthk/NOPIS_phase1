import React, { useState } from 'react';
import Navbar from './components/Navbar';
import NetworkSummary from './components/NetworkSummary';
import GridActivity from './components/GridActivity';
import HotspotsAlerts from './components/HotspotsAlerts';
import PredictiveRisk from './components/PredictiveRisk';
import { API_BASE_URL } from './api/config';

export default function App() {
  const [activePage, setActivePage] = useState('summary');
  const [targetGrid, setTargetGrid] = useState(null);

  const handleNavigateToGrid = (gridId) => {
    setTargetGrid(gridId);
    setActivePage('grid');
  };

  return (
    <div className="app-container">
      <Navbar activePage={activePage} setActivePage={setActivePage} />

      <main className="main-content">
        <header className="page-intro">
          <p className="eyebrow">01. System</p>
          <h1>Network Intelligence</h1>
          <p className="intro-copy">Operational visibility across Milan’s monitored cells, structured for decisive action.</p>
        </header>

        <div hidden={activePage !== 'summary'}>
          <NetworkSummary />
        </div>
        <div hidden={activePage !== 'grid'}>
          <GridActivity initialGridId={targetGrid} />
        </div>
        <div hidden={activePage !== 'hotspots'}>
          <HotspotsAlerts onNavigateToGrid={handleNavigateToGrid} />
        </div>
        <div hidden={activePage !== 'risk'}>
          <PredictiveRisk />
        </div>
      </main>

      <footer className="app-footer">
        <div className="footer-content">
          <span>NOPIS Phase 5 — Network Operations & Predictive Intelligence System</span>
          <span className="footer-api">Connected to API: <code>{API_BASE_URL}</code></span>
        </div>
      </footer>
    </div>
  );
}
