import React, { useState, useEffect } from 'react';
import { getNetworkHotspots, getNetworkAlerts } from '../api/config';
import MapLayer from './MapLayer';

const SEVERITY_ORDER = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'];

export default function HotspotsAlerts({ onNavigateToGrid }) {
  const [geoData, setGeoData] = useState(null);
  const [hotspots, setHotspots] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [availableSeverities, setAvailableSeverities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [severityFilter, setSeverityFilter] = useState('');
  const [limit, setLimit] = useState(20);

  // 177. Load a read-only static copy of milano-grid.geojson from the frontend public/reference/ area or an equivalent static route. Fetch it once and hold it in state — it must not be re-fetched on every interaction.
  useEffect(() => {
    let mounted = true;
    const fetchGeoJSON = async () => {
      try {
        const res = await fetch('/milano-grid.geojson');
        if (!res.ok) throw new Error('Failed to load GeoJSON');
        const data = await res.json();
        if (mounted) setGeoData(data);
      } catch (err) {
        console.error('Error loading static geojson:', err);
      }
    };
    fetchGeoJSON();
    return () => { mounted = false; };
  }, []); // Empty dependency array ensures this is fetched ONCE

  // 176. Call /network/hotspots and /network/alerts.
  const fetchApiData = async () => {
    setLoading(true);
    setError(null);
    try {
      // 179. Add limit and severity filtering.
      const [hotspotsData, alertsData] = await Promise.all([
        getNetworkHotspots(500, ''),
        getNetworkAlerts(500, '', '')
      ]);

      const severities = [...new Set([
        ...hotspotsData.map(item => item.severity),
        ...alertsData.map(item => item.severity)
      ])].sort((a, b) => {
        return (SEVERITY_ORDER.indexOf(a) === -1 ? SEVERITY_ORDER.length : SEVERITY_ORDER.indexOf(a)) -
          (SEVERITY_ORDER.indexOf(b) === -1 ? SEVERITY_ORDER.length : SEVERITY_ORDER.indexOf(b));
      });
      setAvailableSeverities(severities);

      const filteredHotspots = severityFilter
        ? hotspotsData.filter(item => item.severity === severityFilter)
        : hotspotsData;
      const filteredAlerts = severityFilter
        ? alertsData.filter(item => item.severity === severityFilter)
        : alertsData;

      setHotspots(filteredHotspots);
      setAlerts(filteredAlerts);
    } catch (err) {
      setError(err.message || 'Failed to fetch operational data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchApiData();
  }, [limit, severityFilter]);

  // Merge hotspots and alerts for the ranked table
  const combinedItems = [];
  const addedGrids = new Set();
  
  // Prioritize alerts
  alerts.forEach(a => {
    combinedItems.push({
      grid_id: a.grid_id,
      timestamp: a.timestamp,
      type: 'Alert',
      status: a.alert_type,
      severity: a.severity,
      activity: a.total_activity
    });
    addedGrids.add(a.grid_id);
  });

  // Add hotspots that aren't already in the list
  hotspots.forEach(h => {
    if (!addedGrids.has(h.grid_id)) {
      combinedItems.push({
        grid_id: h.grid_id,
        timestamp: h.timestamp,
        type: 'Hotspot',
        status: h.reason,
        severity: h.severity,
        activity: h.total_activity
      });
      addedGrids.add(h.grid_id);
    }
  });

  // Sort by activity descending for the table
  combinedItems.sort((a, b) => b.activity - a.activity);
  const rankedItems = combinedItems.slice(0, limit);

  return (
    <div className="hotspots-page">
      <div className="section-header">
        <div>
          <h2>Hotspots & Alerts</h2>
          <p className="section-subtitle">Prioritized operational attention areas rendered geographically</p>
        </div>
      </div>

      <div className="filters-bar">
        <div className="form-group">
          <label className="search-label">Severity Filter</label>
          <select 
            className="grid-search-input" 
            value={severityFilter} 
            onChange={e => setSeverityFilter(e.target.value)}
          >
            <option value="">All Severities</option>
            {availableSeverities.map(severity => (
              <option key={severity} value={severity}>{severity}</option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <label className="search-label">Row Limit</label>
          <select 
            className="grid-search-input" 
            value={limit} 
            onChange={e => setLimit(Number(e.target.value))}
          >
            <option value="10">Top 10</option>
            <option value="20">Top 20</option>
            <option value="50">Top 50</option>
          </select>
        </div>
        <button className="refresh-button" onClick={fetchApiData}>
          🔄 Refresh
        </button>
      </div>

      {error && (
        <div className="api-status-banner api-status-error">
          <div className="banner-content">
            <span className="banner-icon">⚠️</span>
            <div><strong>Error:</strong> {error}</div>
          </div>
          <button className="banner-retry-btn" onClick={fetchApiData}>Retry</button>
        </div>
      )}

      <div className="dashboard-layout">
        <div className="map-panel">
          <div className="panel-header">
            <h3>Geographic View (Milan)</h3>
          </div>
          <div className="map-wrapper">
            {!geoData ? (
              <div className="simple-loading" style={{ height: '500px' }}>
                <div className="simple-spinner"></div>
                <p>Loading Geographic Reference Data...</p>
              </div>
            ) : (
              <MapLayer 
                geoData={geoData} 
                hotspots={hotspots} 
                alerts={alerts} 
                onGridSelect={(gridId) => onNavigateToGrid(gridId)} 
              />
            )}
          </div>
        </div>

        <div className="table-panel">
          <div className="panel-header">
            <h3>Ranked Operational Attention</h3>
            {loading && <span className="loading-badge">Updating...</span>}
          </div>
          
          <div className="table-responsive">
            {/* 178. Render ranked rows with grid, activity, alert or risk status, and hourly timestamp. */}
            <table className="telemetry-table">
              <thead>
                <tr>
                  <th>Grid</th>
                  <th>Type / Status</th>
                  <th>Severity</th>
                  <th>Activity Index</th>
                  <th>Hourly Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {rankedItems.length === 0 ? (
                  <tr>
                    <td colSpan="5" style={{ textAlign: 'center', padding: '2rem' }}>
                      No areas found matching current filters.
                    </td>
                  </tr>
                ) : (
                  rankedItems.map((item, idx) => (
                    <tr 
                      key={`${item.type}-${item.grid_id}-${idx}`} 
                      className={`row-severity-${item.severity.toLowerCase()}`}
                      onClick={() => onNavigateToGrid(item.grid_id)}
                      style={{ cursor: 'pointer' }}
                    >
                      <td><strong>#{item.grid_id}</strong></td>
                      <td>
                        <div style={{ display: 'flex', flexDirection: 'column' }}>
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{item.type}</span>
                          <span>{item.status}</span>
                        </div>
                      </td>
                      <td>
                        <span className={`severity-badge badge-${item.severity.toLowerCase()}`}>
                          {item.severity === 'HIGH' && '⚠️ '}
                          {item.severity}
                        </span>
                      </td>
                      <td style={{ fontWeight: '600' }}>{item.activity.toFixed(2)}</td>
                      <td style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                        {item.timestamp.replace('T', ' ')}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
