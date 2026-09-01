import React from 'react';

// Reusable metric card component for displaying individual KPI measures
export default function MetricCard({ icon, label, value, description }) {
  return (
    <div className="metric-card">
      <div className="metric-icon">{icon}</div>
      <div className="metric-info">
        <span className="metric-label">{label}</span>
        <span className="metric-value">{value}</span>
        {description && <span className="metric-description">{description}</span>}
      </div>
    </div>
  );
}
