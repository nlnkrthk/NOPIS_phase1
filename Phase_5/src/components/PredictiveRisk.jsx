import React, { useEffect, useState } from 'react';
import { getAvailableModels, getGridFeatures, getPredictRisk, getGridInsight } from '../api/config';

const FEATURE_FIELDS = [
  ['avg_activity', 'Average activity'],
  ['activity_growth', 'Activity growth'],
  ['active_hours', 'Active hours'],
  ['peak_ratio', 'Peak ratio'],
  ['variability', 'Variability'],
  ['internet_share', 'Internet share'],
];

// C1 — Task 230. Claude always responds in these exact four sections;
// split the raw text back into a { SEVERITY, EVIDENCE, INTERPRETATION,
// NEXTCHECKS } map so each can be styled separately in the UI.
const INSIGHT_HEADINGS = ['SEVERITY', 'EVIDENCE', 'INTERPRETATION', 'NEXTCHECKS'];

function parseInsightSections(text) {
  const sections = {};
  let current = null;
  (text || '').split('\n').forEach((line) => {
    const heading = INSIGHT_HEADINGS.find((h) => h === line.trim());
    if (heading) {
      current = heading;
      sections[current] = [];
    } else if (current) {
      sections[current].push(line);
    }
  });
  Object.keys(sections).forEach((key) => {
    sections[key] = sections[key].join('\n').trim();
  });
  return sections;
}

// Maps Claude's SEVERITY line to a badge style. Falls back to
// "indeterminate" when the evidence was insufficient (Task 233) — Claude
// is instructed to say so explicitly rather than guessing a level.
function severityBadgeInfo(severityText) {
  const upper = (severityText || '').toUpperCase();
  if (upper.includes('HIGH')) return { label: 'HIGH', className: 'level-high' };
  if (upper.includes('ATTENTION')) return { label: 'ATTENTION', className: 'level-medium' };
  if (upper.includes('NORMAL')) return { label: 'NORMAL', className: 'level-low' };
  return { label: 'INDETERMINATE', className: 'level-indeterminate' };
}

export default function PredictiveRisk() {
  const [gridInput, setGridInput] = useState('4821');
  const [asOfInput, setAsOfInput] = useState('');
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState('');
  const [inputMode, setInputMode] = useState('stored');
  const [featureInputs, setFeatureInputs] = useState({});
  const [submittedInputs, setSubmittedInputs] = useState(null);
  const [featuresLoading, setFeaturesLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  // C1 — Task 230. State for the "Explain with AI" Claude insight panel.
  const [insight, setInsight] = useState(null);
  const [insightLoading, setInsightLoading] = useState(false);
  const [insightError, setInsightError] = useState(null);

  useEffect(() => {
    getAvailableModels()
      .then((availableModels) => {
        setModels(availableModels);
        if (availableModels.length) setSelectedModel(availableModels[0].model_version);
      })
      .catch((err) => setError(err.message || 'Failed to load available models'));
  }, []);

  useEffect(() => {
    const cleanId = parseInt(gridInput, 10);
    if (!cleanId || cleanId < 1 || cleanId > 10000 || !asOfInput || inputMode !== 'stored') return;
    setFeaturesLoading(true);
    getGridFeatures(cleanId, asOfInput)
      .then((features) => setFeatureInputs({
        avg_activity: features.avg_activity,
        activity_growth: features.activity_growth,
        active_hours: features.active_hours,
        peak_ratio: features.peak_ratio,
        variability: features.variability,
        internet_share: features.internet_share,
      }))
      .catch(() => setFeatureInputs({}))
      .finally(() => setFeaturesLoading(false));
  }, [gridInput, asOfInput, inputMode]);

  const handlePredict = async (e) => {
    e.preventDefault();
    const cleanId = parseInt(gridInput.trim(), 10);
    if (!cleanId || isNaN(cleanId)) return;

    setLoading(true);
    setError(null);
    setResult(null);
    // A new prediction targets a (possibly different) grid — any previous
    // AI insight no longer applies, so clear it rather than showing stale data.
    setInsight(null);
    setInsightError(null);

    try {
      // 183. Submit feature values or a selected grid to POST/network/predict-risk.
      const payload = { grid_id: cleanId, model_version: selectedModel };
      payload.as_of = asOfInput.trim();
      FEATURE_FIELDS.forEach(([field]) => {
        if (featureInputs[field] !== '' && featureInputs[field] !== undefined) {
          payload[field] = Number(featureInputs[field]);
        }
      });
      const response = await getPredictRisk(payload);
      setSubmittedInputs(payload);
      setResult(response);
    } catch (err) {
      setError(err.message || 'Failed to generate prediction');
    } finally {
      setLoading(false);
    }
  };

  // C1 — Task 230. Explain the same grid's evidence-grounded operational
  // context via GET /network/grid/{grid_id}/insight.
  const handleExplainWithAI = async () => {
    if (!submittedInputs?.grid_id) return;
    setInsightLoading(true);
    setInsightError(null);
    setInsight(null);
    try {
      const data = await getGridInsight(submittedInputs.grid_id);
      setInsight(data);
    } catch (err) {
      setInsightError(err.message || 'Failed to generate AI insight');
    } finally {
      setInsightLoading(false);
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
              <label className="search-label" htmlFor="risk-model">Prediction model</label>
              <select id="risk-model" className="grid-search-input" value={selectedModel} onChange={(e) => setSelectedModel(e.target.value)} required>
                {!models.length && <option value="">Loading models...</option>}
                {models.map((model) => <option key={model.model_version} value={model.model_version}>{model.model_version} · {model.model_type}</option>)}
              </select>
              {models.find((model) => model.model_version === selectedModel) && (
                <span className="field-hint">Features: {models.find((model) => model.model_version === selectedModel).features.join(', ')}</span>
              )}
            </div>

            <div className="form-group">
              <label className="search-label" htmlFor="risk-grid">Target grid ID</label>
              <input
                id="risk-grid"
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
              <label className="search-label" htmlFor="risk-as-of">Timestamp</label>
              <input
                type="datetime-local"
                className="grid-search-input"
                value={asOfInput}
                onChange={(e) => setAsOfInput(e.target.value)}
                required
              />
            </div>

            <div className="risk-mode-toggle" role="group" aria-label="Feature input mode">
              <button type="button" className={inputMode === 'stored' ? 'mode-button active' : 'mode-button'} onClick={() => setInputMode('stored')}>Stored features</button>
              <button type="button" className={inputMode === 'custom' ? 'mode-button active' : 'mode-button'} onClick={() => setInputMode('custom')}>Custom input</button>
            </div>

            <div className="risk-features-panel">
              <div className="features-heading">
                <strong>{inputMode === 'custom' ? 'Custom feature values' : 'Resolved feature values'}</strong>
                <span>{featuresLoading ? 'Loading...' : inputMode === 'stored' ? 'From feature store' : 'Sent to model'}</span>
              </div>
              <div className="feature-grid">
                {FEATURE_FIELDS.map(([field, label]) => (
                  <label key={field} className="feature-field">
                    <span>{label}</span>
                    <input type="number" step="any" value={featureInputs[field] ?? ''} onChange={(e) => setFeatureInputs({ ...featureInputs, [field]: e.target.value })} readOnly={inputMode === 'stored'} placeholder="Auto" />
                  </label>
                ))}
              </div>
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

                {submittedInputs && (
                  <div className="prediction-inputs">
                    <h4>Inputs used</h4>
                    <div className="input-summary-grid">
                      <span>Model <strong>{submittedInputs.model_version}</strong></span>
                      <span>Grid <strong>{submittedInputs.grid_id}</strong></span>
                      <span>Timestamp <strong>{submittedInputs.as_of || 'Latest stored data'}</strong></span>
                      {FEATURE_FIELDS.map(([field, label]) => <span key={field}>{label} <strong>{submittedInputs[field] ?? 'Stored by API'}</strong></span>)}
                    </div>
                  </div>
                )}
                
                {result.explanation_note && (
                  <div className="stub-note">
                    {result.explanation_note}
                  </div>
                )}
              </div>

              <div className="narrative-region">
                <h4>Assistant Analysis</h4>

                {!insight && !insightLoading && !insightError && (
                  <p className="narrative-placeholder-text">
                    Get an evidence-grounded operational explanation for Grid #{submittedInputs?.grid_id} from Claude —
                    it only reasons over the stored activity-measure evidence, never invents numbers, and never claims
                    network congestion.
                  </p>
                )}

                {/* C1 — Task 186/230. "Explain with AI" now calls GET /network/grid/{grid_id}/insight. */}
                <button
                  className="explain-btn"
                  onClick={handleExplainWithAI}
                  disabled={insightLoading || !submittedInputs?.grid_id}
                >
                  {insightLoading ? '✨ Generating insight...' : '✨ Explain with AI'}
                </button>

                {insightError && (
                  <div className="grid-status-alert alert-error">
                    <span className="alert-icon">⚠️</span>
                    <div className="alert-body">
                      <strong>AI Insight Failed</strong>
                      <p>{insightError}</p>
                    </div>
                  </div>
                )}

                {insight && (() => {
                  const sections = parseInsightSections(insight.claude_response);
                  const severity = severityBadgeInfo(sections.SEVERITY);
                  const ev = insight.evidence;
                  return (
                    <div className="ai-insight-content">
                      <div className="insight-evidence-strip">
                        <span>Grid <strong>#{ev.grid_id}</strong></span>
                        <span>Timestamp <strong>{ev.timestamp}</strong></span>
                        <span>Current activity <strong>{ev.current_activity.toFixed(2)}</strong></span>
                        <span>Baseline activity <strong>{ev.baseline_activity.toFixed(2)}</strong></span>
                        <span>Direction <strong>{ev.direction}</strong></span>
                        <span>Anomaly score <strong>{ev.anomaly_score.toFixed(2)}</strong></span>
                      </div>

                      {ev.rule_alerts?.length > 0 && (
                        <div className="insight-rule-alerts">
                          {ev.rule_alerts.map((alert, idx) => (
                            <span key={idx} className="insight-alert-chip">
                              🚩 {alert.direction}: {alert.reason}
                            </span>
                          ))}
                        </div>
                      )}

                      <div className="insight-section insight-severity">
                        <div className="insight-section-heading">
                          <span>Severity</span>
                          <span className={`level-badge ${severity.className}`}>{severity.label}</span>
                        </div>
                        <p className="insight-section-text">{sections.SEVERITY}</p>
                      </div>

                      <div className="insight-section">
                        <div className="insight-section-heading"><span>📋 Evidence</span></div>
                        <p className="insight-section-text">{sections.EVIDENCE}</p>
                      </div>

                      <div className="insight-section insight-interpretation">
                        <div className="insight-section-heading">
                          <span>🔮 Interpretation</span>
                          <span className="insight-inference-tag">Inference — not a confirmed fact</span>
                        </div>
                        <p className="insight-section-text">{sections.INTERPRETATION}</p>
                      </div>

                      <div className="insight-section">
                        <div className="insight-section-heading"><span>🔧 Next Checks</span></div>
                        <p className="insight-section-text">{sections.NEXTCHECKS}</p>
                      </div>

                      <div className="insight-model-tag">Model: {insight.model}</div>
                    </div>
                  );
                })()}
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
