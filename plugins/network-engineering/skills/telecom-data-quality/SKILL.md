<!-- 299. Package them into a project or team plugin. -->
---
name: telecom-data-quality
description: Validate warehouse grain integrity, duplicate detection, GeoJSON join contracts, and data-quality rules.
version: 1.0.0
---

# Telecom Data Quality Skill

This skill enforces NOPIS relational grain contracts, cleaning quarantine rules, and spatial join integrity across the analytics dataset.

## Activation Criteria

### Activates On:
- "Check for duplicate grids"
- "Validate network grain"
- "Is there row inflation after the geo join?"
- "Check cleaning quarantine rules"
- "Audit data quality of hourly_grid_summary"

### Does NOT Activate On:
- Real-time cell anomaly triage (use `network-anomaly-analysis`).
- Investigating Airflow scheduler or Spark memory issues (use `pipeline-troubleshooting`).

---

## Required Evidence Checklist

1. **Canonical Grain Duplication Count**: Verification of `(grid_id, timestamp)` uniqueness via `/network-health`.
2. **Quarantine Metrics**: Dropped row statistics from `spark/cleaning.py` (null grid IDs, timestamps, negative activities).
3. **Geometry Join Key**: Verification that spatial enrichment joined on `properties.cellId` against `data/milano-grid.geojson` (never `featureid`).
4. **Valid Domain Boundaries**: Grid IDs in `[1, 10000]`; internet share in `[0.0, 1.0]`.

---

## Non-Negotiable Data Quality Rules

1. **Canonical Grain is Strictly One Grid per Hourly Timestamp**: After country-code aggregation, no duplicate `(grid_id, timestamp)` pairs are permitted.
2. **Geography Join Key**: Always join on `properties.cellId` in `data/milano-grid.geojson`.
3. **Quarantine Rather Than Drop Silently**: Invalid rows must be explicitly quarantined and counted.
4. **No Row Inflation**: Aggregation must reduce row count; spatial join must not duplicate rows.

---

## Mandatory Response Structure

```text
DATA QUALITY STATUS:
[PASS | WARNING | FAIL | INSUFFICIENT EVIDENCE]

VERIFIED QUALITY CHECKS:
- Evaluated Target: <dataset or table path>
- Canonical Grain Uniqueness: <0 duplicates = PASS | N duplicates = FAIL>
- Spatial Join Contract: <verified on properties.cellId>
- Valid Value Ranges: <Grid IDs 1-10000, Non-negative activity>

ANOMALOUS RECORDS / VIOLATIONS:
- Specific duplicate keys or quarantine records identified (if any).

CORRECTIVE ACTION:
- Prescriptive cleanup or pipeline re-run instructions following spark/JOB_CONTRACT.md.
```
