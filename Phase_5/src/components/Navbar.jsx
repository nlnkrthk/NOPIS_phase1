import React from 'react';

// 165. Create simple navigation between the dashboard pages.
export default function Navbar({ activePage, setActivePage }) {
  const navItems = [
    { id: 'summary', label: 'Network Summary', icon: '📊' },
    { id: 'grid', label: 'Grid Activity', icon: '🗺️' },
    { id: 'hotspots', label: 'Hotspots & Alerts', icon: '🚨' },
    { id: 'risk', label: 'Predictive Risk', icon: '⚠️' }
  ];

  return (
    <nav className="navbar">
      <div className="navbar-brand">
        <div className="brand-logo">📡</div>
        <div className="brand-text">
          <span className="brand-title">NOPIS</span>
          <span className="brand-subtitle">Network Operations Center</span>
        </div>
      </div>
      <div className="nav-links">
        {navItems.map((item) => (
          <button
            key={item.id}
            className={`nav-button ${activePage === item.id ? 'active' : ''}`}
            onClick={() => setActivePage(item.id)}
          >
            <span className="nav-icon">{item.icon}</span>
            <span>{item.label}</span>
          </button>
        ))}
      </div>
    </nav>
  );
}
