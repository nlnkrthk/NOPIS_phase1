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
        {activePage === 'summary' && <NetworkSummary />}
        {activePage === 'grid' && <GridActivity initialGridId={targetGrid} />}
        {activePage === 'hotspots' && <HotspotsAlerts onNavigateToGrid={handleNavigateToGrid} />}
        {activePage === 'risk' && <PredictiveRisk />}
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
