# NOC Feature — Top Rising Grids

Show the grids whose `total_activity` increased most sharply relative to their
historical baseline in the current reporting window (AS_OF).

---

## Background

The project already has two pieces of baseline machinery:

1. **`network_anomaly_scores` (ML4, `Phase_6/ml_4.ipynb`)** — a pre-computed
   table with one row per `(grid_id, feature_timestamp)` that stores
   `current_value`, `baseline_value` (median `total_activity` across all
   historical hours with the same hour-of-day), `deviation`, `anomaly_score`
   (% deviation), and `direction` (NORMAL / HIGH / LOW).

2. **`get_grid_features()` live path (`Phase_4/services.py` lines 452–488)** —
   computes `activity_growth` (12-hour first-half vs second-half growth ratio)
   on the fly from the trailing 24 rows ending at `as_of`.

The new feature **reuses `network_anomaly_scores`**. That table already contains
exactly what we need: for each grid, it stores the deviation of the current
period from a pre-computed baseline that **excludes** the current reporting
interval (the baseline is computed from the median over all recorded hours for
the same hour-of-day, not including the current value). No new baseline
calculation is required.

---

## Open Questions

> [!IMPORTANT]
> **Q1 — Baseline definition.** The `network_anomaly_scores` table stores
> `anomaly_score` as a percentage deviation of `current_value` vs `baseline_value`.
> Is this the correct measure of "sharpest increase", or should we rank by
> `current_value - baseline_value` (raw absolute uplift)?
>
> **Recommendation:** use `anomaly_score` (% deviation) so that a grid going
> from 10 → 50 ranks above a large grid going from 1000 → 1100. Absolute delta
> is also easy to add. Please confirm.

> [!IMPORTANT]
> **Q2 — Direction filter.** Should the endpoint return only grids whose
> `direction = 'HIGH'` (rising above baseline), or should it also include
> `direction = 'NORMAL'`/`'LOW'` grids for completeness?
>
> **Recommendation:** default to `direction IN ('HIGH', 'NORMAL')` so
> downward-trending grids are excluded, but expose an optional `direction`
> query parameter the caller can override.

> [!NOTE]
> **Q3 — Freshness.** `network_anomaly_scores` is populated by re-running
> `Phase_6/ml_4.ipynb`. If the notebook has not been re-run since the last
> pipeline run, the table may be stale. The plan does not change this
> refresh mechanism — it only reads what is already there.

---

## 1. Where the Calculation Should Happen

**Layer: API service layer (`Phase_4/services.py`) — SQL query only.**

Reasons:
- The data we need (`current_value`, `baseline_value`, `anomaly_score`,
  `direction`) already exists in `network_anomaly_scores`. The ranking is a
  simple `ORDER BY anomaly_score DESC` with an optional `direction` filter.
- Adding this to Spark would require a new pipeline stage for a read-only
  ranking operation — unnecessary complexity.
- Doing it in Python after fetching all rows would load thousands of rows into
  memory just to sort them — unnecessary.
- The pattern matches exactly how `get_hotspots()` and `get_alerts()` work:
  one SQL query, server-side `ORDER BY`, Python-side severity enrichment.

The `AS_OF` convention is preserved by filtering
`feature_timestamp <= effective_as_of` so that future rows are excluded.

---

## 2. Existing Baseline Logic and Reuse Strategy

### What exists
`network_anomaly_scores` columns (from `Phase_6/ml_4.ipynb`):

| Column | Meaning |
|---|---|
| `grid_id` | Grid cell |
| `feature_timestamp` | The hourly timestamp this score relates to |
| `current_value` | `total_activity` at `feature_timestamp` |
| `baseline_value` | Median `total_activity` across **all historical** same-hour rows |
| `deviation` | `current_value - baseline_value` |
| `anomaly_score` | `(deviation / baseline_value) * 100` (% deviation) |
| `direction` | `'HIGH'` / `'LOW'` / `'NORMAL'` |
| `anomaly_flag` | boolean |
| `reason` | human-readable string |

The baseline definition **already excludes the current reporting interval**
because the ML4 notebook calculates the median over all available historical
hours before computing scores. The current hour's value (`current_value`) is
compared *against* the median — it is not included *in* the median.

### Reuse plan
- `get_rising_grids()` in `services.py` will `SELECT` directly from
  `network_anomaly_scores`, ordered by `anomaly_score DESC`.
- No new median, no new growth calculation — just a SQL read of the
  pre-computed table.
- The `get_evidence_object()` function in `services.py` already JOINs
  `grid_features` with `network_anomaly_scores` — the new function only
  queries `network_anomaly_scores` alone (simpler).

---

## 2. Proposed Changes — Impact Analysis

### Files that must change

| File | Change |
|---|---|
| `Phase_4/services.py` | Add `get_rising_grids()` function (~40 lines) |
| `Phase_4/schemas.py` | Add `RisingGridItem` Pydantic model |
| `Phase_4/routers/network.py` | Add `GET /network/rising-grids` endpoint |
| `Phase_5/src/api/config.js` | Add `getRisingGrids()` fetch helper |
| `Phase_5/src/components/HotspotsAlerts.jsx` | Add "Rising Grids" panel/tab |
| `Phase_4/tests/test_hotspots_alerts.py` | Add tests for new endpoint |

### Files that must NOT change

| File | Why |
|---|---|
| `spark/` (all files) | No ETL change needed |
| `warehouse/` (all files) | No schema change needed |
| `ml/features.py` | No feature engineering change |
| `Phase_4/ml5_model_service.py` | No ML inference change |
| `Phase_4/claude_insight_service.py` | No LLM change |
| `Phase_4/schemas.py` (existing models) | Only adding — not modifying |
| `Phase_4/routers/network.py` (existing routes) | Only adding — not modifying |
| `Phase_5/src/api/config.js` (existing functions) | Only adding |
| `Phase_5/src/components/NetworkSummary.jsx` | Unchanged |
| `Phase_5/src/components/GridActivity.jsx` | Unchanged |
| `Phase_5/src/components/PredictiveRisk.jsx` | Unchanged |
| `Phase_5/src/components/MapLayer.jsx` | Unchanged |
| `Phase_5/src/App.jsx` | Unchanged |
| `warehouse/schema.sql` | Unchanged |
| `test_pipeline_91_92.py` | Unchanged |

---

## 3. Data / Calculation Flow

```
AS_OF parameter
    |
    v
GET /network/rising-grids?limit=N&as_of=YYYY-MM-DDTHH:00:00&direction=HIGH
    |
    v
get_rising_grids(db, limit, as_of, direction)   <- new function in services.py
    |
    |  Resolve effective_as_of (same pattern as get_hotspots / get_alerts):
    |    if as_of is None  ->  MAX(feature_timestamp) from network_anomaly_scores
    |    else              ->  as_of.replace(minute=0, second=0, microsecond=0)
    |
    v
SQL:
    SELECT
        nas.grid_id,
        nas.feature_timestamp,
        nas.current_value     AS current_activity,
        nas.baseline_value    AS baseline_activity,
        nas.deviation         AS absolute_delta,
        nas.anomaly_score     AS pct_increase,
        nas.direction
    FROM network_anomaly_scores nas
    WHERE nas.feature_timestamp <= :as_of          -- respect AS_OF boundary
      AND nas.direction != 'LOW'                   -- only rising / flat grids
    ORDER BY nas.anomaly_score DESC                -- sharpest increase first
    LIMIT :limit
    |
    v
Return list of RisingGridItem dicts
    |
    v
React: fetch & render in a new "Rising Grids" panel inside HotspotsAlerts.jsx
```

> [!IMPORTANT]
> The baseline exclusion rule is satisfied automatically: `baseline_value` in
> `network_anomaly_scores` was computed as the **median of all historical same-hour
> rows** at the time the ML4 notebook ran. The current hour's value is `current_value`,
> which is *compared against* — not included in — the baseline.

---

## 4. API Contract

### New endpoint

```
GET /network/rising-grids
```

**Query parameters** (all optional):

| Parameter | Type | Default | Description |
|---|---|---|---|
| `limit` | int (1–500) | 10 | Max rows to return |
| `as_of` | datetime | MAX(feature_timestamp) | Reporting boundary (AS_OF convention) |
| `direction` | str | `HIGH` | Filter by anomaly direction. `HIGH` = rising only |

**Response — list of `RisingGridItem`:**

```json
[
  {
    "grid_id": 4821,
    "feature_timestamp": "2013-11-07T17:00:00",
    "current_activity": 1425.3,
    "baseline_activity": 890.1,
    "absolute_delta": 535.2,
    "pct_increase": 60.1,
    "direction": "HIGH"
  }
]
```

**Backward compatibility:** this is a brand-new endpoint. Existing endpoints
(`/network/hotspots`, `/network/alerts`, `/network/summary`, `/network/grid/*`,
`/network/predict-risk`) are completely unchanged. No existing client breaks.

### New Pydantic model in `schemas.py`

```python
class RisingGridItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    grid_id: int
    feature_timestamp: datetime
    current_activity: float
    baseline_activity: float
    absolute_delta: float
    pct_increase: float
    direction: str
```

No existing schema is modified.

---

## 5. React Implementation

### Where: `HotspotsAlerts.jsx`

This is the natural home because:
- It already shows ranked operational attention grids.
- It already imports `getNetworkHotspots` and `getNetworkAlerts` from `config.js`.
- The new panel is conceptually related (another ranked view of grids needing attention).
- No new route or page navigation needed in `App.jsx`.

### What changes inside `HotspotsAlerts.jsx`

1. Import a new `getRisingGrids` function from `../api/config`.
2. Add `const [risingGrids, setRisingGrids] = useState([])` state.
3. Inside `fetchApiData()`, add one more parallel fetch:
   `getRisingGrids(limit)` alongside the existing hotspot/alert fetches.
4. Add a new "Rising Grids" table section below the existing table.
   - Columns: Grid, Current Activity, Baseline, % Increase, Timestamp.
   - Each row clickable → `onNavigateToGrid(grid_id)` (same pattern as
     the existing `rankedItems` table).
5. No existing state, fetch, or render logic is removed or modified.

### `config.js` addition

```js
export async function getRisingGrids(limit = 10, asOf = '', direction = 'HIGH') {
  const params = new URLSearchParams({ limit });
  if (asOf) params.append('as_of', asOf);
  if (direction) params.append('direction', direction);
  const response = await fetch(`${API_BASE_URL}/network/rising-grids?${params}`);
  if (!response.ok) throw new Error(`Rising grids request failed: ${response.status}`);
  return response.json();
}
```

---

## 6. Tests

### Existing tests to extend

| File | What to add |
|---|---|
| `Phase_4/tests/test_hotspots_alerts.py` | Tests for the new `/network/rising-grids` endpoint (see below) |

### New tests required

**Endpoint contract tests** (in `test_hotspots_alerts.py`):

1. `test_rising_grids_default_returns_200` — `GET /network/rising-grids` returns 200 and a list.
2. `test_rising_grids_limit_respected` — `?limit=5` returns exactly 5 rows.
3. `test_rising_grids_ordered_by_pct_increase_desc` — each row has `pct_increase >= next row`.
4. `test_rising_grids_all_grid_ids_valid` — every `grid_id` in `1–10000`.
5. `test_rising_grids_fields_present` — every row contains `grid_id`, `feature_timestamp`, `current_activity`, `baseline_activity`, `absolute_delta`, `pct_increase`, `direction`.
6. `test_rising_grids_direction_filter` — `?direction=HIGH` returns only rows where `direction == 'HIGH'`.
7. `test_rising_grids_no_congestion_language` — the word "congestion" appears nowhere in any response field.

**Baseline exclusion test** (unit test, mocked DB):

8. `test_rising_grids_baseline_excludes_current_interval` — mock `network_anomaly_scores` to return a known set; assert that `baseline_activity != current_activity` for every returned row (i.e. the current value is never used as its own baseline).

**AS_OF boundary test**:

9. `test_rising_grids_as_of_respected` — pass `as_of = some_past_timestamp`; assert that no returned `feature_timestamp` exceeds `as_of`.

**Backward-compatibility test**:

10. `test_existing_endpoints_unchanged_after_rising_grids` — verify `/network/hotspots`, `/network/alerts`, `/network/summary` still return 200 and their existing fields after the new endpoint is added.

---

## 7. Verification Steps

After implementation:

```powershell
# 1. Run all existing API tests (must all still pass)
python -m pytest Phase_4/tests/ -v

# 2. Run the pipeline tests (must be unchanged)
python -m pytest test_pipeline_91_92.py -v

# 3. Start the API
cd Phase_4
uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# 4. Manual spot checks
# Default — top 10 rising grids
curl http://127.0.0.1:8000/network/rising-grids

# With limit and as_of
curl "http://127.0.0.1:8000/network/rising-grids?limit=5&as_of=2013-11-07T17:00:00"

# Existing endpoints unchanged
curl http://127.0.0.1:8000/network/hotspots
curl http://127.0.0.1:8000/network/alerts
curl http://127.0.0.1:8000/network/summary

# 5. Start the dashboard and confirm the Rising Grids panel appears
cd Phase_5
npm run dev
# Open http://localhost:5173 -> Hotspots & Alerts page -> verify Rising Grids table
```

**End-to-end verification:**
- Rising Grids table renders in the React dashboard.
- Rows are ordered with the highest `pct_increase` first.
- Clicking a row navigates to `GridActivity` for that `grid_id`.
- The `as_of` parameter scopes results correctly (compare with a known
  timestamp from `SELECT MAX(feature_timestamp) FROM network_anomaly_scores`).

---

## 8. Risks and Assumptions

| Risk / Assumption | Mitigation |
|---|---|
| `network_anomaly_scores` may be empty if ML4 notebook was never run | Endpoint returns `[]` (same as hotspots/alerts when no data). Add a clear empty-state in the React panel. |
| The table has no index on `feature_timestamp` | Add `CREATE INDEX idx_nas_timestamp ON network_anomaly_scores(feature_timestamp)` in the implementation notes, but this is an optional optimization, not a blocker. |
| `anomaly_score` can be negative for `direction='LOW'` grids | The `direction != 'LOW'` filter removes them before `ORDER BY`. |
| The ML4 notebook may redefine "baseline" differently in future versions | The service function reads only stored columns — it does not re-implement the formula. If the notebook changes the formula, the stored values change automatically. |
| React state management | No shared global state is needed — `risingGrids` lives entirely inside `HotspotsAlerts.jsx`, matching the existing hotspot/alert state pattern. |

---

## Summary Table

### Files to change
- `Phase_4/services.py` — add `get_rising_grids()`
- `Phase_4/schemas.py` — add `RisingGridItem`
- `Phase_4/routers/network.py` — add `GET /network/rising-grids`
- `Phase_5/src/api/config.js` — add `getRisingGrids()`
- `Phase_5/src/components/HotspotsAlerts.jsx` — add Rising Grids panel
- `Phase_4/tests/test_hotspots_alerts.py` — add 10 new tests

### Files to leave unchanged
All Spark files, warehouse files, ML files, `App.jsx`, `NetworkSummary.jsx`,
`GridActivity.jsx`, `PredictiveRisk.jsx`, `MapLayer.jsx`, `main.py`,
`ml5_model_service.py`, `claude_insight_service.py`, `test_pipeline_91_92.py`,
`warehouse/schema.sql`.

### Baseline reuse strategy
Read `baseline_value` and `anomaly_score` directly from `network_anomaly_scores`.
No new formula, no duplicated baseline logic.
