import React, { useState } from 'react';
import { getPredictRisk } from '../api/config';

export default function PredictiveRisk() {
  const [gridInput, setGridInput] = useState('4821');
  const [asOfInput, setAsOfInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const handlePredict = async (e) => {
    e.preventDefault();
    const cleanId = parseInt(gridInput.trim(), 10);
    if (!cleanId || isNaN(cleanId)) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      // 183. Submit feature values or a selected grid to POST/network/predict-risk.
      const payload = { grid_id: cleanId };
      if (asOfInput.trim()) {
        payload.as_of = asOfInput.trim();
      }
      const response = await getPredictRisk(payload);
      setResult(response);
    } catch (err) {
      setError(err.message || 'Failed to generate prediction');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="risk-container">
      <div className="section-header">
        <div>
          <h2>Predictive Risk Assessment</h2>
          <p className="section-subtitle">ML Model Anomaly Scoring (Lab Phase)</p>
        </div>
      </div>

      <div className="risk-layout">
        <div className="risk-form-panel">
          <h3>Request Assessment</h3>
          <form onSubmit={handlePredict} className="risk-form">
            <div className="form-group">
              <label className="search-label">Target Grid ID:</label>
              <input
                type="number"
                className="grid-search-input"
                value={gridInput}
                onChange={(e) => setGridInput(e.target.value)}
                placeholder="e.g. 4821"
                min="1"
                max="10000"
                required
              />
            </div>
            
            <div className="form-group" style={{ marginTop: '1rem' }}>
              <label className="search-label">As Of (Optional):</label>
              <input
                type="datetime-local"
                className="grid-search-input"
                value={asOfInput}
                onChange={(e) => setAsOfInput(e.target.value)}
              />
            </div>
            
            <button type="submit" className="search-btn" disabled={loading}>
              {loading ? 'Evaluating...' : 'Run Prediction Model'}
            </button>
          </form>

          {error && (
            <div className="grid-status-alert alert-error" style={{ marginTop: '1rem' }}>
              <span className="alert-icon">⚠️</span>
              <div className="alert-body">
                <strong>Prediction Failed</strong>
                <p>{error}</p>
              </div>
            </div>
          )}
        </div>

        <div className="risk-result-panel">
          {result ? (
            <div className="risk-result-content">
              {/* 184. Display the risk score, the risk level and the model version. */}
              {/* 185. Show the model output visually separate from any narrative explanation. */}
              
              <div className="model-output-region">
                <div className="model-header">
                  <span className="model-badge">🤖 ML Output</span>
                  <span className="version-text">Model Version: {result.model_version}</span>
                </div>
                
                <div className="score-display">
                  <div className="score-main">
                    <span className="score-value">{(result.risk_score * 100).toFixed(1)}%</span>
                    <span className="score-label">Risk Probability</span>
                  </div>
                  <div className={`level-badge level-${result.risk_level.toLowerCase()}`}>
                    {result.risk_level} RISK
                  </div>
                </div>
                
                {result.explanation_note && (
                  <div className="stub-note">
                    {result.explanation_note}
                  </div>
                )}
              </div>

              <div className="narrative-region">
                <h4>Assistant Analysis</h4>
                <p className="narrative-placeholder-text">
                  LLM narrative explanation will be generated here to provide contextual insight into the prediction.
                </p>
                {/* 186. Add a placeholder "Explain with AI" action for the later Claude phase. */}
                <button className="explain-btn" disabled>
                  ✨ Explain with AI (Coming Soon)
                </button>
              </div>
            </div>
          ) : (
            <div className="empty-state">
              <span className="empty-icon">🧠</span>
              <p>Submit a grid ID to generate a predictive risk assessment.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
