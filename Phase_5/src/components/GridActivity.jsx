import React, { useState, useEffect } from 'react';
import { getGridActivity } from '../api/config';

export default function GridActivity({ initialGridId }) {
  const [gridInput, setGridInput] = useState(initialGridId ? String(initialGridId) : '4821');
  const [filterMode, setFilterMode] = useState('date_hour'); // 'date_hour', 'range', or 'as_of'
  const [dateFilter, setDateFilter] = useState('');
  const [hourFilter, setHourFilter] = useState('');
  const [asOfTimestamp, setAsOfTimestamp] = useState('');
  const [rangeFromDate, setRangeFromDate] = useState('');
  const [rangeFromHour, setRangeFromHour] = useState('');
  const [rangeToDate, setRangeToDate] = useState('');
  const [rangeToHour, setRangeToHour] = useState('');
  const [activeGridId, setActiveGridId] = useState(initialGridId ? String(initialGridId) : '4821');
  const [activeDate, setActiveDate] = useState('');
  const [activeHour, setActiveHour] = useState('');
  const [activeAsOf, setActiveAsOf] = useState('');
  const [activeRange, setActiveRange] = useState({ from: '', to: '' });
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isNotFound, setIsNotFound] = useState(false);
  const [viewMode, setViewMode] = useState('chart'); // 'chart' or 'table'
  const [hoveredPoint, setHoveredPoint] = useState(null);

  const rangeOptions = () => ({
    from_dt: rangeFromDate && rangeFromHour ? `${rangeFromDate}T${rangeFromHour}:00:00` : '',
    to_dt: rangeToDate && rangeToHour ? `${rangeToDate}T${rangeToHour}:00:00` : '',
  });

  // 172. Call GET/network/grid/{grid_id} with the selected time filter.
  const fetchGridData = async (gridIdToFetch, mode = filterMode, selectedOptions = {}) => {
    if (!gridIdToFetch) return;
    setLoading(true);
    setError(null);
    setIsNotFound(false);
    setHoveredPoint(null);

    try {
      const options = { ...selectedOptions };
      if (mode === 'date_hour' && options.hour !== '') {
        options.hour = parseInt(options.hour, 10);
      }
      
      const result = await getGridActivity(gridIdToFetch, options);
      setData(result);
      setActiveGridId(gridIdToFetch);
      if (mode === 'date_hour') {
        setActiveDate(options.date || '');
        setActiveHour(options.hour === undefined ? '' : options.hour);
        setActiveAsOf('');
        setActiveRange({ from: '', to: '' });
      } else if (mode === 'range') {
        setActiveRange({ from: options.from_dt || '', to: options.to_dt || '' });
        setActiveDate('');
        setActiveHour('');
        setActiveAsOf('');
      } else {
        setActiveAsOf(options.as_of || '');
        setActiveDate('');
        setActiveHour('');
        setActiveRange({ from: '', to: '' });
      }
    } catch (err) {
      setData(null);
      // 175. Handle an unknown grid gracefully.
      if (err.status === 404) {
        setIsNotFound(true);
        setError(`Grid #${gridIdToFetch} was not found. Valid grid IDs are in the range 1–10,000.`);
      } else {
        setError(err.message || `Failed to fetch activity for Grid #${gridIdToFetch}`);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (filterMode === 'date_hour') {
      fetchGridData(activeGridId, 'date_hour', { date: dateFilter, hour: hourFilter });
    } else if (filterMode === 'range') {
      fetchGridData(activeGridId, 'range', rangeOptions());
    } else {
      fetchGridData(activeGridId, 'as_of', { as_of: asOfTimestamp });
    }
  }, []);

  const handleSearch = (e) => {
    e.preventDefault();
    const cleanId = gridInput.trim();
    if (cleanId) {
      if (filterMode === 'date_hour') {
        fetchGridData(cleanId, 'date_hour', { date: dateFilter, hour: hourFilter });
      } else if (filterMode === 'range') {
        fetchGridData(cleanId, 'range', rangeOptions());
      } else {
        fetchGridData(cleanId, 'as_of', { as_of: asOfTimestamp });
      }
    }
  };

  const selectQuickGrid = (id) => {
    setGridInput(String(id));
    if (filterMode === 'date_hour') {
      fetchGridData(String(id), 'date_hour', { date: dateFilter, hour: hourFilter });
    } else if (filterMode === 'range') {
      fetchGridData(String(id), 'range', rangeOptions());
    } else {
      fetchGridData(String(id), 'as_of', { as_of: asOfTimestamp });
    }
  };

  const handleClearFilters = () => {
    setDateFilter('');
    setHourFilter('');
    setAsOfTimestamp('');
    setRangeFromDate('');
    setRangeFromHour('');
    setRangeToDate('');
    setRangeToHour('');
    fetchGridData(gridInput, filterMode, filterMode === 'range' ? rangeOptions() : {});
  };

  const handleFilterModeChange = (mode) => {
    setFilterMode(mode);
    // Clear all filters when switching modes
    setDateFilter('');
    setHourFilter('');
    setAsOfTimestamp('');
    setRangeFromDate('');
    setRangeFromHour('');
    setRangeToDate('');
    setRangeToHour('');
    setData(null);
  };

  // Helper to format date & hour
  const formatDateTimeLabel = (point) => {
    if (!point) return '';
    const hourStr = `${String(point.hour).padStart(2, '0')}:00`;
    if (point.date) {
      const shortDate = String(point.date).slice(5); // MM-DD
      return `${shortDate} ${hourStr}`;
    }
    return hourStr;
  };

  // Calculate scaling for SVG chart
  const maxTotal = data && data.length > 0 ? Math.max(...data.map((d) => d.total_activity || 0), 1) : 1;
  const maxSms = data && data.length > 0 ? Math.max(...data.map((d) => d.total_sms || 0), 1) : 1;
  const maxCall = data && data.length > 0 ? Math.max(...data.map((d) => d.total_calls || 0), 1) : 1;
  const maxInternet = data && data.length > 0 ? Math.max(...data.map((d) => d.internet_activity || 0), 1) : 1;

  // Chart dimensions
  const svgWidth = 840;
  const svgHeight = 320;
  const paddingLeft = 60;
  const paddingRight = 30;
  const paddingTop = 30;
  const paddingBottom = 60;
  const chartWidth = svgWidth - paddingLeft - paddingRight;
  const chartHeight = svgHeight - paddingTop - paddingBottom;

  const getX = (index) => {
    if (!data || data.length <= 1) return paddingLeft + chartWidth / 2;
    return paddingLeft + (index / (data.length - 1)) * chartWidth;
  };

  const getY = (val) => {
    return paddingTop + chartHeight - (val / maxTotal) * chartHeight;
  };

  return (
    <div className="grid-explorer-container">
      <div className="section-header">
        <div>
          <h2>Grid Activity Explorer</h2>
          <p className="section-subtitle">Chronological hourly operational telemetry breakdown for telecom cells</p>
        </div>
      </div>

      {/* 171.Create a grid input or search control with optional filters. */}
      <div className="search-card">
        <form className="search-form" onSubmit={handleSearch}>
          <div className="search-row">
            <div className="form-group">
              <label htmlFor="grid-input" className="search-label">
                Grid Identifier (1 - 10,000):
              </label>
              <input
                id="grid-input"
                type="number"
                className="grid-search-input"
                value={gridInput}
                onChange={(e) => setGridInput(e.target.value)}
                placeholder="e.g. 4821"
                min="1"
                max="100000"
              />
            </div>

            <button type="submit" className="search-btn" disabled={loading}>
              {loading ? 'Searching...' : 'Explore Grid'}
            </button>
          </div>

          {/* Filter Mode Toggle */}
          <div className="filter-mode-toggle">
            <div className="toggle-label">Filter Mode:</div>
            <div className="toggle-buttons">
              <button
                type="button"
                className={`toggle-option ${filterMode === 'date_hour' ? 'active' : ''}`}
                onClick={() => handleFilterModeChange('date_hour')}
              >
                By Date & Hour
              </button>
              <button
                type="button"
                className={`toggle-option ${filterMode === 'range' ? 'active' : ''}`}
                onClick={() => handleFilterModeChange('range')}
              >
                By Range
              </button>
              <button
                type="button"
                className={`toggle-option ${filterMode === 'as_of' ? 'active' : ''}`}
                onClick={() => handleFilterModeChange('as_of')}
              >
                By As-Of
              </button>
            </div>
          </div>

          {/* Conditional Filter Inputs based on Mode */}
          {filterMode === 'date_hour' ? (
            <div className="search-row">
              <div className="form-group">
                <label htmlFor="date-filter" className="search-label">
                  Filter by Date (Optional):
                </label>
                <input
                  id="date-filter"
                  type="date"
                  className="grid-search-input"
                  value={dateFilter}
                  onChange={(e) => setDateFilter(e.target.value)}
                  placeholder="YYYY-MM-DD"
                />
              </div>

              <div className="form-group">
                <label htmlFor="hour-filter" className="search-label">
                  Filter by Hour (Optional):
                </label>
                <select
                  id="hour-filter"
                  className="grid-search-input"
                  value={hourFilter}
                  onChange={(e) => setHourFilter(e.target.value)}
                >
                  <option value="">All Hours</option>
                  {Array.from({ length: 24 }, (_, i) => (
                    <option key={i} value={String(i)}>
                      {String(i).padStart(2, '0')}:00 - {String(i).padStart(2, '0')}:59
                    </option>
                  ))}
                </select>
              </div>

              {(dateFilter || hourFilter) && (
                <button
                  type="button"
                  className="clear-filter-btn"
                  onClick={handleClearFilters}
                >
                  Clear Filters
                </button>
              )}
            </div>
          ) : filterMode === 'range' ? (
            <div className="search-row">
              <div className="form-group">
                <label htmlFor="range-from-date" className="search-label">From Date:</label>
                <input id="range-from-date" type="date" className="grid-search-input" value={rangeFromDate} onChange={(e) => setRangeFromDate(e.target.value)} />
              </div>
              <div className="form-group">
                <label htmlFor="range-from-hour" className="search-label">From Hour:</label>
                <select id="range-from-hour" className="grid-search-input" value={rangeFromHour} onChange={(e) => setRangeFromHour(e.target.value)}>
                  <option value="">Select hour</option>
                  {Array.from({ length: 24 }, (_, i) => <option key={i} value={String(i).padStart(2, '0')}>{String(i).padStart(2, '0')}:00</option>)}
                </select>
              </div>
              <div className="form-group">
                <label htmlFor="range-to-date" className="search-label">To Date:</label>
                <input id="range-to-date" type="date" className="grid-search-input" value={rangeToDate} onChange={(e) => setRangeToDate(e.target.value)} />
              </div>
              <div className="form-group">
                <label htmlFor="range-to-hour" className="search-label">To Hour:</label>
                <select id="range-to-hour" className="grid-search-input" value={rangeToHour} onChange={(e) => setRangeToHour(e.target.value)}>
                  <option value="">Select hour</option>
                  {Array.from({ length: 24 }, (_, i) => <option key={i} value={String(i).padStart(2, '0')}>{String(i).padStart(2, '0')}:00</option>)}
                </select>
              </div>
              {(rangeFromDate || rangeFromHour || rangeToDate || rangeToHour) && <button type="button" className="clear-filter-btn" onClick={handleClearFilters}>Clear Filters</button>}
            </div>
          ) : (
            <div className="search-row">
              <div className="form-group">
                <label htmlFor="as-of-filter" className="search-label">
                  As-Of Date:
                </label>
                <input
                  id="as-of-filter"
                  type="date"
                  className="grid-search-input"
                  value={asOfTimestamp.split('T')[0] || ''}
                  onChange={(e) => setAsOfTimestamp(`${e.target.value}T${asOfTimestamp.split('T')[1] || ''}`)}
                />
              </div>
              <div className="form-group">
                <label htmlFor="as-of-hour" className="search-label">As-Of Hour:</label>
                <select id="as-of-hour" className="grid-search-input" value={asOfTimestamp.split('T')[1]?.slice(0, 2) || ''} onChange={(e) => setAsOfTimestamp(`${asOfTimestamp.split('T')[0] || ''}T${e.target.value}:00:00`)}>
                  <option value="">Select hour</option>
                  {Array.from({ length: 24 }, (_, i) => <option key={i} value={String(i).padStart(2, '0')}>{String(i).padStart(2, '0')}:00</option>)}
                </select>
              </div>

              {asOfTimestamp && (
                <button
                  type="button"
                  className="clear-filter-btn"
                  onClick={handleClearFilters}
                >
                  Clear Filter
                </button>
              )}
            </div>
          )}
        </form>

      </div>

      {/* 175. Handle an unknown grid gracefully. */}
      {error && (
        <div className={`grid-status-alert ${isNotFound ? 'alert-not-found' : 'alert-error'}`}>
          <span className="alert-icon">{isNotFound ? '🔍' : '⚠️'}</span>
          <div className="alert-body">
            <strong>{isNotFound ? 'Grid Not Found' : 'API Connection Issue'}</strong>
            <p>{error}</p>
          </div>
          {!isNotFound && (
            <button className="retry-btn" onClick={() => {
              if (filterMode === 'range') fetchGridData(activeGridId, 'range', rangeOptions());
              else if (filterMode === 'as_of') fetchGridData(activeGridId, 'as_of', { as_of: asOfTimestamp });
              else fetchGridData(activeGridId, 'date_hour', { date: dateFilter, hour: hourFilter });
            }}>
              Retry
            </button>
          )}
        </div>
      )}

      {loading && (
        <div className="simple-loading">
          <div className="simple-spinner"></div>
          <p>Fetching telemetry activity for Grid #{gridInput}...</p>
        </div>
      )}

      {data && data.length > 0 && !loading && (
        <div className="grid-results-card">
          <div className="results-header">
            <div>
              <h3>Grid #{activeGridId} Telemetry Activity</h3>
              <div className="timeline-info-badge">
                <span>📊 {data.length} Reported Hourly Intervals</span>
                {data.length > 0 && (
                  <span className="timeline-span">
                    Timeline Range: <strong>{data[0]?.date} {String(data[0]?.hour).padStart(2, '0')}:00</strong> → <strong>{data[data.length - 1]?.date} {String(data[data.length - 1]?.hour).padStart(2, '0')}:00</strong>
                  </span>
                )}
                {activeDate && <span>📅 Date: <strong>{activeDate}</strong></span>}
                {activeHour !== '' && <span>⏰ Hour: <strong>{String(activeHour).padStart(2, '0')}:00</strong></span>}
                {activeRange.from && activeRange.to && <span>↔ Range: <strong>{activeRange.from}</strong> to <strong>{activeRange.to}</strong></span>}
                {activeAsOf && <span>⌛ Data As Of (from start): <strong>{activeAsOf}</strong></span>}
              </div>
            </div>

            <div className="view-toggle-group">
              <button
                className={`toggle-btn ${viewMode === 'chart' ? 'active' : ''}`}
                onClick={() => setViewMode('chart')}
              >
                📈 Time-Series Chart
              </button>
              <button
                className={`toggle-btn ${viewMode === 'table' ? 'active' : ''}`}
                onClick={() => setViewMode('table')}
              >
                📋 Data Table
              </button>
            </div>
          </div>

          {/* 174. Display call, SMS, internet and total activity as separate series. */}
          <div className="series-legend-bar">
            <div className="legend-item legend-total">
              <span className="legend-dot dot-total"></span>
              <span className="legend-label">Total Activity</span>
              <span className="legend-max">Max: {maxTotal.toFixed(1)}</span>
            </div>
            <div className="legend-item legend-internet">
              <span className="legend-dot dot-internet"></span>
              <span className="legend-label">Internet Activity</span>
              <span className="legend-max">Max: {maxInternet.toFixed(1)}</span>
            </div>
            <div className="legend-item legend-call">
              <span className="legend-dot dot-call"></span>
              <span className="legend-label">Call Activity</span>
              <span className="legend-max">Max: {maxCall.toFixed(1)}</span>
            </div>
            <div className="legend-item legend-sms">
              <span className="legend-dot dot-sms"></span>
              <span className="legend-label">SMS Activity</span>
              <span className="legend-max">Max: {maxSms.toFixed(1)}</span>
            </div>
          </div>

          {/* 173. Render an activity table or a simple time-series chart. */}
          {viewMode === 'chart' ? (
            <div className="chart-wrapper">
              <div className="chart-svg-container">
                <svg className="activity-chart-svg" viewBox={`0 0 ${svgWidth} ${svgHeight}`}>
                  {/* Y-Axis Grid Lines and Scale Labels */}
                  {[0, 0.25, 0.5, 0.75, 1].map((ratio, i) => {
                    const y = paddingTop + ratio * chartHeight;
                    const val = ((1 - ratio) * maxTotal).toFixed(0);
                    return (
                      <g key={i}>
                        <line
                          x1={paddingLeft}
                          y1={y}
                          x2={svgWidth - paddingRight}
                          y2={y}
                          stroke="rgba(255,255,255,0.08)"
                          strokeDasharray="4 4"
                        />
                        <text
                          x={paddingLeft - 10}
                          y={y + 4}
                          textAnchor="end"
                          fill="#64748b"
                          fontSize="10"
                        >
                          {val}
                        </text>
                      </g>
                    );
                  })}

                  {/* Series 1: Total Activity (Green Solid Line) */}
                  <polyline
                    fill="none"
                    stroke="#10b981"
                    strokeWidth="3"
                    points={data.map((d, i) => `${getX(i)},${getY(d.total_activity || 0)}`).join(' ')}
                  />

                  {/* Series 2: Internet Activity (Purple Dashed Line) */}
                  <polyline
                    fill="none"
                    stroke="#a855f7"
                    strokeWidth="2.5"
                    strokeDasharray="4 3"
                    points={data.map((d, i) => `${getX(i)},${getY(d.internet_activity || 0)}`).join(' ')}
                  />

                  {/* Series 3: Call Activity (Cyan Solid Line) */}
                  <polyline
                    fill="none"
                    stroke="#06b6d4"
                    strokeWidth="2"
                    points={data.map((d, i) => `${getX(i)},${getY(d.total_calls || 0)}`).join(' ')}
                  />

                  {/* Series 4: SMS Activity (Amber Solid Line) */}
                  <polyline
                    fill="none"
                    stroke="#f59e0b"
                    strokeWidth="2"
                    points={data.map((d, i) => `${getX(i)},${getY(d.total_sms || 0)}`).join(' ')}
                  />

                  {/* Data Points, Vertical Guidelines and X-axis Labels */}
                  {data.map((d, i) => {
                    const x = getX(i);
                    const y = getY(d.total_activity || 0);
                    const isEveryOther = data.length > 16 ? i % 2 === 0 || i === data.length - 1 : true;
                    return (
                      <g
                        key={i}
                        className="chart-node"
                        onMouseEnter={() => setHoveredPoint(d)}
                      >
                        {/* Hover trigger zone */}
                        <rect
                          x={x - 12}
                          y={paddingTop}
                          width={24}
                          height={chartHeight}
                          fill="transparent"
                        />
                        {/* Data Node Circle */}
                        <circle cx={x} cy={y} r="4" fill="#10b981" />
                        
                        {/* Clean Non-Overlapping X-Axis Ticks */}
                        {isEveryOther && (
                          <g transform={`translate(${x}, ${svgHeight - paddingBottom + 16})`}>
                            <text
                              textAnchor="end"
                              transform="rotate(-35)"
                              fill="#94a3b8"
                              fontSize="10"
                              fontWeight="500"
                            >
                              {formatDateTimeLabel(d)}
                            </text>
                          </g>
                        )}
                      </g>
                    );
                  })}
                </svg>
              </div>

              {hoveredPoint ? (
                <div className="point-tooltip">
                  <div className="tooltip-header">
                    <strong>📅 {hoveredPoint.date} — {String(hoveredPoint.hour).padStart(2, '0')}:00 hrs</strong>
                  </div>
                  <div className="tooltip-metrics">
                    <span style={{ color: '#10b981' }}>📈 Total Activity: <strong>{hoveredPoint.total_activity?.toFixed(2)}</strong></span>
                    <span style={{ color: '#a855f7' }}>🌐 Internet Activity: <strong>{hoveredPoint.internet_activity?.toFixed(2)}</strong></span>
                    <span style={{ color: '#06b6d4' }}>📞 Call Activity: <strong>{hoveredPoint.total_calls?.toFixed(2)}</strong></span>
                    <span style={{ color: '#f59e0b' }}>💬 SMS Activity: <strong>{hoveredPoint.total_sms?.toFixed(2)}</strong></span>
                    <span style={{ color: '#38bdf8' }}>📊 Internet Share: <strong>{((hoveredPoint.internet_share || 0) * 100).toFixed(1)}%</strong></span>
                  </div>
                </div>
              ) : (
                <p className="tooltip-hint">💡 Hover over any point on the chart to inspect the detailed telemetry breakdown.</p>
              )}
            </div>
          ) : (
            <div className="table-responsive">
              <table className="telemetry-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Hour</th>
                    <th>Total Activity</th>
                    <th>Internet Activity</th>
                    <th>Call Activity</th>
                    <th>SMS Activity</th>
                    <th>Internet Share</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((row, idx) => (
                    <tr key={idx}>
                      <td>{row.date}</td>
                      <td><strong>{String(row.hour).padStart(2, '0')}:00</strong></td>
                      <td className="cell-total">{row.total_activity?.toFixed(2)}</td>
                      <td className="cell-internet">{row.internet_activity?.toFixed(2)}</td>
                      <td className="cell-call">{row.total_calls?.toFixed(2)}</td>
                      <td className="cell-sms">{row.total_sms?.toFixed(2)}</td>
                      <td>{((row.internet_share || 0) * 100)?.toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
