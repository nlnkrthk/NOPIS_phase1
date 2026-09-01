# NOPIS API5 — Prediction Endpoint Contract (`POST /network/predict-risk`)

This contract defines the stable interface for the Network Risk Prediction Endpoint consumed by React clients, NOC dashboards, and Claude investigation agents.

## Endpoint Specification

- **HTTP Method**: `POST`
- **Path**: `/network/predict-risk`
- **Content-Type**: `application/json`

---

## 1. Request Body Schema (`PredictRiskRequest`)

| Field | Type | Required | Range / Format | Description |
| :--- | :--- | :--- | :--- | :--- |
| `grid_id` | `integer` | **Yes** | `1` to `10000` | Target Milan grid identifier. |
| `as_of` | `datetime` | No | ISO 8601 string | Optional reference timestamp for prediction. |
| `avg_activity` | `float` | No | `≥ 0.0` | Optional override for average network activity. |
| `activity_growth` | `float` | No | Any float | Optional override for activity growth rate. |
| `active_hours` | `integer` | No | `0` to `24` | Optional override for active hours count. |
| `peak_ratio` | `float` | No | `≥ 0.0` | Optional override for peak-to-average ratio. |
| `variability` | `float` | No | `≥ 0.0` | Optional override for activity variability / std ratio. |
| `internet_share` | `float` | No | `0.0` to `1.0` | Optional override for internet traffic proportion. |

### Sample Request Payload
```json
{
  "grid_id": 4821,
  "as_of": "2013-11-03T17:30:00",
  "avg_activity": 1250.5
}
```

---

## 2. Response Body Schema (`PredictRiskResponse`)

| Field | Type | Description |
| :--- | :--- | :--- |
| `grid_id` | `integer` | The grid identifier evaluated. |
| `risk_score` | `float` | Continuous risk probability score bounded in `[0.0, 1.0]`. |
| `risk_level` | `string` | Categorical classification: `"LOW"`, `"MEDIUM"`, `"HIGH"`, or `"CRITICAL"`. |
| `model_version` | `string` | Identifies the serving model version (e.g. `"stub-v0.1.0"`, `"lgbm-v1.0.0"`). |
| `prediction_timestamp` | `datetime` | ISO 8601 timestamp when prediction was generated. |
| `explanation_note` | `string` | Human-readable explanation of risk assessment or stub status. |
| `is_stub` | `boolean` | `true` for stub phase; `false` once ML5 production model is wired in. |

### Sample Response Payload
```json
{
  "grid_id": 4821,
  "risk_score": 0.65,
  "risk_level": "HIGH",
  "model_version": "stub-v0.1.0",
  "prediction_timestamp": "2026-08-31T23:15:00",
  "explanation_note": "STUB IMPLEMENTATION: This is a placeholder prediction model contract (stub-v0.1.0). ML5 will replace this stub with the trained production model while preserving this exact contract.",
  "is_stub": true
}
```

---

## 3. Integration Guidelines for ML5

1. **Contract Invariance**: When ML5 trains and wires in the model, the response field names and data types **must remain identical**.
2. **React Independence**: No frontend React code changes are required when swapping `is_stub: true` to `is_stub: false`.
3. **Validation Rules**: Requests missing `grid_id` or providing invalid ranges (`grid_id < 1` or `> 10000`) will return `422 Unprocessable Entity` or `404 Not Found`.
