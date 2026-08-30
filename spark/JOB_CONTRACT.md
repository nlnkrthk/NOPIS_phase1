# NOPIS Telecom Pipeline — Job Contract (SP7 / DE2)

## Overview

The telecom pipeline is a **batch ETL job** that validates incoming Milan telecom
activity CSVs from the landing drop zone, routes them to raw or rejected zones, reads
validated raw data into Spark, cleans and standardizes the data, aggregates to the
`(timestamp, grid_id)` grain, enriches with GeoJSON geometry, and writes
the result as Parquet and CSV.

---

## Expected Inputs & Data Zones

### 1. Data Zone Architecture

| Zone / Layer      | Location                                              | Description / Format                     |
|-------------------|-------------------------------------------------------|------------------------------------------|
| **Landing Zone**  | `--landing` (default: `D:\NOPIS\data\landing`)       | Incoming daily CSV drop zone             |
| **Raw Zone**      | `--raw` (default: `D:\NOPIS\data\raw`)               | Validated immutable CSV storage          |
| **Rejected Zone** | `--rejected` (default: `D:\NOPIS\data\rejected`)     | Quarantined invalid CSV files            |
| **Ingestion Logs**| `--logs` (default: `D:\NOPIS\logs`)                   | Audit log (`ingestion_log.csv`)          |

### 2. Telecom Activity CSVs

| Property       | Value                                        |
|----------------|----------------------------------------------|
| **Pattern**    | `sms-call-internet-mi-*.csv`                 |
| **Format**     | CSV with header row                          |
| **Encoding**   | UTF-8                                        |
| **Min files**  | 1 (pipeline fails if zero raw files match)   |

**Required columns** (raw names):

| Column        | Type      | Nullable |
|---------------|-----------|----------|
| `datetime`    | Timestamp | No       |
| `CellID`      | Integer   | No       |
| `countrycode` | Integer   | Yes      |
| `smsin`       | Double    | Yes      |
| `smsout`      | Double    | Yes      |
| `callin`      | Double    | Yes      |
| `callout`     | Double    | Yes      |
| `internet`    | Double    | Yes      |

### 3. GeoJSON Reference File

| Property       | Value                                               |
|----------------|-----------------------------------------------------|
| **Location**   | `--reference` path (default: `D:\NOPIS\data\milano-grid.geojson`) |
| **Format**     | GeoJSON FeatureCollection                           |
| **Join key**   | `features[].properties.cellId` → maps to `grid_id`  |
| **Features**   | ~10,000 grid polygons covering Milan                |

---

## Expected Outputs

Written to the `--output` directory (default: `D:\NOPIS\spark\output`):

### 1. `enriched_hourly_grid/` (Parquet)

Full enriched dataset at the `(timestamp, grid_id)` grain.

| Column             | Type      | Description                              |
|--------------------|-----------|------------------------------------------|
| `timestamp`        | Timestamp | Hourly time slot                         |
| `grid_id`          | Integer   | Milan grid cell identifier               |
| `sms_in`           | Double    | Inbound SMS activity                     |
| `sms_out`          | Double    | Outbound SMS activity                    |
| `call_in`          | Double    | Inbound call activity                    |
| `call_out`         | Double    | Outbound call activity                   |
| `internet_activity`| Double    | Internet activity                        |
| `date`             | Date      | Derived date                             |
| `hour`             | Integer   | Derived hour (0-23)                      |
| `total_sms`        | Double    | sms_in + sms_out                         |
| `total_calls`      | Double    | call_in + call_out                       |
| `total_activity`   | Double    | Sum of all 5 activity measures           |
| `internet_share`   | Double    | internet_activity / total_activity       |
| `geometry`         | String    | GeoJSON geometry (from broadcast join)   |

### 2. `summary_csv/` (CSV)

Same data coalesced into a single CSV file for quick inspection.

---

## Pipeline Stages

```
process_landing() → read_raw() → clean() → aggregate() → enrich() → write_outputs()
```

| Stage                 | Module                 | Key Operation                          |
|-----------------------|------------------------|----------------------------------------|
| **Landing Ingestion** | `landing_ingestion.py` | Detect, validate schema/quality, route |
| **Raw Ingestion**     | `ingestion.py`         | Read raw CSVs from raw/ with schema    |
| **Cleaning**          | `cleaning.py`          | Rename, quarantine, null→zero, derive  |
| **Aggregation**       | `aggregation.py`       | Collapse country codes, compute KPIs   |
| **Enrichment**        | `enrichment.py`        | Broadcast-join with GeoJSON            |
| **Writing**           | `writer.py`            | Parquet + CSV output                   |

---

## Failure Conditions

| Condition                          | Behavior                               |
|------------------------------------|----------------------------------------|
| No CSV files match in raw folder   | `FileNotFoundError` — exit code 1      |
| Null `grid_id` or `timestamp`      | Row quarantined (not in output)        |
| Negative activity values           | Row quarantined (not in output)        |
| Duplicate `(grid_id, timestamp)`   | `ValueError` — exit code 1            |
| Aggregation doesn't reduce rows    | `AssertionError` — exit code 1        |
| Any unexpected exception           | Logged with traceback — exit code 1    |

---

## Logging Contract

Every run logs the following to stdout:

| Metric               | When Logged             |
|----------------------|-------------------------|
| Start time (UTC)     | Pipeline start          |
| Landing files count  | After landing ingestion |
| Raw input row count  | After ingestion         |
| Null counts/column   | During cleaning         |
| Rejected row count   | After cleaning          |
| Rows after agg       | After aggregation       |
| Enrichment coverage  | After enrichment        |
| Output row count     | After writing           |
| End time (UTC)       | Pipeline end            |
| Elapsed seconds      | Pipeline end            |
| Final status         | Pipeline end (SUCCESS/FAILED) |

---

## Running the Pipeline

```bash
# Default run
python -m spark.telecom_pipeline

# Custom paths
python -m spark.telecom_pipeline \
    --landing   D:\NOPIS\data\landing \
    --raw       D:\NOPIS\data\raw \
    --rejected  D:\NOPIS\data\rejected \
    --logs      D:\NOPIS\logs \
    --output    D:\NOPIS\spark\output \
    --reference D:\NOPIS\data\milano-grid.geojson

# Using a config file
python -m spark.telecom_pipeline --config pipeline_config.json
```

### Config file format (JSON)

```json
{
    "landing":   "D:\\NOPIS\\data\\landing",
    "raw":       "D:\\NOPIS\\data\\raw",
    "rejected":  "D:\\NOPIS\\data\\rejected",
    "logs":      "D:\\NOPIS\\logs",
    "output":    "D:\\NOPIS\\spark\\output",
    "reference": "D:\\NOPIS\\data\\milano-grid.geojson"
}
```

