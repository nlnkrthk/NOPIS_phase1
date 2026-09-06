# C11 — Checkpoints & Safe Rollback

## Activity

C11 — Checkpoints & Safe Rollback

## Tasks Completed

* Task 286 — Checkpoint creation
* Task 287 — Anomaly/risk threshold experiment
* Task 288 — Before-and-after operational comparison
* Task 289 — Regression/undesirable behaviour identification
* Task 290 — Safe rollback
* Task 291 — Decision and experiment documentation

---

## Checkpoint

* **Checkpoint Mechanism**: Git tree commit object referencing the complete uncommitted state, tagged with an explicit identifier.
* **Checkpoint Identifier**: `c11-checkpoint-pre-experiment` (commit object SHA: `7790f8180b7c2a7baca4982873f34479970f4b4a`).
* **Repository State Before Experiment**:
  - Full test suite passing (57/57 Phase 4 API tests passed, 9/9 pipeline tests passed, total 66/66 passing).
  - Raw telemetry data in `data/raw/` unmodified and intact.
  - Database warehouse tables verified.
* **Original Threshold / Rule**:
  - Statistical anomaly threshold: `anomaly_score >= 50.0%` (percentage deviation from historical median diurnal baseline for that grid and hour-of-day).
  - Implemented in ML4 (`Phase_6/ml_4.ipynb` cells 9 and 15) and operationalized via `Phase_4/services.py` (`get_rising_grids` querying `direction = 'HIGH'`).

---

## Experiment

* **Original Threshold**: `anomaly_score >= 50.0%` (flagging cells exceeding historical median by $\ge 50\%$).
* **New Threshold**: `anomaly_score >= 40.0%` (flagging cells exceeding historical median by $\ge 40\%$).
* **Why the Threshold was Changed**: Task 287 requested a controlled experiment to lower the threshold so that roughly twice as many grids are flagged, without changing the ML model, feature engineering, NP3 rule, database schema, or raw data. An empirical scan of `network_anomaly_scores` at the active reporting window (`2013-11-07 17:30:00`) showed that lowering the cutoff from 50% to 40% increased flagged grids from 161 to 311 (a 1.93× increase, precisely meeting the ~2× specification).
* **Files Changed**: `Phase_4/services.py` (inside `get_rising_grids`).

---

## Before-and-After Comparison

### 1. Alert Volume

| Scope / Dimension | Before (50.0% Threshold) | After (40.0% Threshold) | Absolute Change | Percentage Change |
| :--- | :--- | :--- | :--- | :--- |
| **Active Reporting Window (`2013-11-07 17:30:00`)** | 161 grids | 311 grids | +150 grids | **+93.17%** |
| **Entire Historical Dataset (`network_anomaly_scores`)** | 30,692 rows | 46,037 rows | +15,345 rows | **+49.99%** |
| **NP3 Rule Alerts (`total_activity >= 300.0` at 23:00)** | 3,691 alerts | 3,691 alerts | 0 alerts | **0.00%** (unchanged) |

### 2. Top-20 Attention List

* **Operational Attention List (Dashboard Priority: Top 20 by Proportional Activity)**:
  - **Before**: `[4857, 4856, 5458, 5758, 4855, 4457, 4755, 5955, 5567, 6073, 5857, 4462, 4456, 4654, 4655, 5061, 4754, 6169, 5959, 5658]`
  - **After**: `[4857, 4856, 5458, 5758, 4855, 4457, 4755, 5955, 5567, 6073, 5857, 4462, 4456, 4654, 4655, 5061, 4754, 6169, 5959, 5658]`
* **Top-20 Composition Changes**:
  - **Grids that stayed**: 20/20 grids (100% retention).
  - **Grids that entered**: 0 grids.
  - **Grids that left**: 0 grids.
  - *Note*: Top-20 extreme percentage outliers ($> 1,000\%$) in `get_rising_grids` also remained unchanged. However, at the classification boundary, **150 newly flagged grids** entered the active operational anomaly stream (scores between $+40.0\%$ and $+49.7\%$).

### 3. Agreement with NP3 Rule Alerts

Evaluated across all 9,929 Milan grid cells at reporting window `2013-11-07 17:30:00`:

| Quadrant | Definition | Before (50.0%) | After (40.0%) | Delta |
| :--- | :--- | :--- | :--- | :--- |
| **Both Active** | NP3 = 1, Anomaly = 1 | 76 grids | 129 grids | +53 grids |
| **Both Normal** | NP3 = 0, Anomaly = 0 | 6,192 grids | 6,095 grids | -97 grids |
| **NP3 Only** | Activity $\ge 300$, Anomaly $< \text{Threshold}$ | 3,576 grids | 3,523 grids | -53 grids |
| **Anomaly Only** | Anomaly $\ge \text{Threshold}$, Activity $< 300$ | 85 grids | 182 grids | +97 grids |
| **Total Agreement Rate** | $\frac{\text{Both Active} + \text{Both Normal}}{\text{Total Grids}}$ | **63.13%** | **62.69%** | **-0.44% (Worsened)** |

### 4. Test Results

* **`Phase_4/tests/`**: 57 passed, 0 failed.
* **`test_pipeline_91_92.py`**: 9 passed, 0 failed.
* **Total**: 66 passed, 0 failed.
* **Failure reasons**: None. All tests passed.

---

## Regression Analysis

### EVIDENCE
1. Lowering the threshold to 40% increased flagged anomaly alert volume from 161 to 311 grids (+93.17%).
2. Overall agreement between the anomaly detector and NP3 heuristic rule alerts decreased from 63.13% to 62.69% (-0.44%).
3. Of the 150 newly flagged grids, 97 grids (64.7%) had proportional total activity under 300, introducing "Anomaly Only" noise. Only 53 grids (35.3%) coincided with high absolute activity ($\ge 300$).
4. The top-20 operational attention list by volume remained identical.

### INTERPRETATION
1. **Alert Fatigue**: Doubling alert volume without an increase in operational precision floods NOC engineers with low-priority items.
2. **Low-Denominator Distortion**: Cells with low median baselines (e.g. 10 units) trigger percentage anomalies on trivial variations (e.g. +4.5 units), generating false positives.
3. **Signal Divergence**: Rather than improving signal convergence, lowering the threshold weakened the alignment between statistical deviations and operational rule alerts.

---

## Rollback

* **Whether Rollback Was Performed**: YES.
* **Checkpoint Used**: `c11-checkpoint-pre-experiment` (`7790f8180b7c2a7baca4982873f34479970f4b4a`).
* **Restoration Command**: `git checkout c11-checkpoint-pre-experiment -- Phase_4/services.py`.
* **Tests After Rollback**:
  - `Phase_4/tests/test_hotspots_alerts.py`: 16 passed, 0 failed.
  - `test_pipeline_91_92.py`: 9 passed, 0 failed.
  - Total: 25 focused regression tests passed with 100% pass rate.
* **Alert Volume After Rollback**: Returned exactly to **161 grids** at the active reporting window (`2013-11-07 17:30:00`) and 30,692 historically.
* **Whether Prior Behaviour Was Restored**: YES. Operational agreement returned to **63.13%**, top-20 rankings were preserved, and code diff against checkpoint is 0 bytes.

---

## Learner Decision

* **Decision**: **ROLLBACK**
* **Why the Learner Made That Decision**: The measured evidence showed that lowering the anomaly threshold to 40% created an undesirable +93.2% alert volume surge while worsening agreement with NP3 heuristic alerts (-0.44%). 64.7% of newly flagged cells were low-activity noise. The learner exercised their operational judgement to reject the change and restore the proven 50% baseline.

---

## Validation Results

* [x] **PASS**: Checkpoint created before change (`c11-checkpoint-pre-experiment`).
* [x] **PASS**: Quantitative before-and-after comparison exists (measured actual counts, percentages, and agreement).
* [x] **PASS**: Rollback verified (`Phase_4/services.py` restored with 0 bytes diff against checkpoint).
* [x] **PASS**: Alert volume returned to the prior value (161 grids at active window).

---

## Files Created or Modified

1. `Phase_4/services.py` — modified during Task 287 experiment, safely restored during Task 290 rollback.
2. `Phase_7/C11_Checkpoints_Safe_Rollback_Report.md` — newly created C11 milestone report.
3. `Phase_7/c11_walkthrough.md` — newly created C11 walkthrough document.
4. `CLAUDE.md` (root) & `Phase_7/CLAUDE.md` — updated with Section 15 documenting C11 checkpoint and rollback conventions.

---

## Final Status

**All C11 acceptance criteria passed.**
