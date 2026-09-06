<!-- 299. Package them into a project or team plugin. -->
---
name: pipeline-troubleshooting
description: Troubleshoot NOPIS PySpark ETL batch runs, landing ingestion rejections, and warehouse freshness issues.
version: 1.0.0
---

# Pipeline Troubleshooting Skill

This skill governs how Claude investigates, diagnoses, and remediates batch ETL and warehouse ingestion problems across the NOPIS data pipeline.

## Activation Criteria

### Activates On:
- "Why did the pipeline fail?"
- "Are there rejected rows in landing?"
- "Is our warehouse analytics data stale?"
- "Why is hourly_grid_summary missing?"
- "Check pipeline health and errors"
- Questions regarding stage failures in `spark/telecom_pipeline.py`.

### Does NOT Activate On:
- Investigating individual cell tower/grid anomaly scores (use `network-anomaly-analysis`).
- Verifying data warehouse grains or duplicate keys (use `telecom-data-quality`).
- Modifying production Airflow DAG schedules without authorization.

---

## Required Evidence Checklist

Before drawing conclusions about pipeline health, verify:
1. **Ingestion Log Status**: Entries in `logs/ingestion_log.csv` (`VALID` vs. `INVALID`, failure reasons).
2. **Quarantine Directory**: Presence of files in `data/rejected/`.
3. **Warehouse Freshness**: Maximum timestamp in `dim_time` vs. expected schedule.
4. **Fact Table Volume**: Record counts in `fact_network_activity`.
5. **Atomic Stage Completion**: Verification that `data/processed/` and `data/analytics/` were not left in a partial state.
6. **Execution Logs**: Spark exit codes and stage traces from `python -m spark.telecom_pipeline`.

---

## Non-Negotiable Pipeline Rules

1. **Fixed Pipeline Order**: The pipeline order is non-negotiable:
   `process_landing() -> read_raw() -> clean() -> aggregate() -> enrich() -> write_outputs()`
2. **Atomic Failure**: On any pipeline failure, partial outputs in `data/processed/` or `data/analytics/` must never be used. The pipeline exits with code 1.
3. **Raw Data Immutability**: Golden input data under `data/raw/` is immutable and must never be altered or deleted during troubleshooting.
4. **Never Guess or Invent Failures**: State observed evidence directly from `logs/ingestion_log.csv` or terminal output.

---

## Mandatory Response Structure

```text
PIPELINE HEALTH STATUS:
[HEALTHY | DEGRADED | UNHEALTHY | INSUFFICIENT EVIDENCE]

OBSERVED EVIDENCE:
- Warehouse Latest Timestamp: <timestamp or NONE>
- Fact Records Count: <count>
- Ingestion Log Validation Summary: <valid_count> VALID, <invalid_count> INVALID
- Files in data/rejected/: <count and names>
- Target Output Verification: <status of data/analytics/hourly_grid_summary>

ROOT CAUSE ANALYSIS:
- Concrete assessment based strictly on verified log errors and filesystem state.
- Clearly separate observed facts from diagnostic hypotheses.

REMEDIATION ACTIONS:
1. Exact fix following spark/JOB_CONTRACT.md runbook.
2. Safe verification command: /check-pipeline.
```
