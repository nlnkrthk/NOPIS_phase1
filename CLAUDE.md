#c4
# NOPIS — Claude Code Project Guide

**NOPIS** is the *Network Operations Predictive Intelligence System* for the
Milan telecom network. This file is the single source of truth for Claude Code.
Read it before making any change to the project.

---

## 1. Architecture Overview

NOPIS is a five-layer system. Each layer feeds the next one.

```
data/landing/           <- raw daily CSV files arrive here
       |
       v
spark/ (PySpark ETL)    <- validates, cleans, aggregates, enriches
       |
       v
data/analytics/         <- Parquet output, then loaded to MySQL
warehouse/              <- MySQL tables: dim_grid, dim_time, fact_network_activity
       |
       v
ml/                     <- feature engineering + logistic regression scoring
Phase_4/ (FastAPI)      <- REST API reads from MySQL, runs ML inference
       |
       v
Phase_5/ (React/Vite)   <- dashboard UI calls the FastAPI endpoints
```

---

## 2. Component Map — Actual File Locations

| Component          | Path                                                                  |
|--------------------|-----------------------------------------------------------------------|
| Spark pipeline     | `spark/telecom_pipeline.py`                                           |
| Pipeline stages    | `spark/landing_ingestion.py`, `ingestion.py`, `cleaning.py`, `aggregation.py`, `enrichment.py`, `writer.py` |
| Pipeline contract  | `spark/JOB_CONTRACT.md`                                               |
| Airflow DAG        | `Phase_3/AirFlow_Practice/dags/nopis_pipeline_dag.py`                |
| FastAPI entry      | `Phase_4/main.py`                                                     |
| API routes         | `Phase_4/routers/network.py`                                          |
| API service layer  | `Phase_4/services.py`                                                 |
| Pydantic schemas   | `Phase_4/schemas.py`                                                  |
| ML feature store   | `ml/features.py`                                                      |
| ML model files     | `ml/ml3_logistic_regression.joblib`, `ml/v2_logistic_regression.joblib` |
| ML serving         | `Phase_4/ml5_model_service.py`                                        |
| Claude/LLM insight | `Phase_4/claude_insight_service.py`                                   |
| React components   | `Phase_5/src/components/` (GridActivity, NetworkSummary, HotspotsAlerts, PredictiveRisk, MapLayer) |
| React API calls    | `Phase_5/src/api/config.js`                                           |
| GeoJSON reference  | `data/milano-grid.geojson`                                            |
| MySQL schema       | `warehouse/schema.sql`                                                |
| Warehouse loader   | `warehouse/load_warehouse.py`                                         |
| Prediction contract| `docs/predict_risk_contract.md`                                       |
| Pipeline tests     | `tests/test_pipeline_91_92.py`                                        |
| API tests          | `Phase_4/tests/`                                                      |

---

## 3. Data Flow (Step by Step)

### Step 1 — Landing Ingestion
Daily CSV files land in `data/landing/`.
`process_landing()` validates each file's schema and quality.
Valid files are copied to `data/raw/`.
Invalid files go to `data/rejected/` and are logged in `logs/`.

### Step 2 — Spark ETL
Run with: `python -m spark.telecom_pipeline`

The pipeline stages run in this exact order:

```
process_landing() -> read_raw() -> clean() -> aggregate() -> enrich() -> write_outputs()
```

| Stage           | What it does                                                         |
|-----------------|----------------------------------------------------------------------|
| `read_raw`      | Reads validated CSVs from `data/raw/`                                |
| `clean`         | Renames columns, drops nulls in key fields, quarantines bad rows     |
| `aggregate`     | Groups by `(timestamp, grid_id)`, collapses country codes, computes KPIs |
| `enrich`        | Broadcast-joins with `data/milano-grid.geojson` to add geometry      |
| `write_outputs` | Writes Parquet to `data/processed/`, CSV to `data/analytics/`        |

### Step 3 — Warehouse Load
`warehouse/load_warehouse.py` loads the Parquet output into MySQL tables:
- `dim_grid` — one row per grid cell
- `dim_time` — one row per hourly timestamp
- `fact_network_activity` — one row per `(grid_id, timestamp)` pair

### Step 4 — Feature Engineering
`ml/features.py` reads from MySQL and computes the ML2 feature set per grid:
`avg_activity`, `activity_growth`, `active_hours`, `peak_ratio`, `variability`, `internet_share`.
Results are stored in the `grid_features` MySQL table.

### Step 5 — FastAPI
`Phase_4/main.py` serves the REST API on `http://127.0.0.1:8000`.
Key endpoints in `Phase_4/routers/network.py`:
- `GET /network/summary` — overall network metrics
- `GET /network/grid/{grid_id}` — time-series activity for one grid
- `GET /network/hotspots` — highest-activity grids
- `GET /network/alerts` — rule-triggered alerts
- `GET /network/grid/{grid_id}/features` — ML feature vector
- `POST /network/predict-risk` — ML risk score
- `GET /network/grid/{grid_id}/evidence` — curated evidence object
- `GET /network/grid/{grid_id}/insight` — Claude AI narrative

### Step 6 — React Dashboard
`Phase_5/src/` (Vite/React). All API calls go through `Phase_5/src/api/config.js`.
The base URL comes from `VITE_API_BASE_URL` (defaults to `http://127.0.0.1:8000`).
Main components: `GridActivity`, `NetworkSummary`, `HotspotsAlerts`, `PredictiveRisk`, `MapLayer`.

---

## 4. Canonical Data Grain

The canonical analytics grain is:

> **one grid per hourly timestamp** — after country-code aggregation.

Each row in `fact_network_activity` (and in the Spark output) represents one
Milan grid cell (`grid_id`) at one hourly slot (`timestamp`).
The `aggregate()` step collapses all country-code sub-rows into this single
grain by summing the activity measures.
The grain is validated in `aggregation.py` — any duplicate `(grid_id, timestamp)`
combination raises a `ValueError` and stops the pipeline.

---

## 5. Terminology

| Term               | Meaning in this project                                              |
|--------------------|----------------------------------------------------------------------|
| `grid_id`          | Integer ID of a Milan grid cell (1–10 000)                           |
| `timestamp`        | Hourly time slot (the grain key alongside `grid_id`)                 |
| `total_activity`   | Sum of all five activity measures for a grid at one hour             |
| `activity measure` | A proportional composite derived from call, SMS and internet events  |
| `AS_OF`            | The "now" reference point — see Rule 5 below                         |
| `risk_score`       | ML probability score in [0.0, 1.0] — HIGH activity risk, not congestion |
| `anomaly_score`    | Statistical deviation of current activity from historical baseline   |
| `direction`        | NORMAL / HIGH / LOW — output of the anomaly-detection pipeline       |
| `feature_timestamp`| The point-in-time the ML feature vector was computed for             |

---

## 6. Non-Negotiable Project Rules

### Rule 1 — High activity does not mean confirmed congestion

Never equate high activity with confirmed congestion.

```
High activity  !=  Confirmed congestion
```

High activity may be described as *elevated* or *high* activity.
Congestion must **not** be claimed without capacity or utilization evidence.
The dataset contains no capacity or utilization data — those concepts do not apply here.

Do not use the words *congestion*, *bandwidth exhaustion*, or *capacity exhaustion*
anywhere in analysis, comments, documentation, or responses about this data.

### Rule 2 — Canonical grain is one grid per hourly timestamp

The analytics grain is always:

> **one row = one grid, one hourly timestamp** (after country-code aggregation).

Never write queries, transformations, or documentation that assumes a finer grain
(e.g. per country-code sub-row) or a coarser grain (e.g. per day).

### Rule 3 — Geographic join key is `properties.cellId`

When joining `milano-grid.geojson` to activity data, always use:

```
features[].properties.cellId  ->  grid_id
```

**Never** use the 0-based `featureid` field as the join key.
The enrichment step in `spark/enrichment.py` correctly uses `properties.cellId`.

### Rule 4 — Activity values are proportional measures, not raw counts or MB

The values in `sms_in`, `sms_out`, `call_in`, `call_out`, `internet_activity`,
and `total_activity` are **proportional activity measures**.

They are **not**:
- call counts
- SMS counts
- megabytes (MB)
- data volume figures

Do not convert or label them as any of those units.

### Rule 5 — AS_OF defines "now"

The `as_of` parameter is the project's convention for "what the system knows
up to this point in time." It appears on every summary and time-series endpoint.
Whenever discussing the "current" or "latest" network state, respect the `as_of`
boundary — never silently extend it to a later timestamp.

### Rule 6 — Analytics grain is after country-code aggregation

The `aggregate()` step in `spark/aggregation.py` collapses country-code rows
by summing all five activity measures per `(timestamp, grid_id)` group.
The output grain — **one grid per hourly timestamp after country-code aggregation** —
is the only grain used by the warehouse, the API, the ML model, and the dashboard.
Keep this terminology consistent throughout all code and documentation.

---

## 7. Important Constraints for Future Changes

- **Pipeline order is fixed.** Always: `process_landing -> read_raw -> clean -> aggregate -> enrich -> write_outputs`. Do not reorder, skip, or merge stages.
- **Failure must be atomic.** On any pipeline failure, do not leave partial outputs in `data/processed/` or `data/analytics/`. The pipeline exits with code 1 on any unhandled error.
- **API contract stability.** The Pydantic schemas in `Phase_4/schemas.py` are consumed by the React frontend, the ML scoring service, and Claude tools. Any field removal or type change is a **breaking change** — add fields only, never remove or rename.
- **Frontend API calls belong in `config.js`.** All `fetch()` calls live in `Phase_5/src/api/config.js`. Never add inline API calls directly inside React components.
- **MySQL required at API startup.** `Phase_4/main.py` loads the ML model at startup. A missing MySQL connection or missing `ml/` artifacts will prevent the server from starting.
- **Windows Spark paths.** The Spark session uses `winutils` and Windows-style temp directories. See `spark/spark_session.py` before changing runtime paths.
- **Do not mix output paths.** The unified pipeline writes to `data/processed/` and `data/analytics/`. The legacy Phase 2 scripts wrote to `spark/output/`. Do not mix them.
- **Contracts are canonical.** `spark/JOB_CONTRACT.md` and `docs/predict_risk_contract.md` are the canonical interface definitions. Update implementation and tests together when a contract changes.

---

## 8. How to Run the Project

### Run the Spark pipeline
```powershell
python -m spark.telecom_pipeline
```

### Run the FastAPI server
```powershell
cd Phase_4
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

### Run the React dashboard
```powershell
cd Phase_5
npm run dev
```

### Run the pipeline tests
```powershell
python -m pytest tests/test_pipeline_91_92.py -v
```

### Run the API tests
```powershell
python -m pytest Phase_4/tests/ -v
```

---

## 9. Proposed Missing Tests

The following tests do not currently exist and would improve coverage:

| Test area | What to test |
|-----------|-------------|
| Spark cleaning | Quarantine of rows with null `grid_id`, null `timestamp`, or negative activity values |
| Spark aggregation grain | Confirm no duplicate `(grid_id, timestamp)` after `aggregate()` |
| Spark enrichment | Confirm `properties.cellId` is used (not `featureid`); no row inflation after join |
| Spark writer | Output files appear in `data/processed/` only on success, not on failure |
| ML features | `compute_and_store_features()` produces the expected 6 feature columns per grid |
| ML scoring | `predict()` returns a float in [0.0, 1.0] for a valid feature vector |
| API — `GET /network/summary` | Returns 404 when no data exists; returns 500 on DB error |
| API — `GET /network/grid/{grid_id}` | Returns 404 for grid outside 1–10 000 |
| API — `GET /network/grid/{grid_id}/features` | `feature_timestamp` matches AS_OF boundary |
| API — `POST /network/predict-risk` | `risk_score` is in [0.0, 1.0]; `risk_level` is one of LOW/MEDIUM/HIGH/CRITICAL |
| API — evidence endpoint | Evidence object contains only fields from the `grid_features JOIN network_anomaly_scores` query |
| Geography join | Integration test: after pipeline run, every active `grid_id` in analytics has non-null geometry |
| Data quality | Pipeline produces zero output rows only when input is genuinely empty |

---

## 10. Proposed Missing Documentation

| Document | What to include |
|----------|----------------|
| Architecture diagram | Visual diagram of the six-layer data flow |
| Data dictionary | Column-by-column description of `fact_network_activity`, `dim_grid`, `dim_time`, `grid_features` |
| API supplement | Human-readable guide to query parameters, `as_of` semantics, and error codes (OpenAPI spec at `/docs` covers the schema) |
| Setup / run guide | Step-by-step: install dependencies -> place CSVs -> run pipeline -> start API -> start dashboard |
| ML model card | What the logistic regression predicts, the feature set, training period, known limitations |
| Pipeline runbook | What to do when the pipeline fails at each stage (landing, cleaning, aggregation, enrichment) |
| Airflow setup guide | How to register and trigger `nopis_pipeline_dag` in a local Airflow instance |

---

## 11. Security & Permission Policy (ALLOW / ASK / DENY)

This repository enforces a strict three-tier permission model for Claude Code operations to protect system integrity, guarantee data immutability, and prevent unintended operational disruptions.

### ALLOW (Safe Operations — Automatically Permitted)
- **Safe Source Reads**: Reading code, schemas, SQL queries, tests, and documentation files across all repository directories.
- **Raw Data Reads**: Inspecting raw data under `data/raw/` or `data/milano-grid.geojson` for schema verification or testing.
- **Automated Test Execution**: Running test suites (`python -m pytest ...`).
- **Formatting and Linting**: Running linters or code formatting tools without altering business logic.

### ASK (Human Approval Required Before Action)
- **Dependency Changes**: Adding, removing, or modifying packages in `requirements.txt` or `Phase_5/package.json`.
- **Database Migrations & DDL Edits**: Altering `warehouse/schema.sql` or table structures.
- **Airflow DAG Modifications**: Modifying pipeline DAG definitions under `Phase_3/AirFlow_Practice/dags/`.
- **Pipeline & Session Configuration**: Modifying `spark/spark_session.py`, `spark/JOB_CONTRACT.md`, `spark/telecom_pipeline.py`, or database configurations.
- **API Schema Modifications**: Altering response models in `Phase_4/schemas.py` or canonical API contracts.

### DENY (Strictly Prohibited — Always Blocked)
- **Raw Data Deletion or Modification**: `data/raw/` is immutable. Deleting or writing files under `data/raw/` is strictly forbidden.
- **Data Directory Deletion**: Deleting files or folders under `data/`.
- **Secrets Access**: Reading `.env`, printing, or exposing passwords, API keys, or connection credentials.
- **Destructive Database Operations**: Executing `DROP TABLE`, `DROP DATABASE`, `TRUNCATE TABLE`, or bulk unconditional `DELETE` statements.

---

## 12. Reusable Project Slash Commands

Commands stored in `.claude/commands/` backed by `Phase_4/project_commands.py`:

| Command | Category | Purpose | Example |
|---|---|---|---|
| `/check-pipeline` | NOC | Verify ingestion logs, rejected files, and warehouse freshness | `/check-pipeline` |
| `/explain-grid` | NOC | 4-section incident report (SEVERITY, EVIDENCE, INTERPRETATION, NEXT CHECKS) | `/explain-grid 4821` |
| `/review-anomaly` | NOC | Compare rule alert, ML classifier, and anomaly scores for signal consensus | `/review-anomaly 4821` |
| `/test-api` | Engineering | Execute API test suite and summarize passes/failures | `/test-api` |
| `/network-health` | Engineering | Validate (grid_id, timestamp) canonical grain on hourly_grid_summary | `/network-health` |

---

## 13. Reusable Claude Skills

Skills stored under `.claude/skills/<skill_name>/SKILL.md`:

| Skill | Category | Trigger / Purpose | Required Evidence |
|---|---|---|---|
| `network-anomaly-analysis` | NOC | Grid anomaly diagnosis, alert triage, surge explanation | Current activity, baseline, anomaly score, direction, rule alert, ML risk, pipeline freshness |
| `pipeline-troubleshooting` | NOC / DE | PySpark ETL crashes, rejected rows, stale data triage | Ingestion log (`ingestion_log.csv`), `data/rejected/`, `dim_time` freshness, stage exit codes |
| `telecom-data-quality` | Engineering | Grain audit, duplicate detection, GeoJSON join validation | Grain check (`(grid_id, timestamp)` 0 dupes), quarantine counts, `properties.cellId` join key |


---

## 14. C10 — Hooks & Event-Driven Workflows

Project hooks are configured in `.claude/hooks.json`. They run automatically during Claude Code sessions.

### Hook files

| File | Purpose |
|---|---|
| `.claude/hooks.json` | Hook event registration |
| `.claude/hooks/run_post_edit_checks.py` | Post-edit runner for `spark/` and `ml/` Python files |
| `.claude/hooks/run_pre_action_check.py` | Pre-action gate for sensitive pipeline configuration |
| `Phase_4/tests/test_c10_ml2_leakage.py` | ML2 feature-leakage tests (standalone, no MySQL) |
| `logs/hook_log.csv` | Hook outcome log (appended, never overwritten) |

### Post-edit hook — `spark/` and `ml/` Python files

After any Python file under `spark/` or `ml/` is edited, the hook automatically runs:

1. **Grain/duplicate check** — `pytest test_pipeline_91_92.py -k TestSparkFailurePath`
2. **ML2 leakage test** — `pytest Phase_4/tests/test_c10_ml2_leakage.py`

Exit 0 = PASS. Exit 2 = FAIL (Claude Code will surface the failure).

### Pre-action gate — sensitive pipeline files

Before any edit to the files below, the hook exits code 2 (BLOCKED) and requires
explicit human confirmation:

- `Phase_3/AirFlow_Practice/dags/` (all Airflow DAGs)
- `spark/spark_session.py`, `spark/JOB_CONTRACT.md`, `spark/telecom_pipeline.py`
- `warehouse/schema.sql`, `Phase_4/schemas.py`

This enforces the C6 ASK-tier policy (§11 above) and does not bypass it.

### Log

Every hook execution appends one row to `logs/hook_log.csv`:

```
datetime,hook_name,trigger_file,checks_performed,result,details
```

`result` is one of: `PASS`, `FAIL`, `BLOCKED`.

---

## 15. C11 — Checkpoints & Safe Rollback

Safe experimentation with anomaly and risk rules follows strict rollback and checkpoint rules:

### Rules for Rule Experiments
1. **Never change multiple independent rules at once**: Modify strictly one threshold or rule parameter per experiment.
2. **Never change the ML model or feature engineering during a threshold experiment**: Hold model artifacts and feature vector calculations constant.
3. **Never touch `data/raw/`**: Raw landing telemetry remains strictly immutable.
4. **Never execute destructive database operations**: Do not truncate or modify production warehouse tables for transient rule testing.
5. **Always create a checkpoint before making changes**: Tag a commit or stash object (e.g. `c11-checkpoint-pre-experiment`) to preserve pre-experiment state.
6. **Quantify operational impact before and after**:
   - Compare alert volume (active window count and percentage change).
   - Compare top-20 attention list composition (grids that stayed, entered, or left).
   - Compare agreement rate with NP3 heuristic rules ($\frac{\text{Both Active} + \text{Both Normal}}{\text{Total Grids}}$).
7. **Separate EVIDENCE from INTERPRETATION**: State measured metrics strictly as facts; label operational impact inferences clearly.
8. **Learner owns the judgment**: The assistant recommends KEEP or ROLLBACK, but the human operator makes the final decision.
9. **Verify rollback restoration**: Confirm code diff is 0 bytes, alert volume returns to baseline, and relevant test suites pass 100%.
