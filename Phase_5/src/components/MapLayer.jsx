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
  const getGridSeverity = (gridId) => {
    // Alert takes precedence if it's HIGH, otherwise check hotspot severity
    const alert = alertMap.get(gridId);
    const hotspot = hotspotMap.get(gridId);
    
    if (alert && alert.severity === 'HIGH') return 'HIGH';
    if (hotspot && hotspot.severity === 'HIGH') return 'HIGH';
    if (alert && alert.severity === 'ATTENTION') return 'ATTENTION';
    if (hotspot && hotspot.severity === 'ATTENTION') return 'ATTENTION';
    
    return 'NORMAL';
  };

  // 181.Visually distinguish NORMAL, ATTENTION and HIGH in both the ranked table and the map.
  const styleFeature = (feature) => {
    const gridId = feature.properties.cellId;
    const severity = getGridSeverity(gridId);
    
    let color = '#3b82f6'; // NORMAL border blue
    let dashArray = '';
    let weight = 2;
    let fillOpacity = 0; // no fill for normal
    
    if (severity === 'HIGH') {
      color = '#ef4444'; // Red
      weight = 4;
      fillOpacity = 0.6; // keep red fill highlight
    } else if (severity === 'ATTENTION') {
      color = '#f59e0b'; // Amber
      dashArray = '5, 5'; // Dashed border so it doesn't rely on color alone
      weight = 3;
      fillOpacity = 0; // no fill for attention, only outline
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
    const severity = getGridSeverity(gridId);
    
    layer.bindTooltip(`
      <strong>Grid #${gridId}</strong><br/>
      Status: ${severity}
    `);
    
    layer.on({
      click: () => {
        if (onGridSelect) onGridSelect(gridId);
      },
      mouseover: (e) => {
        const target = e.target;
        target.setStyle({ fillOpacity: 0.8 });
      },
      mouseout: (e) => {
        const target = e.target;
        target.setStyle({ fillOpacity: styleFeature(feature).fillOpacity });
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
          key={JSON.stringify(allFeatures.features.map(f => f.properties.cellId))}
        />
      )}
    </MapContainer>
  );
}
