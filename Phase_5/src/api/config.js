// 161.Create the app and the API base configuration.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

/**
 * Helper function to fetch the high-level network summary.
 * Accepts optional from/to ISO datetime strings or an as_of timestamp.
 * Returns the parsed JSON response or throws an error.
 */
export async function getNetworkSummary(fromDt = '', toDt = '', asOf = '') {
  try {
    const params = new URLSearchParams();
    if (fromDt) params.append('from_dt', fromDt);
    if (toDt) params.append('to_dt', toDt);
    if (asOf) params.append('as_of', asOf);
    const queryString = params.toString() ? `?${params.toString()}` : '';
    
    const response = await fetch(`${API_BASE_URL}/network/summary${queryString}`);
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Server returned status ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    if (error.name === 'TypeError' && error.message.includes('fetch')) {
      throw new Error(`Cannot connect to API at ${API_BASE_URL}. Ensure the FastAPI backend is running.`);
    }
    throw error;
  }
}

/**
 * Helper function to fetch time-series activity for a specific grid with optional date/hour filters.
 */
export async function getGridActivity(gridId, options = {}) {
  try {
    const params = new URLSearchParams();
    if (options.date) params.append('date', options.date);
    if (options.hour !== undefined && options.hour !== '') params.append('hour', options.hour);
    if (options.as_of) params.append('as_of', options.as_of);
    if (options.from_dt) params.append('from_dt', options.from_dt);
    if (options.to_dt) params.append('to_dt', options.to_dt);

    const queryString = params.toString() ? `?${params.toString()}` : '';
    const response = await fetch(`${API_BASE_URL}/network/grid/${gridId}${queryString}`);
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const error = new Error(errorData.detail || `Grid ${gridId} request failed with status ${response.status}`);
      error.status = response.status;
      throw error;
    }
    return await response.json();
  } catch (error) {
    if (error.name === 'TypeError' && error.message.includes('fetch')) {
      const connError = new Error(`Cannot connect to API at ${API_BASE_URL}. Ensure the FastAPI backend is running.`);
      connError.status = 503;
      throw connError;
    }
    throw error;
  }
}

// 176. Call /network/hotspots and /network/alerts.
export async function getNetworkHotspots(limit = 10, asOf = '') {
  const params = new URLSearchParams({ limit });
  if (asOf) params.append('as_of', asOf);
  
  const response = await fetch(`${API_BASE_URL}/network/hotspots?${params}`);
  if (!response.ok) throw new Error(`Failed to fetch hotspots: ${response.status}`);
  return response.json();
}

export async function getNetworkAlerts(limit = 20, severity = '', asOf = '') {
  const params = new URLSearchParams({ limit });
  if (severity) params.append('severity', severity);
  if (asOf) params.append('as_of', asOf);
  
  const response = await fetch(`${API_BASE_URL}/network/alerts?${params}`);
  if (!response.ok) throw new Error(`Failed to fetch alerts: ${response.status}`);
  return response.json();
}
// 183. Submit feature values or a selected grid to POST /network/predict-risk.
export async function getPredictRisk(payload) {
  // payload should contain at least { grid_id: <id> } and optional feature fields.
  const response = await fetch(`${API_BASE_URL}/network/predict-risk`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Predict risk request failed: ${response.status}`);
  }
  return response.json(); // expected { risk_score, risk_level, model_version }
}
