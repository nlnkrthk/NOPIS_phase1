# NOPIS Project Documentation

**Network Operations Predictive Intelligence System**  
Milan telecom network activity analytics, anomaly detection, machine-learning risk scoring, API serving, dashboard visualization, and Claude-assisted investigation.

> This document describes the repository as implemented. It distinguishes the current unified runtime from historical, educational, experimental, and operational-support phases. Where implementation and documentation differ, the current code behavior is stated and the discrepancy is called out.

## 1. System Purpose

NOPIS processes hourly telecom activity data for Milan grid cells. It validates daily CSV files, cleans and aggregates activity to a canonical grid-hour grain, enriches records with Milan grid geometry, stores analytical data in Parquet and MySQL, computes machine-learning features and anomaly scores, exposes those results through FastAPI, and presents them through a React dashboard.

The system also provides evidence-grounded operational investigation tools. Claude/LLM components consume curated evidence from the API and produce structured narratives. They are an interpretation layer; they do not replace the deterministic pipeline, warehouse queries, anomaly rules, or ML model.

### Important terminology

- **Grid**: A Milan geographic cell identified by `grid_id`.
- **Timestamp**: An hourly time slot.
- **Canonical grain**: One row per `(grid_id, timestamp)` after country-code aggregation.
- **Activity measure**: A proportional activity value derived from call, SMS, and internet signals. These values are not call counts, SMS counts, megabytes, or physical data volumes.
- **High activity**: Elevated measured activity. It is not proof of congestion, bandwidth exhaustion, or capacity exhaustion. The repository does not contain capacity or utilization evidence.
- **`as_of`**: The point-in-time boundary defining what the system knows for a query.
- **Risk score**: A model probability associated with high-activity risk. It is not a confirmed service-failure or capacity diagnosis.

## 2. Repository Map

### Root files

| Path | Purpose |
|---|---|
| `AGENTS.md` | Active agent and repository operating guide, canonical commands, contracts, terminology, and safety rules. |
| `CLAUDE.md` | Detailed architecture, data-flow, phase map, operational rules, commands, skills, hooks, and checkpoint guidance. |
| `requirements.txt` | Python dependencies for the pipeline, API, ML, and supporting tooling. |
| `pyrightconfig.json` | Python/Pylance type-checking configuration. |
| `test_pipeline_91_92.py` | Root pipeline and failure-path tests. |
| `airflow_run.txt` | Airflow execution notes/output. |
| `docs/` | Stable project contracts, currently including the prediction API contract. |
| `logs/` | Operational ingestion and hook logs. |

### Primary runtime folders

| Folder | Role |
|---|---|
| `data/` | Landing, raw, rejected, processed, analytics, reference, source CSV, and GeoJSON data zones. |
| `spark/` | Current PySpark ETL pipeline, session setup, anomaly scoring, and output writing. |
| `warehouse/` | MySQL DDL, Parquet-to-MySQL loading, and analytical SQL. |
| `ml/` | Feature-store computation and serialized logistic-regression model artifacts. |
| `Phase_4/` | Current FastAPI application, database access, schemas, service logic, and model serving. |
| `Phase_5/` | Current React/Vite operator dashboard. |
| `Phase_7/` | Claude/LLM integrations, investigation agents, orchestration, MCP work, reports, and tests. |

### Historical, educational, and design folders

| Folder | Role |
|---|---|
| `Phase_1/` | Earlier pandas-based processing implementation, documentation, tests, and outputs. |
| `Phase_2/` | Educational Spark stages and notebooks demonstrating ingestion, cleaning, aggregation, geospatial processing, performance, and ETL. |
| `Phase_3/` | Data-engineering architecture, storage strategy, batch/streaming discussion, and Airflow practice. |
| `Phase_6/` | Machine-learning development notebooks covering model and feature-engineering stages. |
| `.claude/` | Active Claude project configuration, skills, commands, hooks, and MCP server. |
| `plugins/` | Packaged `network-engineering` Claude plugin containing reusable commands, skills, hooks, rules, and MCP documentation. |
| `tmp/` and Spark temporary directories | Runtime temporary files. They are not analytical source data or authoritative outputs. |

## 3. Authoritative Runtime Versus Project History

The current executable pipeline is:

```text
python -m spark.telecom_pipeline
```

The current conceptual order is:

```text
process_landing()
  -> read_raw()
  -> clean()
  -> aggregate()
  -> enrich()
  -> write_outputs()
  -> warehouse load
  -> ML feature/anomaly jobs
  -> FastAPI
  -> React dashboard and investigation tools
```

`Phase_1` and `Phase_2` explain earlier implementation approaches and learning stages. They are not interchangeable with the unified pipeline. In particular, older scripts may use hard-coded paths, different output locations, or raw field names.

`Phase_3` explains architecture and orchestration concepts. Its Airflow DAG is practice/orchestration code and should not be confused with the direct package entry point.

`Phase_6` contains notebook-based ML development. The deployed API uses serialized artifacts under `ml/`, not notebook execution at request time.

`Phase_7` contains operational intelligence and AI tooling built around the API and evidence model. It is not a replacement for Spark or the warehouse.

## 4. End-to-End Data Flow

### 4.1 Source and landing zones

Daily source files follow the naming pattern:

```text
sms-call-internet-mi-YYYY-MM-DD.csv
```

The intended ingestion zone is `data/landing/`. The repository also contains source CSVs at the `data/` root; their presence is useful for inspection but does not change the documented landing contract.

`process_landing()` discovers candidate files, validates their structure and values, and moves or copies accepted files into `data/raw/`. Invalid files go to `data/rejected/`. Each file is recorded in `logs/ingestion_log.csv` with the validation outcome.

Raw input is treated as immutable after acceptance. Pipeline logic should never rewrite or delete files in `data/raw/`.

### 4.2 Spark session

The current Spark setup is Windows-oriented. `spark/spark_session.py` configures local Spark, Windows Hadoop/winutils settings, temporary directories, and timezone behavior. The session uses UTC-oriented timestamp handling so that hourly grouping is stable.

### 4.3 Reading raw data

`spark/ingestion.py` reads accepted CSV files using an explicit schema rather than relying on uncontrolled inference. It adds the input filename for lineage and diagnostics.

Raw fields:

| Raw field | Meaning | Type/handling |
|---|---|---|
| `datetime` | Activity timestamp | Timestamp; required. |
| `CellID` | Milan grid identifier | Integer; required. |
| `countrycode` | Country grouping dimension | Integer; nullable. |
| `smsin` | Incoming SMS activity | Numeric; nullable. |
| `smsout` | Outgoing SMS activity | Numeric; nullable. |
| `callin` | Incoming call activity | Numeric; nullable. |
| `callout` | Outgoing call activity | Numeric; nullable. |
| `internet` | Internet activity | Numeric; nullable. |

The five activity measures are proportional values supplied by the source dataset. They are not physical units.

### 4.4 Cleaning and preprocessing

`spark/cleaning.py` standardizes names and applies row-level quality rules.

| Raw name | Canonical name |
|---|---|
| `datetime` | `timestamp` |
| `CellID` | `grid_id` |
| `countrycode` | `country_code` |
| `smsin` | `sms_in` |
| `smsout` | `sms_out` |
| `callin` | `call_in` |
| `callout` | `call_out` |
| `internet` | `internet_activity` |

Cleaning behavior:

1. Casts timestamps, grid identifiers, and activity columns to the expected types.
2. Rejects or quarantines rows with missing key fields such as `grid_id` or `timestamp`.
3. Rejects or quarantines rows with negative activity values.
4. Retains missing activity measures as zero-valued measures where the contract permits this.
5. Derives date and time attributes used by later aggregation, partitioning, and analysis.
6. Computes preliminary KPI columns before aggregation; aggregation recomputes them at the canonical grain.

Derived fields include:

- `date`
- `hour`
- `day_of_week`
- `total_sms = sms_in + sms_out`
- `total_calls = call_in + call_out`
- `total_activity = total_sms + total_calls + internet_activity`
- `internet_share`, representing the internet component's share of total activity where defined

Invalid-row handling is separate from invalid-file handling. A file can be accepted into the raw zone while individual bad rows are quarantined during cleaning.

### 4.5 Aggregation

`spark/aggregation.py` collapses country-code subrows by `(timestamp, grid_id)`. All five activity measures are summed, and aggregate KPIs are recomputed.

The resulting grain is:

> One grid cell at one hourly timestamp, after country-code aggregation.

The aggregation stage checks for duplicate `(grid_id, timestamp)` keys. A duplicate at the published grain is a data-quality failure and stops the pipeline. It also checks that aggregation performs the expected reduction when input contains multiple country-code rows.

### 4.6 Geospatial enrichment

`spark/enrichment.py` reads `data/milano-grid.geojson` and performs a left join using:

```text
features[].properties.cellId -> grid_id
```

The `featureid` property is not the analytical join key. Geometry and related geographic attributes are attached to the enriched output. A missing geometry is logged; current implementation does not always fail publication for missing geometry, so downstream completeness should be checked separately.

### 4.7 Output writing

`spark/writer.py` publishes two principal analytical representations:

| Output | Contents |
|---|---|
| `data/processed/enriched_hourly_grid/` | Enriched Parquet including geometry, partitioned by `date`. |
| `data/analytics/hourly_grid_summary/` | Analytical Parquet without geometry, intended for warehouse loading and queries. |
| `data/analytics/summary_csv/` | Coalesced CSV summary for convenient inspection or exchange. |

Incremental runs use append-oriented behavior. Initial/non-incremental operation can overwrite the target. Publication should remain atomic: a failed run must not leave a misleading partial processed or analytics result.

There is a historical output convention under `spark/output` in older contracts or scripts. The current unified pipeline uses `data/processed` and `data/analytics`; these locations must not be mixed without an explicit migration decision.

### 4.8 Warehouse and analytical jobs

The warehouse loader reads the analytical Parquet snapshot and populates MySQL dimensions and facts. The feature job in `ml/features.py` computes six per-grid features. `spark/anomaly_scoring.py` computes hour-of-day baselines and anomaly scores. These are separate analytical jobs after the core ETL publication.

### 4.9 API and dashboard

FastAPI queries MySQL and serves JSON. React calls FastAPI through `Phase_5/src/api/config.js`. The browser does not connect directly to MySQL. Claude/MCP tools also use the API for their normal read-only path.

## 5. Storage Model

### 5.1 File storage zones

| Zone | Purpose | Expected contents |
|---|---|---|
| `data/landing/` | Incoming drop zone | Unvalidated daily source files. |
| `data/raw/` | Accepted immutable inputs | Files that passed landing validation. |
| `data/rejected/` | Rejected inputs | Invalid files and rejection evidence. |
| `data/processed/` | Enriched pipeline output | Partitioned Parquet with geometry. |
| `data/analytics/` | Curated analytical output | Summary Parquet and CSV. |
| `data/reference/` | Static lookup/reference area | Reference assets where used. |
| `data/milano-grid.geojson` | Geographic reference | Milan grid polygons keyed by `properties.cellId`. |
| `logs/` | Operational evidence | Ingestion and hook logs. |

### 5.2 Warehouse tables

The core DDL is in `warehouse/schema.sql`. The relationship is:

```text
dim_grid 1 --- * fact_network_activity * --- 1 dim_time
```

#### `dim_grid`

One row per Milan grid cell.

| Column/role | Description |
|---|---|
| `grid_id` | Primary key and canonical grid identifier. |
| `centroid_lon` | Grid centroid longitude. |
| `centroid_lat` | Grid centroid latitude. |
| `geometry` | Stored polygon/geospatial representation. |

Rows are loaded from GeoJSON using `properties.cellId`.

#### `dim_time`

One row per analytical timestamp.

| Column/role | Description |
|---|---|
| `time_key` | Primary key formatted as `YYYYMMDDHH`. |
| `timestamp` | Hourly timestamp. |
| `date` | Calendar date. |
| `hour` | Hour-of-day. |
| `day` | Day component. |
| `month` | Month component. |
| `year` | Year component. |

#### `fact_network_activity`

The central activity fact table. Its primary key is `(grid_id, time_key)`, enforcing the grid-hour grain through foreign keys to `dim_grid` and `dim_time`.

Measures:

- `sms_in`
- `sms_out`
- `call_in`
- `call_out`
- `internet_activity`
- `total_sms`
- `total_calls`
- `total_activity`
- `internet_share`

This table is the primary source for summary metrics, grid time series, hotspots, alerts, and feature recomputation.

#### `grid_features`

Created/populated by `ml/features.py`. It stores the feature vector used by risk prediction:

- `grid_id`
- `feature_timestamp`
- `avg_activity`
- `activity_growth`
- `active_hours`
- `peak_ratio`
- `variability`
- `internet_share`
- `data_quality_status`
- `created_at`

The feature calculation uses up to the trailing 24 observations per grid. The API can read stored features or recompute a point-in-time vector when `as_of` is supplied.

#### `network_anomaly_scores`

Created dynamically by the anomaly-scoring job rather than being fully declared in the core warehouse DDL.

- `grid_id`
- `feature_timestamp`
- `current_value`
- `baseline_value`
- `deviation`
- `anomaly_score`
- `direction`
- `anomaly_flag`
- `reason`

The current baseline is the median activity for a grid and hour-of-day. The implementation uses approximately `+50%` deviation for `HIGH` and `-50%` deviation for `LOW`; otherwise the direction is normal.

### 5.3 Storage caveats

- The main project is Windows-oriented, but parts of the warehouse loader use `/mnt/d/...` paths associated with WSL/Linux environments.
- Several modules use hard-coded database URLs while anomaly scoring can honor `NOPIS_DATABASE_URL`.
- `network_anomaly_scores` is dynamically created/populated, so deployment must run the relevant setup before anomaly endpoints are used.
- The repository includes temporary folders with encoded-looking Windows path names. They are runtime artifacts, not authoritative data zones.

## 6. Machine Learning

### 6.1 Feature generation

`ml/features.py` reads warehouse activity and computes a vector per grid using recent activity history. The six canonical features are:

1. `avg_activity`: Mean activity over the selected recent window.
2. `activity_growth`: Change relative to the comparison activity window.
3. `active_hours`: Number of active observations/hours in the window.
4. `peak_ratio`: Peak activity relative to the selected average or baseline.
5. `variability`: Variation of activity over the window.
6. `internet_share`: Internet activity proportion.

Feature rows include a `feature_timestamp`, quality status, and creation time so consumers can assess freshness.

### 6.2 Model artifacts

The serialized artifacts are stored in `ml/`:

- `ml3_logistic_regression.joblib`, metadata `ml3_model_metadata.json`, exposed as `ml3_v1.0`.
- `v2_logistic_regression.joblib`, metadata `ml3_v2_model_metadata.json`, exposed as `ml3_v2.0`.

`Phase_4/ml5_model_service.py` loads the default model during API startup. The prediction API constructs the six-feature vector, invokes the selected model, and returns a probability.

Risk-level mapping:

| Score | Level |
|---|---|
| `< 0.25` | `LOW` |
| `0.25` to `< 0.50` | `MEDIUM` |
| `0.50` to `< 0.75` | `HIGH` |
| `>= 0.75` | `CRITICAL` |

### 6.3 ML caveats

The v2 metadata names its internet feature `internet_share_avg`, while the API currently constructs the vector using `internet_share`. The API does not fully adapt feature names by model version, so v2 compatibility should be verified before relying on it.

The model predicts a risk score based on the available activity-derived feature vector. It does not prove congestion or capacity exhaustion.

## 7. FastAPI Application

### 7.1 Application structure

| File | Responsibility |
|---|---|
| `Phase_4/main.py` | Creates the FastAPI application, startup lifespan, model loading, and router registration. |
| `Phase_4/routers/network.py` | Defines HTTP routes and translates service results/errors to HTTP responses. |
| `Phase_4/services.py` | Contains SQLAlchemy `text()` queries, aggregation logic, feature resolution, prediction orchestration, and evidence assembly. |
| `Phase_4/schemas.py` | Pydantic request/response contracts and validation constraints. |
| `Phase_4/database.py` | SQLAlchemy engine/session configuration and database connection settings. |
| `Phase_4/ml5_model_service.py` | Loads model artifacts and performs inference. |
| `docs/predict_risk_contract.md` | Canonical prediction endpoint contract. |

Routes generally create a SQLAlchemy session, call a service, map failures to an HTTP response, and close the session. `get_db()` exists, but the current routes commonly manage sessions directly rather than using FastAPI dependency injection.

The database engine uses a connection timeout, `pool_pre_ping`, and pool recycling. Database failures are intended to fail promptly rather than hang requests.

### 7.2 Endpoint reference

#### `GET /`

Returns a service-running message and a link to the OpenAPI documentation at `/docs`.

#### `GET /network/summary`

Returns network-level metrics for an inclusive time range.

Inputs:

- `from_dt`, optional start datetime.
- `to_dt`, optional end datetime.
- `as_of`, optional knowledge boundary.

The service resolves omitted bounds from warehouse data. `as_of` represents the latest permitted timestamp and is mutually exclusive with explicit range parameters in the intended contract.

Response fields include:

- `total_activity`
- `active_grids`
- `peak_hour`
- `top_grid`
- Effective `from_dt`
- Effective `to_dt`

#### `GET /network/grid/{grid_id}`

Returns hourly activity for one grid.

Inputs:

- `grid_id`, expected range `1..10000`.
- Optional `date` and `hour` filters.
- Optional `as_of`.
- Optional inclusive `from_dt` and `to_dt`.

Default behavior returns the latest 24 rows. `as_of` is rounded down to the hour and limits records to timestamps at or before that boundary. Results include component measures, totals, and `internet_share`.

#### `GET /network/hotspots`

Ranks grids at the selected latest/as-of timestamp by `total_activity`.

Inputs:

- `limit`, constrained to `1..500`.
- Optional `severity`.
- Optional `as_of`.

Severity thresholds are currently:

- `CRITICAL`: `total_activity >= 2000`
- `HIGH`: `1000..1999`
- `MEDIUM`: `500..999`
- `LOW`: `< 500`

The endpoint reports activity severity. It does not invoke the ML model and does not establish capacity conditions.

#### `GET /network/alerts`

Returns rule-based activity alerts for a selected timestamp.

Inputs include `limit`, optional `severity`, and optional `as_of`. The service first considers rows with `total_activity >= 300`, then applies rules such as:

- `HIGH_ACTIVITY`
- `INTERNET_SURGE`
- `ACTIVITY_SPIKE`
- `ELEVATED_ACTIVITY`

Hotspot and alert responses may include ML-related fields as `null`; these endpoints do not calculate model predictions.

#### `GET /network/rising-grids`

Reads `network_anomaly_scores` and ranks grids by anomaly evidence.

Inputs:

- `limit`, generally `1..500`.
- Optional `as_of`.
- `direction`, default `HIGH`.

Returns current value, baseline, deviation, percentage deviation, direction, and anomaly score. It does not recompute the anomaly score during the request.

#### `GET /network/grid/{grid_id}/features`

Returns the six-feature vector and freshness metadata.

Without `as_of`, the service reads stored `grid_features`. With `as_of`, it recomputes from the latest qualifying 24 rows through the rounded hour.

Response fields include:

- `grid_id`
- `feature_timestamp`
- Six feature values
- `data_quality_status`
- `freshness_hours`
- `is_fresh`

#### `POST /network/predict-risk`

Accepts a `PredictRiskRequest` containing `grid_id`, with optional `model_version`, `as_of`, and feature overrides.

Processing sequence:

1. Validate the grid identifier and confirm the grid exists.
2. Resolve features from an as-of activity window or stored `grid_features`.
3. Apply any supplied feature overrides.
4. Reject the request if a required feature remains unavailable.
5. Run the selected serialized logistic-regression model.
6. Convert the probability to a risk level.
7. Add anomaly context and a model-feature explanation note.

Response fields include `grid_id`, `risk_score`, `risk_level`, `model_version`, `prediction_timestamp`, `explanation_note`, and `is_stub: false`.

#### `GET /network/models`

Returns available model versions, model types, and expected feature names.

#### `GET /network/grid/{grid_id}/evidence`

Returns a curated evidence object assembled from `grid_features` and `network_anomaly_scores`. This is the structured input used by the insight path.

#### `GET /network/grid/{grid_id}/insight`

Retrieves evidence and sends it to the active LLM provider. Returns the evidence, generated narrative, and model/provider name. The LLM is expected to preserve the distinction between evidence and interpretation.

#### `GET /network/pipeline/status`

Delegates to the project pipeline-status command and reports ingestion-log status, rejected files, and warehouse freshness. This route is coupled to the Phase 7 command implementation rather than being a pure database-health route.

### 7.3 Validation and error behavior

- FastAPI/Pydantic validation errors generally return `422`.
- Database failures are commonly translated to `500` with a database-unavailable detail.
- Missing data or unknown grids commonly produce `404`.
- Missing prediction features and unknown model versions produce `422`.
- Missing Claude configuration produces `503`; provider request failures produce `502`.
- Explicit grid activity/features/prediction routes validate the normal `1..10000` range.

Known behavior gaps:

- Some invalid combinations of `as_of`, explicit ranges, or partial bounds return empty/`404` behavior rather than a clean `422` validation response.
- Stored feature lookup uses `LIMIT 1` without ordering in one path, so the selected row can be nondeterministic if multiple rows exist.
- Some anomaly explanation lookups are not fully constrained by the prediction request's `as_of` boundary.
- Freshness for stored features is measured against wall-clock time; live as-of features report a simplified freshness value.
- There is no implemented `/network/grid/{grid_id}/location` or nearby-hotspots route, although some older tools refer to them.

## 8. React Frontend

### 8.1 Application structure

The dashboard is a Vite/React application under `Phase_5/`.

| File/folder | Role |
|---|---|
| `src/main.jsx` | Browser entry point. |
| `src/App.jsx` | Top-level view state and navigation composition. |
| `src/api/config.js` | Central API base URL and fetch helpers. |
| `src/components/Navbar.jsx` | View navigation. |
| `src/components/NetworkSummary.jsx` | Network-level summary view. |
| `src/components/GridActivity.jsx` | Grid time-series view. |
| `src/components/HotspotsAlerts.jsx` | Hotspot, alert, and rising-grid view. |
| `src/components/MapLayer.jsx` | Leaflet/GeoJSON map layer. |
| `src/components/PredictiveRisk.jsx` | Feature, prediction, and AI insight view. |
| `src/index.css` | Application styling. |
| `public/milano-grid.geojson` | Static browser-side grid geometry. |
| `package.json` | Vite scripts and React/Leaflet dependencies. |

The API base URL comes from `VITE_API_BASE_URL`, defaulting to `http://127.0.0.1:8000`. All normal backend calls belong in `src/api/config.js`; components consume those helpers rather than opening database connections.

### 8.2 Network Summary

`NetworkSummary.jsx` calls `/network/summary` and supports overall, explicit date-range, and as-of modes. It displays:

- Total activity
- Active grid count
- Peak hour
- Top grid
- Loading and API error states

### 8.3 Grid Activity

`GridActivity.jsx` calls `/network/grid/{grid_id}`. Users can select a grid and apply date, hour, range, or as-of filters. The view displays activity over time, including total, internet, call, and SMS series, using chart/table presentation and grid-not-found or connection-error states.

### 8.4 Hotspots and Alerts

`HotspotsAlerts.jsx` calls:

- `/network/hotspots`
- `/network/alerts`
- `/network/rising-grids`

It supports severity and result-limit filters and displays ranked operational rows. It also loads the static GeoJSON once from the public assets.

### 8.5 MapLayer

`MapLayer.jsx` uses React Leaflet and OpenStreetMap tiles. It renders Milan grid polygons with Canvas rendering, joins activity rows to polygons using `feature.properties.cellId`, and styles polygons by severity. Selecting a polygon navigates to the corresponding Grid Activity view.

The browser map uses static geometry for rendering, while activity and severity information comes from FastAPI. This keeps geographic display assets separate from warehouse access.

### 8.6 Predictive Risk

`PredictiveRisk.jsx`:

1. Loads `/network/models`.
2. Loads `/network/grid/{grid_id}/features`.
3. Sends the selected feature values to `/network/predict-risk`.
4. Displays probability, risk level, model version, inputs, and explanation.
5. Calls `/network/grid/{grid_id}/insight` for the AI narrative.
6. Parses the expected structured sections: `SEVERITY`, `EVIDENCE`, `INTERPRETATION`, and `NEXTCHECKS`.

The frontend therefore connects to warehouse-derived information indirectly:

```text
React component -> config.js fetch -> FastAPI route -> service SQL -> MySQL warehouse
```

There is no direct React-to-MySQL connection.

### 8.7 Frontend execution

From `Phase_5/`:

```powershell
npm run build
npm run dev
npm run preview
```

The project currently defines no dedicated frontend test or lint script.

## 9. Claude, LLM, MCP, and Agent Tooling

### 9.1 Evidence-grounded insight

The implemented insight service is under `Phase_7/c_tasks/claude_insight_service.py`. Some older project references describe a Phase 4 Claude service, but the actual current implementation is in Phase 7.

Provider behavior:

- Primary provider: Anthropic.
- Fallback/provider option: NVIDIA NIM through an OpenAI-compatible client.
- Provider selection is configuration-driven.
- API keys are read from environment variables and should never be committed or printed.
- The service receives one curated evidence object rather than unrestricted warehouse data.

The expected output has four sections:

```text
SEVERITY
EVIDENCE
INTERPRETATION
NEXTCHECKS
```

The prompt requires the model to avoid inventing missing evidence, preserve source facts, and label interpretation as interpretation. `Phase_7/c_tasks/test_insufficient_evidence.py` tests the behavior where a required field such as `anomaly_score` is missing.

### 9.2 Investigation workflow

`Phase_7/investigate_grid.py` is a headless investigation agent. It gathers pipeline status first, then calls API-backed tools for activity, features, location/evidence where available, and related operational context. It produces structured severity, evidence, uncertainty, and recommended-check sections and can optionally request an Anthropic narrative.

`Phase_7/c_tasks/c3_incident_investigation.py` compares broad context with curated context and includes an insufficient-evidence scenario. The goal is to reduce irrelevant context while preserving enough evidence for a defensible result.

### 9.3 Multi-agent orchestration

`Phase_7/c_tasks/c9_orchestration.py` defines specialized roles:

- `DataPipelineAgent`: ingestion, freshness, and data-quality state.
- `NetworkAnalysisAgent`: activity, alerts, and anomaly interpretation.
- `MLAnalysisAgent`: features and risk-model evidence.
- `APIAgent`: endpoint/API contract perspective.
- `SupervisorOrchestrator`: combines outputs, preserves source attribution, compares disagreements, and recommends checks.

The orchestrator is a reasoning and evidence-combination layer. It does not replace deterministic calculations.

### 9.4 MCP server

`.claude/mcp_server.py` uses stdio transport and calls FastAPI over HTTP. It exposes read-oriented tools for summary, grid activity, features, hotspots, alerts, and pipeline status. It validates grid IDs, limits, hours, and severity values, then returns API results without independently re-ranking or changing business metrics.

The packaged equivalent and usage notes are under `plugins/network-engineering/mcp/`.

Some MCP/legacy tools mention location and nearby-hotspot operations. Those currently return gap reports or `Not implemented` because the corresponding API routes do not exist.

### 9.5 Project commands and skills

`.claude/commands/` and `Phase_7/c_tasks/project_commands.py` provide deterministic operational commands such as:

- `/check-pipeline`
- `/explain-grid`
- `/review-anomaly`
- `/test-api`
- `/network-health`

The project skills under `.claude/skills/` package domain workflows for anomaly analysis, pipeline troubleshooting, and telecom data quality. Hooks under `.claude/hooks/` run focused checks after relevant edits and record outcomes in `logs/hook_log.csv`.

## 10. Phase-by-Phase System Guide

This section is the primary navigation model for the repository. Each phase is divided into purpose, implementation areas, inputs and outputs, contracts, and validation. The earlier chapters remain the detailed reference for schemas, storage, endpoints, and runtime behavior.

### Phase 1: Initial pandas processing

#### Purpose

Phase 1 establishes the original analytical vocabulary and the first grid-level summaries. It is historical context for the current system rather than the deployed pipeline.

#### Processing sections

- **Source interpretation**: understand the original timestamp, grid, country, SMS, call, and internet fields.
- **Pandas transformation**: derive date, hour, weekday, grid, and activity KPIs.
- **Reference outputs**: compare daily and grid-level exports with later Spark results when investigating regressions.
- **Tests and documentation**: use the phase tests to understand the initial expected behavior.

#### Implementation and boundary

`Phase_1/src/` contains the processor, `Phase_1/tests/` contains its tests, `Phase_1/docs/` contains supporting documentation, and `Phase_1/outputs/` contains generated examples. This phase may use different paths and assumptions from the unified runtime and must not be treated as the production entry point.

#### What was done

The `UsageProcessor` in `Phase_1/src/usage_processor.py` implemented the first complete pandas workflow:

1. Loaded CSV data into a DataFrame.
2. Validated required columns, null key fields, and negative activity values.
3. Derived date, hour, and day-of-week fields.
4. Aggregated country-code rows by `(datetime, CellID)`.
5. Calculated `total_sms`, `total_calls`, and `total_activity`.
6. Produced daily and grid-level CSV summaries.

The accompanying tests in `Phase_1/tests/test_usage_processor.py` covered individual processing methods and the full workflow. They also checked that the aggregated output had no duplicate `(datetime, CellID)` keys and that summary files were created.

#### Observations and results

The recorded notebook run in `Phase_1/notebooks/np2.ipynb` processed one day of data:

| Observation | Recorded result |
|---|---:|
| Raw rows | 1,891,928 |
| Grid-hour rows after aggregation | 240,000 |
| Total activity | 95,727,626.1171 |
| Busiest hour | 11 |
| Busiest grid | 5161 |

The alert prototype in `Phase_1/notebooks/np3.ipynb` used a within-grid median baseline, a 25th-percentile activity floor, and 1.5x/0.5x thresholds. It recorded 10,731 high-activity alerts, 4,112 spike alerts, and 18,483 drop alerts, for 33,326 alert records.

#### Phase 1 observations and limitations

- The pandas implementation proved the basic transformations and KPI definitions before the Spark version was introduced.
- Aggregating country-code rows substantially reduced the data to the intended grid-hour shape.
- The alert prototype was useful for discovering unusual activity, but its baseline covered only one day. The documented limitation is that it cannot represent longer-term seasonality or historical behavior.
- The alert logic was notebook-based; `Phase_1/src/network_alerts.py` did not yet provide a reusable alert module.
- The phase had no landing-zone routing, immutable raw zone, GeoJSON enrichment, warehouse load, or atomic multi-stage publication.
- A notebook run also recorded a `NameError` caused by referencing `rows_per_grid_hour` before it was defined, showing that this phase was exploratory rather than production-hardened.

#### Validation

Validate that derived measures and grouping keys agree with the canonical definitions in [Section 4](#4-end-to-end-data-flow). Differences should be explained by implementation generation, not silently merged.

### Phase 2: Educational Spark pipeline

#### Purpose

Phase 2 demonstrates the transformation from accepted source files to one row per grid and hourly timestamp after country-code aggregation.

#### Processing sections

- **Ingestion**: `sp1_ingestion.py` reads source data with explicit schema expectations.
- **Cleaning**: `sp2_cleaning.py` standardizes fields and identifies invalid rows.
- **Aggregation**: `sp3_aggregation.py` computes grid-hour measures and KPIs.
- **Geospatial enrichment**: `sp4_geospatial.py` joins activity to Milan grid geometry.
- **Performance and execution**: `sp5-6_Performance_Execution.ipynb` explores Spark execution behavior.
- **End-to-end execution**: `sp7_etl_job.ipynb` demonstrates the complete educational flow.

#### Current runtime boundary

The educational files explain the concepts, but the current runtime is under `spark/` and starts with `python -m spark.telecom_pipeline`. The authoritative stage order is `process_landing -> read_raw -> clean -> aggregate -> enrich -> write_outputs`, documented in `spark/JOB_CONTRACT.md`.

#### What was done

Phase 2 rebuilt the transformation as separate Spark stages:

1. `sp1_ingestion.py` created a local Spark session, read seven source files using an explicit schema, added input-file lineage, and profiled partitions and dimensions.
2. `sp2_cleaning.py` standardized raw names, cast types, profiled nulls, rejected invalid keys and negative values, converted permitted activity nulls to zero, and derived time and activity features.
3. `sp3_aggregation.py` grouped by `(timestamp, grid_id)`, removed `country_code`, recomputed KPIs and `internet_share`, validated the canonical grain, and wrote Parquet.
4. `sp4_geospatial.py` loaded the Milan GeoJSON, mapped `properties.cellId` to `grid_id`, broadcast the lookup, checked row counts and coverage, and wrote enriched Parquet.
5. `sp5-6_Performance_Execution.ipynb` investigated caching, execution plans, broadcast versus standard joins, partitioning, and Parquet writes.

This phase established the main transformation pattern later used by the unified `spark/` package, but the scripts remained educational standalone programs with hard-coded local paths.

#### Observations and results

The recorded stage reports contain the following results:

| Stage or measure | Recorded result |
|---|---:|
| Source files ingested | 7 |
| Raw rows | 15,089,165 |
| Grid identifiers | 10,000 |
| Country-code categories | 326 |
| Hourly intervals | 168 |
| Spark partitions | 15 |
| Rows after cleaning | 15,089,165 |
| Rejected rows | 0 |
| Rows after aggregation | 1,679,994 |
| Theoretical seven-day grid-hour maximum | 1,680,000 |
| Duplicate grid-hour keys | 0 |
| GeoJSON grid coverage | 10,000 / 10,000, or 100% |
| Aggregated peak hour | 17 |
| Top grid | 5161 |

The small difference between the theoretical maximum and observed aggregate rows indicates a small number of grid-hour combinations had no activity row, while the zero duplicate count confirms the canonical grain was preserved. Cleaning retained all source rows because no rows violated the tested key and negative-value rules; naturally occurring null activity measures were handled as zero where permitted.

#### Phase 2 observations and limitations

- The Spark implementation scaled the Phase 1 logic from a one-day pandas workflow to seven daily files and more than 15 million source rows.
- Country-code aggregation reduced 15,089,165 source rows to 1,679,994 grid-hour rows without duplicate keys.
- The enrichment step achieved complete coverage and used the correct `properties.cellId` join key.
- During the original lookup construction, the Windows Spark run recorded worker-reset warnings when the GeoJSON lookup was created through Python. The join and output still completed successfully; the current unified enrichment implementation avoids this path by using a temporary JSON lookup read through Spark.
- Phase 2 scripts read directly from `data/`, write to `Phase_2/outputs/`, and use fixed paths. They do not provide the unified landing/raw/rejected workflow, centralized orchestration, atomic publication behavior, warehouse handoff, or current API integration.

#### Inputs, outputs, and validation

Daily CSV files enter `data/landing/`; accepted files become immutable under `data/raw/`; successful runs publish to `data/processed/` and `data/analytics/`. Validate schema handling, row quarantine, duplicate `(grid_id, timestamp)` keys, `properties.cellId` joins, and atomic publication with `python -m pytest test_pipeline_91_92.py -v`.

`Phase_2/` breaks the transformation into numbered learning stages:

1. `sp1_ingestion.py`: ingest source data.
2. `sp2_cleaning.py`: clean and standardize records.
3. `sp3_aggregation.py`: group activity to grid/time summaries.
4. `sp4_geospatial.py`: join grid activity to geographic data.
5. `sp5-6_Performance_Execution.ipynb`: performance and execution exploration.
6. `sp7_etl_job.ipynb`: end-to-end educational ETL job.

The phase also includes `winutils`, documentation, and outputs. These files explain Spark concepts and processing order but may use fixed local paths and should not be used as the unified production command.

### Phase 3: Architecture, storage, and orchestration

#### Purpose

Phase 3 defines how data moves between zones and how the batch workflow can be scheduled around the Spark runtime and warehouse.

#### Design sections

- **Architecture**: `de1_telco_data_arch.txt` describes the layered system.
- **Storage strategy**: `de_5_storage_strat.txt` describes file and warehouse roles.
- **Batch versus streaming**: `de4_batch_vs_streaming.txt` records execution tradeoffs.
- **Orchestration practice**: `AirFlow_Practice/` contains Airflow exercises and DAG examples.
- **Warehouse loading**: `warehouse/load_warehouse.py` loads analytical output into MySQL.

#### Contracts and validation

The warehouse preserves one `(grid_id, timestamp)` row after country-code aggregation. Check that fact rows resolve to both dimensions, duplicate grid-hour rows are rejected, and loaded timestamps match the analytics output. The direct package command remains authoritative; Airflow is an orchestration layer.

`Phase_3/` contains:

- `de1_telco_data_arch.txt`: broader telecom data architecture.
- `de_5_storage_strat.txt`: storage and warehouse strategy.
- `de4_batch_vs_streaming.txt`: batch/streaming design discussion.
- `AirFlow_Practice/`: Airflow DAG practice and related execution material.

This phase explains why the project separates landing, processing, analytics, warehouse, ML, API, and dashboard layers. The Airflow DAG is orchestration practice; the current direct pipeline command remains `python -m spark.telecom_pipeline`.

### Phase 4: API and serving layer

#### Purpose

Phase 4 exposes warehouse, feature, anomaly, and model results through stable HTTP contracts for browser and investigation-tool consumers.

#### Service sections

- **Application lifecycle**: `main.py` creates the app and loads serving dependencies.
- **Routes**: `routers/network.py` defines summary, grid, hotspot, alert, anomaly, feature, prediction, evidence, insight, and pipeline-status endpoints.
- **Service logic**: `services.py` owns SQL queries, range resolution, feature selection, and evidence assembly.
- **Schemas and database**: `schemas.py` and `database.py` define the API boundary and connection behavior.
- **Prediction contract**: `docs/predict_risk_contract.md` is authoritative for `/network/predict-risk`.

#### Request flow and validation

```text
HTTP request -> router validation -> service query/feature resolution -> model or evidence calculation -> response schema
```

Run `python -m pytest Phase_4/tests/ -v`. Verify inclusive ranges, `as_of` filtering, prompt database failures, missing-data responses, deterministic feature selection, and model-feature compatibility.

`Phase_4/` contains the current FastAPI implementation, database access, Pydantic schemas, service SQL, model serving, validation SQL, API tests, and output artifacts. It is the contract boundary between warehouse/ML data and browser/agent consumers.

### Phase 5: React operator dashboard

#### Purpose

Phase 5 presents API-backed operational views without connecting the browser directly to MySQL or the filesystem.

#### Interface sections

- **Navigation and composition**: `src/App.jsx` and `src/components/Navbar.jsx` coordinate views.
- **Network summary**: totals, active grids, peak hour, and top grid.
- **Grid activity**: hourly series with date, hour, range, and `as_of` filters.
- **Hotspots and alerts**: ranked activity, severity, rule alerts, and rising-grid evidence.
- **Map**: Leaflet/GeoJSON rendering keyed by `properties.cellId`.
- **Predictive risk and insight**: feature display, probability, risk level, and structured AI sections.

#### Client boundary and validation

All API calls belong in `src/api/config.js`; geometry is served from `public/`; components do not duplicate SQL or model calculations. From `Phase_5/`, run `npm run build` and verify loading, empty, error, and missing-grid states. There is currently no dedicated frontend test or lint script.

`Phase_5/` contains the current Vite/React user interface. It provides summary monitoring, grid-level time series, ranked hotspots and alerts, a Leaflet map, predictive risk, and Claude insight presentation. It communicates with the API and does not access storage directly.

### Phase 6: ML development notebooks

#### Purpose

Phase 6 documents model and feature-engineering experiments that produced the artifacts used by the serving layer.

#### Development sections

- **Notebook experiments**: `Phase_6/` contains staged ML development notebooks.
- **Feature generation**: `ml/features.py` computes `avg_activity`, `activity_growth`, `active_hours`, `peak_ratio`, `variability`, and `internet_share`.
- **Model artifacts**: `ml/*.joblib` and metadata files define deployable versions.
- **Anomaly evidence**: `spark/anomaly_scoring.py` computes baseline, deviation, direction, and anomaly score.

#### Contract and validation

The API consumes serialized artifacts, not notebooks at request time. Verify point-in-time feature windows, scores in `[0.0, 1.0]`, risk-level thresholds, missing-feature behavior, and the v2 metadata naming difference for the internet feature.

`Phase_6/` contains notebooks named for ML development stages, including model and feature-generation experiments. These notebooks document experimentation and artifact creation. The deployed service uses the resulting `.joblib` artifacts and metadata in `ml/`; notebook execution is not part of the normal API request path.

### Phase 7: Operational intelligence and AI integration

#### Purpose

Phase 7 adds the operational intelligence and engineering-governance layer around the deterministic NOPIS runtime. It includes Claude/LLM insight, reusable commands and skills, edit-time safeguards, MCP access, headless investigation, multi-agent orchestration, plugin packaging, engineering review, and controlled experimentation.

#### 7.1 `CLAUDE.md` project guide

`CLAUDE.md` is the project-level Claude Code guide and operational source of truth. It documents:

- The NOPIS architecture and actual component locations.
- The end-to-end data flow from landing files through Spark, MySQL, ML, FastAPI, and React.
- The canonical `(grid_id, timestamp)` grain after country-code aggregation.
- Required terminology for activity measures, grid identity, risk, anomaly scores, and `as_of` behavior.
- The fixed pipeline order: `process_landing -> read_raw -> clean -> aggregate -> enrich -> write_outputs`.
- Atomic failure expectations and output-path rules.
- API, prediction, frontend, database, model, and Windows Spark constraints.
- Required run commands, proposed tests, and proposed documentation.
- The repository security policy using `ALLOW`, `ASK`, and `DENY` operation classes.

The guide also requires raw inputs to remain immutable, prevents destructive database operations, protects secrets, and requires explicit approval for sensitive pipeline, schema, Airflow, dependency, and API-contract changes.

#### 7.2 `.claude/` project configuration

The `.claude/` directory contains the active Claude Code configuration:

```text
.claude/
├── commands/
├── hooks/
├── hooks.json
├── mcp_config.json
├── mcp_server.py
└── skills/
```

It connects project rules to repeatable commands, reusable expertise, automated safeguards, and read-only network tools.

#### 7.3 Reusable slash commands

Commands are stored in `.claude/commands/` and use deterministic project code where applicable:

| Command | Purpose |
|---|---|
| `/check-pipeline` | Checks ingestion logs, rejected files, and warehouse freshness. |
| `/explain-grid` | Produces a structured grid investigation with severity, evidence, interpretation, and next checks. |
| `/review-anomaly` | Compares rule alerts, ML risk, and statistical anomaly evidence. |
| `/test-api` | Runs the FastAPI test suite and summarizes results. |
| `/network-health` | Checks uniqueness of the canonical grid-hour grain. |
| `/engineering-review` | Reviews changed files, applicable tests, data quality, contracts, terminology, and missing coverage. |

#### 7.4 Reusable Claude skills

Skills are stored under `.claude/skills/`:

- **`network-anomaly-analysis`**: investigates unusual grid activity using current activity, baseline, anomaly score, direction, rule evidence, model risk, and pipeline freshness.
- **`pipeline-troubleshooting`**: investigates Spark failures, rejected files, stale warehouse data, and stage exit codes.
- **`telecom-data-quality`**: validates canonical grain integrity, duplicate detection, quarantine counts, and GeoJSON joins using `properties.cellId`.

#### 7.5 C3 and C5: Investigation design and rising grids

C3 compared broad raw context with a smaller curated evidence package. The curated approach selects relevant activity, feature, anomaly, and pipeline information while preserving source attribution. Investigation results use the sections `SEVERITY`, `EVIDENCE`, `INTERPRETATION`, and `NEXTCHECKS`.

C5 designed the rising-grid capability around existing anomaly results. It specifies reuse of current baseline and deviation calculations, an API route, frontend integration in the hotspot view, and focused tests rather than a second independent calculation path.

#### 7.6 C6 and C7: Security policy and slash commands

C6 formalized repository operation classes:

- **ALLOW**: source reads, approved raw-data inspection, automated tests, formatting, and linting.
- **ASK**: dependency changes, database schema changes, Airflow DAG edits, pipeline/session configuration changes, and API schema changes.
- **DENY**: raw-data modification or deletion, data-directory deletion, secrets access, and destructive database operations.

C7 converted recurring NOC and engineering activities into the commands listed above, making pipeline checks, API tests, grid investigations, anomaly reviews, and grain checks repeatable.

#### 7.7 C8 and C9: Skills and multi-agent orchestration

C8 packaged reusable network expertise into the three `.claude/skills/` workflows. Each skill defines the evidence needed for a defensible result.

C9 defines specialist roles:

- `DataPipelineAgent`: ingestion, freshness, rejection, and data-quality state.
- `NetworkAnalysisAgent`: activity, alerts, and anomaly interpretation.
- `MLAnalysisAgent`: feature and model evidence.
- `APIAgent`: endpoint and contract perspective.
- `SupervisorOrchestrator`: combines outputs, preserves source attribution, compares disagreements, and recommends checks.

The orchestrator is an evidence-combination layer and does not replace Spark, warehouse queries, anomaly calculations, or model inference.

#### 7.8 C10: Event-driven hooks

Hooks are configured in `.claude/hooks.json`:

| Hook file | Trigger and purpose |
|---|---|
| `.claude/hooks/run_post_edit_checks.py` | Runs after edits to Python files under `spark/` or `ml/`. |
| `.claude/hooks/run_pre_action_check.py` | Runs before edits to protected pipeline, schema, and Airflow files. |

The post-edit hook runs the Spark grain/duplicate failure-path check and the ML2 feature-leakage test in `Phase_4/tests/test_c10_ml2_leakage.py`. The leakage tests verify feature names, future-data exclusion, feature timestamps, all six features, finite values, non-negative activity, and bounded internet share.

The pre-action gate blocks unapproved edits to sensitive files and requires explicit approval. Every hook execution is appended to `logs/hook_log.csv` with the trigger file, checks, result, and details.

#### 7.9 C11: Checkpoints and controlled rollback

C11 defines a controlled process for experimenting with anomaly or risk rules:

1. Create a checkpoint before the change.
2. Change one threshold or rule at a time.
3. Keep model artifacts and feature engineering fixed.
4. Compare alert volume before and after.
5. Compare the top-20 attention list.
6. Measure agreement with the existing rule system.
7. Separate measured evidence from interpretation.
8. Verify rollback restores the original diff, alert volume, and tests.

Raw data and destructive database operations are excluded from experiments.

#### 7.10 C12: MCP Network Intelligence server

The MCP server is implemented in `.claude/mcp_server.py` and configured in `.claude/mcp_config.json`:

```text
Claude / Claude Code
  |
  v
.claude/mcp_server.py
  |
  v
FastAPI endpoints
  |
  v
NOPIS services and MySQL
```

It is a thin, read-only wrapper. It validates inputs, calls existing FastAPI endpoints over HTTP, and returns API results. It does not query MySQL directly, calculate anomaly or risk scores, apply thresholds, rank data, reinterpret results, or access secrets.

Supported tools include `network_summary`, `grid_activity`, `grid_features`, `hotspots`, `alerts`, and `pipeline_status`. `grid_location` and `nearby_hotspots` are documented gap-report tools because their corresponding API capabilities are not currently implemented.

The MCP server requires FastAPI to be running and uses `NOPIS_API_BASE_URL` to locate it. The current server location is `.claude/mcp_server.py`; some older reports refer to a Phase 7 path.

#### 7.11 C13: Network Engineering plugin

C13 packages team-standard rules and tools under `plugins/network-engineering/`:

```text
plugins/network-engineering/
├── plugin.json
├── README.md
├── rules/
├── commands/
├── skills/
├── hooks/
└── mcp/
```

The plugin contains portable copies of the project rules, commands, skills, hook runners, hook configuration, and MCP documentation. Secrets, credentials, tokens, and private environment values are excluded. Versioning uses semantic versioning: major releases for breaking changes, minor releases for compatible capabilities, and patch releases for fixes or documentation updates.

#### 7.12 C14: Headless NOC investigation agent

`Phase_7/investigate_grid.py` provides a command-line investigation workflow:

```powershell
python Phase_7/investigate_grid.py 4821
```

The workflow is `gather -> compare -> assess -> summarize`. Pipeline status is checked first, followed by grid activity, features, curated evidence, and location information where available. Failed API calls are recorded in `uncertainty`; no fallback values are invented. The output contains `severity`, `evidence`, `uncertainty`, and `recommended_checks`.

#### 7.13 C15: Engineering review command

C15 adds `/engineering-review`. It reads `CLAUDE.md`, inspects the working-tree change, selects and runs relevant tests, and reviews code separately from test results.

The review checks canonical grain and duplicate risk, feature leakage, geographic join keys, API and prediction contracts, terminology, missing tests, and residual risks. The output is advisory; human reviewers retain approval, merge, deployment, and release decisions.

#### 7.14 C16: Context and usage optimization

C16 compared broad context with curated context for investigations. Curated context reduces irrelevant material and improves evidence focus while preserving source attribution. The tradeoff is that filtering must still retain pipeline status, activity, features, anomaly evidence, and uncertainty.

#### 7.15 Phase 7 evidence boundary and validation

AI output is interpretation over curated evidence. It must preserve source facts, distinguish evidence from interpretation, and state uncertainty when fields are missing. The deterministic Spark, warehouse, anomaly, ML, and API layers remain the source of truth.

Phase 7 changed NOPIS from a pipeline and dashboard into a governed engineering and investigation environment. It introduced repeatable commands, reusable skills, automated edit-time checks, protected configuration files, read-only MCP access, headless investigation, multi-agent evidence combination, plugin packaging, engineering review, and controlled rollback procedures.

Relevant validation includes Phase 7 investigation tests, C10 hook checks, C12 MCP tests, C9 orchestration tests, insufficient-evidence tests, API tests, and the engineering-review workflow. Inspect `logs/hook_log.csv` when verifying hook behavior.


## 11. Testing and Validation

### Pipeline

From the repository root:

```powershell
python -m pytest test_pipeline_91_92.py -v
```

The tests cover important pipeline behavior, including failure paths and grain-related checks. Additional proposed coverage in the repository guides includes cleaning quarantine, enrichment join correctness, atomic output publication, and genuinely empty input handling.

### API

API tests are under `Phase_4/tests/`. They should be run with:

```powershell
python -m pytest Phase_4/tests/ -v
```

Phase 7 contains additional tests for agent/tooling behavior, including insufficient evidence and orchestration scenarios.

### Build and runtime checks

```powershell
python -m spark.telecom_pipeline
Set-Location Phase_4
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
Set-Location ..\Phase_5
npm run build
```

The API requires MySQL and model artifacts at runtime. The dashboard requires the API to be reachable at the configured base URL.

## 12. Current Caveats and Review Points

1. **Output contracts differ by generation.** Current code writes under `data/processed` and `data/analytics`; older material may describe `spark/output`.
2. **Path conventions are mixed.** The project targets Windows, but warehouse loading includes WSL-style paths.
3. **Database configuration is inconsistent.** Some modules use hard-coded URLs while others support environment configuration.
4. **Anomaly storage is not fully represented in core DDL.** `network_anomaly_scores` is created dynamically.
5. **Feature selection needs deterministic ordering.** One stored-feature query uses `LIMIT 1` without `ORDER BY`.
6. **Point-in-time behavior is incomplete in some explanation paths.** Prediction feature resolution honors `as_of` more consistently than anomaly context lookup.
7. **Model metadata and API feature names diverge for v2.** Verify the v2 artifact before production use.
8. **Some invalid query combinations are reported as empty/404 behavior.** Clear request validation would be preferable.
9. **Location and nearby-hotspot routes are referenced by older tools but are not implemented in FastAPI.**
10. **Frontend automated coverage is limited.** No frontend test or lint script is currently defined.
11. **Geometry completeness is logged rather than always enforced as a publication failure.** Downstream quality checks should verify that active grids have geometry.
12. **Generated and temporary directories should not be treated as source-of-truth data.**

## 13. Source Map

### Canonical contracts and guides

- [AGENTS.md](AGENTS.md)
- [CLAUDE.md](CLAUDE.md)
- [spark/JOB_CONTRACT.md](spark/JOB_CONTRACT.md)
- [docs/predict_risk_contract.md](docs/predict_risk_contract.md)

### Current data and pipeline implementation

- [spark/telecom_pipeline.py](spark/telecom_pipeline.py)
- [spark/landing_ingestion.py](spark/landing_ingestion.py)
- [spark/ingestion.py](spark/ingestion.py)
- [spark/cleaning.py](spark/cleaning.py)
- [spark/aggregation.py](spark/aggregation.py)
- [spark/enrichment.py](spark/enrichment.py)
- [spark/writer.py](spark/writer.py)
- [spark/anomaly_scoring.py](spark/anomaly_scoring.py)
- [warehouse/schema.sql](warehouse/schema.sql)
- [warehouse/load_warehouse.py](warehouse/load_warehouse.py)
- [ml/features.py](ml/features.py)

### API and frontend

- [Phase_4/main.py](Phase_4/main.py)
- [Phase_4/routers/network.py](Phase_4/routers/network.py)
- [Phase_4/services.py](Phase_4/services.py)
- [Phase_4/schemas.py](Phase_4/schemas.py)
- [Phase_4/database.py](Phase_4/database.py)
- [Phase_4/ml5_model_service.py](Phase_4/ml5_model_service.py)
- [Phase_5/src/main.jsx](Phase_5/src/main.jsx)
- [Phase_5/src/App.jsx](Phase_5/src/App.jsx)
- [Phase_5/src/api/config.js](Phase_5/src/api/config.js)
- [Phase_5/src/components](Phase_5/src/components)

### AI, MCP, and operational tooling

- [Phase_7/c_tasks/claude_insight_service.py](Phase_7/c_tasks/claude_insight_service.py)
- [Phase_7/c_tasks/c3_incident_investigation.py](Phase_7/c_tasks/c3_incident_investigation.py)
- [Phase_7/c_tasks/c9_orchestration.py](Phase_7/c_tasks/c9_orchestration.py)
- [Phase_7/investigate_grid.py](Phase_7/investigate_grid.py)
- [.claude/mcp_server.py](.claude/mcp_server.py)
- [Phase_7/c_tasks/project_commands.py](Phase_7/c_tasks/project_commands.py)
- [plugins/network-engineering/mcp/README.md](plugins/network-engineering/mcp/README.md)

## 14. Summary

NOPIS is a layered system with a clear canonical path: validate and preserve source files, transform them with Spark to a grid-hour analytical grain, enrich with geographic identity, publish analytical outputs, load a relational warehouse, derive ML and anomaly evidence, serve that evidence through FastAPI, visualize it in React, and add Claude-assisted interpretation on top of curated evidence.

The most important architectural boundary is that deterministic data processing and model calculations happen before interpretation. Spark, MySQL, anomaly scoring, and ML prediction provide measurable evidence. FastAPI exposes that evidence. React and Claude consume it. Historical phases document how the system evolved, but the unified `spark.telecom_pipeline` path and the Phase 4 API are the primary runtime surfaces.
