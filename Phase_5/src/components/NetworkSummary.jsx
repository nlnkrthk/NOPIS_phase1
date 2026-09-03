import React, { useState, useEffect } from 'react';
import { getNetworkSummary } from '../api/config';
import MetricCard from './MetricCard';

const HOURS = Array.from({ length: 24 }, (_, hour) => String(hour).padStart(2, '0'));

export default function NetworkSummary() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [summaryMode, setSummaryMode] = useState('overall');
  const [fromDate, setFromDate] = useState('');
  const [fromHour, setFromHour] = useState('');
  const [toDate, setToDate] = useState('');
  const [toHour, setToHour] = useState('');
  const [asOfDate, setAsOfDate] = useState('');
  const [asOfHour, setAsOfHour] = useState('');

  // 166. Call /network/summary with optional inclusive datetime range.
  const loadSummary = async (fromDt = '', toDt = '', asOf = '') => {
    setLoading(true);
    setError(null);
    try {
      const summaryData = await getNetworkSummary(fromDt, toDt, asOf);
      setData(summaryData);
    } catch (err) {
      setError(err.message || 'API endpoint unavailable or failed to respond');
    } finally {
      setLoading(false);
    }
  };

  const handleApplySummary = () => {
    if (summaryMode === 'overall') {
      loadSummary();
      return;
    }

    if (summaryMode === 'as_of') {
      if (!asOfDate || !asOfHour) {
        setError('Select both a date and hour for the as_of timestamp.');
        return;
      }
      loadSummary('', '', `${asOfDate}T${asOfHour}:00:00`);
      return;
    }

    const hasFrom = fromDate || fromHour;
    const hasTo = toDate || toHour;

    if ((hasFrom && (!fromDate || !fromHour)) || (hasTo && (!toDate || !toHour))) {
      setError('Select both a date and hour for each range boundary.');
      return;
    }

    const fromDt = fromDate && fromHour ? `${fromDate}T${fromHour}:00:00` : '';
    const toDt = toDate && toHour ? `${toDate}T${toHour}:00:00` : '';

    if (fromDt && toDt && fromDt > toDt) {
      setError('The start datetime must be before or equal to the end datetime.');
      return;
    }

    loadSummary(fromDt, toDt);
  };

  const handleModeChange = (mode) => {
    setSummaryMode(mode);
    setError(null);
    if (mode === 'overall') {
      loadSummary();
    }
  };

  const handleClearRange = () => {
    setFromDate('');
    setFromHour('');
    setToDate('');
    setToHour('');
    setAsOfDate('');
    setAsOfHour('');
    setSummaryMode('overall');
    loadSummary();
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
          <button className="banner-retry-btn" onClick={() => loadSummary()}>
            Retry
          </button>
        </div>
      )}

      <div className="overview-header">
        <div>
          <h2>Network Overview</h2>
          <p className="header-subtitle">High-level operational metrics across all monitored cells</p>
        </div>

        <div className="summary-mode-toggle" role="group" aria-label="Summary mode">
          {[
            ['overall', 'Overall'],
            ['range', 'Range'],
            ['as_of', 'As Of'],
          ].map(([mode, label]) => (
            <button
              key={mode}
              type="button"
              className={`summary-mode-button ${summaryMode === mode ? 'active' : ''}`}
              onClick={() => handleModeChange(mode)}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="datetime-selector">
          {summaryMode === 'range' && <>
            <label className="datetime-field">
              <span>From date</span>
              <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} className="datetime-input" />
            </label>
            <label className="datetime-field">
              <span>From hour</span>
              <select value={fromHour} onChange={(e) => setFromHour(e.target.value)} className="datetime-input">
                <option value="">Hour</option>
                {HOURS.map((hour) => <option key={hour} value={hour}>{hour}:00</option>)}
              </select>
            </label>
            <label className="datetime-field">
              <span>To date</span>
              <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} className="datetime-input" />
            </label>
            <label className="datetime-field">
              <span>To hour</span>
              <select value={toHour} onChange={(e) => setToHour(e.target.value)} className="datetime-input">
                <option value="">Hour</option>
                {HOURS.map((hour) => <option key={hour} value={hour}>{hour}:00</option>)}
              </select>
            </label>
          </>}
          {summaryMode === 'as_of' && <>
            <label className="datetime-field">
              <span>As of date</span>
              <input type="date" value={asOfDate} onChange={(e) => setAsOfDate(e.target.value)} className="datetime-input" />
            </label>
            <label className="datetime-field">
              <span>As of hour</span>
              <select value={asOfHour} onChange={(e) => setAsOfHour(e.target.value)} className="datetime-input">
                <option value="">Hour</option>
                {HOURS.map((hour) => <option key={hour} value={hour}>{hour}:00</option>)}
              </select>
            </label>
          </>}
          <button
            onClick={handleApplySummary}
            className="apply-datetime-btn"
            disabled={loading}
          >
            {loading ? 'Loading...' : 'Apply'}
          </button>
          {summaryMode !== 'overall' && data && (
            <button
              onClick={handleClearRange}
              className="clear-datetime-btn"
            >
              Clear
            </button>
          )}
        </div>

        {/* 168. Show the effective range returned by the API. */}
        {data && data.from_dt && data.to_dt && (
          <div className="reporting-timestamp-tag">
            <span className="timestamp-icon">🕒</span>
            <span>Range: <strong>{data.from_dt}</strong> to <strong>{data.to_dt}</strong></span>
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
            <button className="refresh-link-btn" onClick={() => loadSummary()}>
              Refresh Data
            </button>
          </div>
        </>
      )}
    </div>
  );
}
