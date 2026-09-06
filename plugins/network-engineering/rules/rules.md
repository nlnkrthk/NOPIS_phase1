<!-- 299. Package them into a project or team plugin. -->
# NOPIS Engineering Rules & Guidelines

This document packages the team-standard rules and domain guidelines originating from `CLAUDE.md`. All engineers and AI assistants working on the NOPIS repository must adhere strictly to these principles.

---

## 1. System Architecture Overview

NOPIS is a five-layer system where each layer feeds the next:

```text
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

## 2. Canonical Data Grain

The canonical analytics grain is:

> **one grid per hourly timestamp** — after country-code aggregation.

* Each row in `fact_network_activity` (and in the Spark analytics output) represents one Milan grid cell (`grid_id`) at one hourly slot (`timestamp`).
* The `aggregate()` step collapses all country-code sub-rows into this single grain by summing activity measures.
* Duplicate `(grid_id, timestamp)` combinations are strictly prohibited and will halt the pipeline.

---

## 3. Core Terminology

| Term | Meaning in NOPIS |
| ---- | ---------------- |
| `grid_id` | Integer identifier of a Milan spatial cell (1–10,000) |
| `timestamp` | Hourly time slot (canonical grain key alongside `grid_id`) |
| `total_activity` | Sum of all five proportional activity measures for a grid at one hour |
| `activity measure` | Proportional composite derived from call, SMS, and internet events (NOT raw counts or MB) |
| `AS_OF` | Reference point representing "what the system knows up to this point in time" |
| `risk_score` | Machine learning probability score in [0.0, 1.0] representing high activity risk, NOT congestion |
| `anomaly_score` | Statistical deviation of current activity from historical baseline |
| `direction` | Statistical classification: `NORMAL`, `HIGH`, or `LOW` |
| `feature_timestamp`| Point-in-time for which an ML feature vector was computed |

---

## 4. Non-Negotiable Project Rules

### Rule 1 — High activity does not mean confirmed congestion
Never equate high activity with confirmed congestion:
```text
High activity  !=  Confirmed congestion
```
High activity may be described as *elevated* or *high* activity. Congestion must **not** be claimed without direct capacity or utilization evidence (which this dataset does not contain). Never use *congestion*, *bandwidth exhaustion*, or *capacity exhaustion* in analysis or triage.

### Rule 2 — Canonical grain is one grid per hourly timestamp
The analytics grain is always **one row = one grid, one hourly timestamp** (after country-code aggregation). Queries and transformations must never assume finer country-code sub-rows or coarser daily aggregations.

### Rule 3 — Geographic join key is `properties.cellId`
When joining GeoJSON spatial geometries (`data/milano-grid.geojson`) to activity data, always use:
```text
features[].properties.cellId  ->  grid_id
```
**Never** use the 0-based `featureid` field as the join key.

### Rule 4 — Activity values are proportional measures, not counts or MB
The fields `sms_in`, `sms_out`, `call_in`, `call_out`, `internet_activity`, and `total_activity` are **proportional activity measures**. They are NOT call counts, SMS counts, or data volumes in MB.

### Rule 5 — AS_OF defines "now"
The `as_of` parameter is the system's boundary for historical reference. Never silently extend queries beyond the `as_of` timestamp.

### Rule 6 — Immutability of Raw Data
Raw data under `data/landing/` and `data/raw/` is immutable. Pipeline transformations write to `data/processed/` and `data/analytics/` atomically.

### Rule 7 — Existing APIs are the Source of Truth
Never reimplement business logic or execute direct SQL queries when an existing API endpoint (`Phase_4/routers/network.py`) provides the data. MCP tools and CLI commands must act as thin wrappers over these APIs.

### Rule 8 — Report Missing Evidence
If telemetry, baseline data, or feature vectors are missing during investigation, report `INSUFFICIENT EVIDENCE`. Do not fabricate or estimate metrics.
