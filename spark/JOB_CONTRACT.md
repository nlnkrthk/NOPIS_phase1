# NOPIS Telecom Pipeline — Job Contract (SP7)

## Overview

The telecom pipeline is a **batch ETL job** that reads raw Milan telecom
activity CSVs, cleans and standardizes the data, aggregates to the
`(timestamp, grid_id)` grain, enriches with GeoJSON geometry, and writes
the result as Parquet and CSV.

---

## Expected Inputs

### 1. Telecom Activity CSVs

| Property       | Value                                        |
|----------------|----------------------------------------------|
| **Location**   | `--input` directory (default: `D:\NOPIS\data`) |
| **Pattern**    | `sms-call-internet-mi-*.csv`                 |
| **Format**     | CSV with header row                          |
| **Encoding**   | UTF-8                                        |
| **Min files**  | 1 (pipeline fails if zero files match)       |

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

### 2. GeoJSON Reference File

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
read_raw() → clean() → aggregate() → enrich() → write_outputs()
```

| Stage          | Module            | Key Operation                          |
|----------------|-------------------|----------------------------------------|
| **Ingestion**  | `ingestion.py`    | Read CSVs with manual schema           |
| **Cleaning**   | `cleaning.py`     | Rename, quarantine, null→zero, derive  |
| **Aggregation**| `aggregation.py`  | Collapse country codes, compute KPIs   |
| **Enrichment** | `enrichment.py`   | Broadcast-join with GeoJSON            |
| **Writing**    | `writer.py`       | Parquet + CSV output                   |

---

## Failure Conditions

| Condition                          | Behavior                               |
|------------------------------------|----------------------------------------|
| No CSV files match glob pattern    | `FileNotFoundError` — exit code 1      |
| Null `grid_id` or `timestamp`      | Row quarantined (not in output)        |
| Negative activity values           | Row quarantined (not in output)        |
| Duplicate `(grid_id, timestamp)`   | `ValueError` — exit code 1            |
| Aggregation doesn't reduce rows    | `AssertionError` — exit code 1        |
| Any unexpected exception           | Logged with traceback — exit code 1    |

---

## Logging Contract

Every run logs the following to stdout:

| Metric             | When Logged             |
|--------------------|-------------------------|
| Start time (UTC)   | Pipeline start          |
| Input file count   | After ingestion         |
| Input row count    | After ingestion         |
| Null counts/column | During cleaning         |
| Rejected row count | After cleaning          |
| Rows after agg     | After aggregation       |
| Enrichment coverage| After enrichment        |
| Output row count   | After writing           |
| End time (UTC)     | Pipeline end            |
| Elapsed seconds    | Pipeline end            |
| Final status       | Pipeline end (SUCCESS/FAILED) |

---

## Running the Pipeline

```bash
# Default training run
python -m spark.telecom_pipeline

# Custom paths
python -m spark.telecom_pipeline \
    --input  D:\NOPIS\data \
    --output D:\NOPIS\spark\output \
    --reference D:\NOPIS\data\milano-grid.geojson

# Using a config file
python -m spark.telecom_pipeline --config pipeline_config.json
```

### Config file format (JSON)

```json
{
    "input":     "D:\\NOPIS\\data",
    "output":    "D:\\NOPIS\\spark\\output",
    "reference": "D:\\NOPIS\\data\\milano-grid.geojson"
}
```
