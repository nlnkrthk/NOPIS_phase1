import React, { useMemo } from 'react';
import { MapContainer, TileLayer, GeoJSON } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

export default function MapLayer({ geoData, hotspots, alerts, onGridSelect }) {
  // Center of Milan
  const center = [45.4642, 9.1900];

  // Create lookup maps for faster joining
  const hotspotMap = useMemo(() => {
    const map = new Map();
    hotspots.forEach(h => map.set(h.grid_id, h));
    return map;
  }, [hotspots]);

  const alertMap = useMemo(() => {
    const map = new Map();
    alerts.forEach(a => map.set(a.grid_id, a));
    return map;
  }, [alerts]);

  // Render all grid polygons (≈10k) using Canvas for performance.
  const allFeatures = geoData; // Use the full geoData without filtering

  // Determine severity for a grid
  const getGridStatus = (gridId) => {
    const alert = alertMap.get(gridId);
    const hotspot = hotspotMap.get(gridId);
    const severityOrder = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'];
    const severities = [alert?.severity, hotspot?.severity].filter(Boolean);
    const severity = severities.sort((a, b) => {
      const aIndex = severityOrder.indexOf(a);
      const bIndex = severityOrder.indexOf(b);
      return (aIndex === -1 ? severityOrder.length : aIndex) -
        (bIndex === -1 ? severityOrder.length : bIndex);
    })[0] || '';

    return {
      severity,
      source: alert ? 'Alert' : hotspot ? 'Hotspot' : ''
    };
  };

  // 181. Visually distinguish each API severity in both the ranked table and the map.
  const styleFeature = (feature) => {
    const gridId = feature.properties.cellId;
    const { severity, source } = getGridStatus(gridId);
    
    let color = source === 'Hotspot' ? '#f59e0b' : '#3b82f6';
    let dashArray = '';
    let weight = 2;
    let fillOpacity = 0;
    
    if (severity === 'CRITICAL') {
      color = '#facc15';
      weight = 4;
      fillOpacity = 0.6;
    } else if (severity === 'HIGH') {
      color = source === 'Hotspot' ? '#f59e0b' : '#ef4444';
      weight = 4;
      fillOpacity = 0.5;
    } else if (severity === 'MEDIUM') {
      color = source === 'Hotspot' ? '#d97706' : '#f59e0b';
      weight = 3;
      fillOpacity = 0.3;
    } else if (severity === 'LOW') {
      color = source === 'Hotspot' ? '#fbbf24' : '#3b82f6';
      dashArray = '5, 5';
    } else if (severity === 'INFO') {
      color = '#64748b';
      dashArray = '2, 4';
    }

    return {
      color,
      weight,
      dashArray,
      fillOpacity,
      fillColor: color,
    };
  };

  // 182. Allow a selected or highlighted polygon to open the Grid Explorer for that grid.
  const onEachFeature = (feature, layer) => {
    const gridId = feature.properties.cellId;
    const status = getGridStatus(gridId);
    const baseStyle = styleFeature(feature);

    layer.bindTooltip(status.severity ? `
      <strong>Grid #${gridId}</strong><br/>
      ${status.source}<br/>
      Severity: ${status.severity}
    ` : `
      <strong>Grid #${gridId}</strong><br/>
      Status: Normal
    `);
    
    layer.on({
      click: () => {
        if (onGridSelect) onGridSelect(gridId);
      },
      mouseover: (e) => {
        const target = e.target;
        target.bringToFront();
        target.setStyle({
          fillOpacity: Math.max(baseStyle.fillOpacity, 0.8),
          weight: baseStyle.weight + 1
        });
      },
      mouseout: (e) => {
        const target = e.target;
        target.setStyle(baseStyle);
      }
    });
  };

  return (
    <MapContainer center={center} zoom={12} style={{ height: '500px', width: '100%', borderRadius: '0.5rem' }}>
      {/* Light OpenStreetMap basemap */}
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {/* Render all grid polygons using Canvas for performance */}
      {allFeatures && allFeatures.features && (
        <GeoJSON
          data={allFeatures}
          style={styleFeature}
          onEachFeature={onEachFeature}
          renderer={L.canvas()}
          key={JSON.stringify([
            ...hotspots.map(item => `h-${item.grid_id}-${item.severity}`),
            ...alerts.map(item => `a-${item.grid_id}-${item.severity}`)
          ])}
        />
      )}
    </MapContainer>
  );
}
