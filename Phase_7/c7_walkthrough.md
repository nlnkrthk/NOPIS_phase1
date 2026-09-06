# C7 — Reusable Claude Code Project Slash Commands Walkthrough

This document records the completion of **C7 (Tasks 264–268)**, converting repeated network engineering and NOC checks into reusable Claude Code slash commands.

---

## 1. Task 264: Command Creation & Structure

We created the root `.claude/` directory and `.claude/commands/` subfolder containing the five project-level slash commands. To ensure deterministic execution, all commands are backed by [`Phase_4/project_commands.py`](file:///d:/NOPIS/Phase_4/project_commands.py).

### Command Inventory

| Command | File Location | Classification | Description |
|---|---|---|---|
| `/check-pipeline` | `.claude/commands/check-pipeline.md` | NOC-oriented | Checks ingestion logs, rejected directory, and warehouse freshness (`dim_time`). |
| `/explain-grid` | `.claude/commands/explain-grid.md` | NOC-oriented | Gathers activity, features, anomalies, and location; outputs SEVERITY, EVIDENCE, INTERPRETATION, NEXT CHECKS. |
| `/review-anomaly` | `.claude/commands/review-anomaly.md` | NOC-oriented | Compares rule-based alerts, ML classifier output, and statistical anomaly scores for signal consensus. |
| `/test-api` | `.claude/commands/test-api.md` | Engineering-oriented | Runs the Phase 4 pytest suite and reports passes, failures, and execution time. |
| `/network-health` | `.claude/commands/network-health.md` | Engineering-oriented | Validates the canonical `(grid_id, timestamp)` grain across `hourly_grid_summary`. |

---

## 2. Task 265: Inputs and Expected Outputs

### 1. `/check-pipeline`
- **Inputs**: None
- **Backing tools/APIs**: `logs/ingestion_log.csv`, `data/rejected/`, MySQL `dim_time` and `fact_network_activity`.
- **Output Format**: Status summary (`HEALTHY`, `DEGRADED`, `UNHEALTHY`), latest warehouse timestamp, fact count, valid/invalid batches, rejected files count.
- **Example Invocation**: `/check-pipeline`

### 2. `/explain-grid`
- **Inputs**: `grid_id` (required, int), `as_of` (optional, datetime)
- **Backing tools/APIs**: `GET /network/grid/{grid_id}`, `GET /network/grid/{grid_id}/features`, `POST /network/predict-risk`, `dim_grid` coordinates.
- **Output Format**: Four structured sections:
  1. `SEVERITY`
  2. `EVIDENCE`
  3. `INTERPRETATION` (strictly preserves: proportional activity != confirmed congestion)
  4. `NEXT CHECKS`
- **Example Invocation**: `/explain-grid 4821`

### 3. `/review-anomaly`
- **Inputs**: `grid_id` (required, int), `as_of` (optional, datetime)
- **Backing tools/APIs**: `GET /network/alerts`, `POST /network/predict-risk`, `network_anomaly_scores` table.
- **Output Format**:
  1. Rule-Based Alert (Type, Severity, Reason)
  2. ML Risk Classifier (Level, Score, Version)
  3. Statistical Anomaly Score (Direction, % Deviation, Baseline vs. Current)
  4. Signal Convergence Assessment & Explanation of Disagreements
- **Example Invocation**: `/review-anomaly 4821`

### 4. `/test-api`
- **Inputs**: Optional test path (defaults to `Phase_4/tests/`)
- **Backing tools/APIs**: `python -m pytest Phase_4/tests/ -v`
- **Output Format**: Status (`PASS`/`FAIL`), command, passed count, failed count, warning count, duration.
- **Example Invocation**: `/test-api`

### 5. `/network-health`
- **Inputs**: Optional dataset path (defaults to `data/analytics/hourly_grid_summary`)
- **Backing tools/APIs**: `spark/aggregation.py` grain validation logic (`df.duplicated(subset=['grid_id', 'timestamp'])`).
- **Output Format**: Status (`PASS`/`FAIL`), target path, grain definition, records evaluated, duplicate keys count, sample violating keys if any.
- **Example Invocation**: `/network-health`

---

## 3. Task 266: Run `/test-api` After a Code Change

We made a safe code improvement to `Phase_4/services.py:get_rising_grids` to handle both aliased and raw column mappings (`current_activity` vs. `current_value`) and updated the mock in `test_hotspots_alerts.py`.

### Execution
```bash
python Phase_4/project_commands.py test-api Phase_4/tests/test_hotspots_alerts.py
```

### Result
```text
=================================================================
API TEST SUITE SUMMARY: PASS
=================================================================
- Command  : python -m pytest Phase_4/tests/test_hotspots_alerts.py -v
- Passed   : 16
- Failed   : 0
- Warnings : 0
- Duration : 132.21s
- Exit Code: 0

All executed API tests passed without regression.
```

---

## 4. Task 267: Run `/review-anomaly` for Grid 4821

### Execution
```bash
python Phase_4/project_commands.py review-anomaly 4821
```

### Result
```text
=================================================================
ANOMALY SIGNAL REVIEW FOR GRID: 4821
=================================================================

1. Rule-Based Alert:
   Status  : NO ALERT
   Type    : NONE (Severity: NONE)

2. ML Risk Classifier:
   Risk Level : LOW
   Risk Score : 0.0108
   Model Ver  : ml3_v1.0

3. Statistical Anomaly Score:
   Direction      : NORMAL
   Score (% Dev)  : -27.9%
   Current vs Base: 253.06 vs 350.75 (Delta: -97.69)

SIGNAL CONVERGENCE:
Result: AGREEMENT (NORMAL)
- All signals agree the grid is operating within standard operating bounds.
```

---

## 5. Task 268: Engineering-Oriented vs. NOC-Oriented Classification

### Engineering-Oriented Commands
- `/test-api`: Used by developers to verify API integrity and catch regression bugs during local development and CI/CD pipelines.
- `/network-health`: Used by data engineers to verify that ETL pipeline runs satisfy the relational grain constraint `(grid_id, timestamp)` without row inflation.

### NOC-Oriented Commands
- `/check-pipeline`: Used by network operations duty engineers to confirm whether incoming telemetry is fresh, whether landing ingestions failed, or if rejected files need triage.
- `/explain-grid`: Used by NOC operators investigating an active incident on a cell tower grid to obtain an immediate 4-section summary without manual SQL queries.
- `/review-anomaly`: Used by triage engineers to cross-reference static rule thresholds against probabilistic ML predictions and statistical median baselines.

---

## 6. Required Duplicate Test (`/network-health`)

### Step 1: Normal Run
```bash
python Phase_4/project_commands.py network-health
```
```text
=================================================================
NETWORK GRAIN HEALTH CHECK: PASS
=================================================================
- Evaluated Target : data\analytics\hourly_grid_summary
- Canonical Grain  : (grid_id, timestamp)
- Records Checked  : 1,679,994
- Duplicate Keys   : 0

Grain Integrity Verified: Every (grid_id, timestamp) pair is unique.
```

### Step 2: Controlled Duplicate in Isolated Test Fixture
Created `tmp/test_hourly_grid_summary/slice.parquet` containing a 10-row sample plus 1 controlled duplicate of Grid 381 at `2013-11-01 00:00:00`.
```bash
python Phase_4/project_commands.py network-health tmp/test_hourly_grid_summary
```
```text
=================================================================
NETWORK GRAIN HEALTH CHECK: FAIL
=================================================================
- Evaluated Target : tmp\test_hourly_grid_summary
- Canonical Grain  : (grid_id, timestamp)
- Records Checked  : 11
- Duplicate Keys   : 1

GRAIN VIOLATION DETECTED: Found duplicate (grid_id, timestamp) combinations:
  * Grid 381 at 2013-11-01 00:00:00
```

### Step 3: Cleanup and Re-run
Deleted `tmp/test_hourly_grid_summary`. Re-ran command on production:
```bash
python Phase_4/project_commands.py network-health
```
Result: **PASS** (1,679,994 records checked, 0 duplicates).
No raw data or production database tables were modified.

---

## 7. Files Changed / Created

| File | Status | Purpose |
|---|---|---|
| `.claude/commands/check-pipeline.md` | NEW | Slash command definition for `/check-pipeline` |
| `.claude/commands/explain-grid.md` | NEW | Slash command definition for `/explain-grid` |
| `.claude/commands/review-anomaly.md` | NEW | Slash command definition for `/review-anomaly` |
| `.claude/commands/test-api.md` | NEW | Slash command definition for `/test-api` |
| `.claude/commands/network-health.md` | NEW | Slash command definition for `/network-health` |
| `Phase_4/project_commands.py` | NEW | Reusable CLI implementation backing all five commands |
| `Phase_7/CLAUDE.md` | MODIFIED | Added Section 11 (Security Policy) and Section 12 (Project Commands) |
| `Phase_4/services.py` | MODIFIED | Made `get_rising_grids` resilient to column name mapping |
| `Phase_4/tests/test_hotspots_alerts.py` | MODIFIED | Updated mock dictionary for baseline exclusion test |
| `Phase_7/c7_walkthrough.md` | NEW | Persistent walkthrough and demonstration report |
