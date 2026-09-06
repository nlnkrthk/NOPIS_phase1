<!-- 299. Package them into a project or team plugin. -->
---
description: Compare rule-based alerts, ML classifier output, and statistical anomaly scores for a grid (NOC-oriented)
---

# /review-anomaly

Cross-examines three independent signal sources for a grid cell to identify consensus or explain divergence:
1. **Rule-based alert** (from `GET /network/alerts`)
2. **ML risk classifier** (from `POST /network/predict-risk`)
3. **Statistical anomaly score** (from `network_anomaly_scores`)

## Usage
```text
/review-anomaly <grid_id> [as_of]
```

### Example
```text
/review-anomaly 4821
```

## Behind the Scenes
Executes:
```bash
python Phase_7/c_tasks/project_commands.py review-anomaly $1 $2
```

## Expected Output
- **1. Rule-Based Alert**: Type, Severity, and Reason
- **2. ML Risk Classifier**: Risk Score and Level (LOW, MEDIUM, HIGH, CRITICAL)
- **3. Statistical Anomaly Score**: Direction (HIGH/NORMAL/LOW), % deviation from baseline, delta
- **Signal Convergence**: `AGREEMENT (NORMAL)`, `AGREEMENT (ELEVATED)`, or `PARTIAL DISAGREEMENT`
- **Explanation of Disagreement**: Detailed root cause for differing signals (e.g. baseline vs. feature velocity)
