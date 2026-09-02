import React, { useState, useEffect } from 'react';
import { getNetworkSummary } from '../api/config';
import MetricCard from './MetricCard';

export default function NetworkSummary() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedDateTime, setSelectedDateTime] = useState('');

  // 166. Call /network/summary with optional as_of parameter.
  const loadSummary = async (asOf = '') => {
    setLoading(true);
    setError(null);
    try {
      const summaryData = await getNetworkSummary(asOf);
      setData(summaryData);
    } catch (err) {
      setError(err.message || 'API endpoint unavailable or failed to respond');
    } finally {
      setLoading(false);
    }
  };

  const handleDateTimeChange = (e) => {
    const value = e.target.value;
    setSelectedDateTime(value);
  };

  const handleApplyDateTime = () => {
    if (selectedDateTime) {
      // Convert from datetime-local format (YYYY-MM-DDTHH:mm) to ISO format (YYYY-MM-DDTHH:mm:00)
      const isoDateTime = selectedDateTime + ':00';
      loadSummary(isoDateTime);
    } else {
      // Load default (latest)
      loadSummary();
    }
  };

  useEffect(() => {
    loadSummary();
  }, []);

  // 170. Keep the styling intentionally simple.
  return (
    <div className="overview-container">
      {/* 169. Show a small status banner when the API is unavailable. */}
      {error && (
        <div className="api-status-banner api-status-error" role="alert">
          <div className="banner-content">
            <span className="banner-icon">⚠️</span>
            <div>
              <strong>API Unavailable:</strong> {error}
            </div>
          </div>
          <button className="banner-retry-btn" onClick={loadSummary}>
            Retry
          </button>
        </div>
      )}

      <div className="overview-header">
        <div>
          <h2>Network Overview</h2>
          <p className="header-subtitle">High-level operational metrics across all monitored cells</p>
        </div>

        {/* DateTime selector for as_of filtering */}
        <div className="datetime-selector">
          <input
            type="datetime-local"
            value={selectedDateTime}
            onChange={handleDateTimeChange}
            placeholder="Select date and time"
            className="datetime-input"
          />
          <button
            onClick={handleApplyDateTime}
            className="apply-datetime-btn"
            disabled={loading}
          >
            {loading ? 'Loading...' : 'Apply'}
          </button>
          {selectedDateTime === '' && data && (
            <button
              onClick={() => { setSelectedDateTime(''); loadSummary(); }}
              className="clear-datetime-btn"
            >
              Latest
            </button>
          )}
        </div>

        {/* 168. Show the as_of value returned by the API as the reporting timestamp — do not display the browser clock, which would be misleading on a historical dataset. */}
        {data && data.as_of && (
          <div className="reporting-timestamp-tag">
            <span className="timestamp-icon">🕒</span>
            <span>Data As Of: <strong>{data.as_of}</strong></span>
          </div>
        )}
      </div>

      {loading && !data && (
        <div className="simple-loading">
          <div className="simple-spinner"></div>
          <p>Loading network summary...</p>
        </div>
      )}

      {/* 167. Display four metric cards. */}
      {data && (
        <>
          <div className="metrics-grid">
            <MetricCard
              icon="📊"
              label="Total Activity Index"
              value={Number(data.total_activity).toLocaleString(undefined, { maximumFractionDigits: 2 })}
              description="Aggregate telemetry activity indicator"
            />
            <MetricCard
              icon="🌐"
              label="Active Grids"
              value={data.active_grids.toLocaleString()}
              description="Total active cells reporting metrics"
            />
            <MetricCard
              icon="⏰"
              label="Peak Hour"
              value={`${String(data.peak_hour).padStart(2, '0')}:00`}
              description="Highest overall activity window"
            />
            <MetricCard
              icon="📍"
              label="Top Grid"
              value={`Grid #${data.top_grid}`}
              description="Cell with maximum activity"
            />
          </div>

          <div className="overview-footer-bar">
            <span className="api-healthy-tag">● API Connected</span>
            <button className="refresh-link-btn" onClick={loadSummary}>
              Refresh Data
            </button>
          </div>
        </>
      )}
    </div>
  );
}
