import React from 'react';

export default function Navbar({ activePage, setActivePage }) {
  const navItems = [
    { id: 'summary', label: 'Network Summary', index: '01' },
    { id: 'grid', label: 'Grid Activity', index: '02' },
    { id: 'hotspots', label: 'Hotspots & Alerts', index: '03' },
    { id: 'risk', label: 'Predictive Risk', index: '04' }
  ];

  return (
    <nav className="navbar">
      <div className="navbar-brand">
        <div className="brand-mark" aria-hidden="true">N</div>
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
            type="button"
          >
            <span className="nav-index">{item.index}</span>
            <span>{item.label}</span>
          </button>
        ))}
      </div>
    </nav>
  );
}
