<!-- 299. Package them into a project or team plugin. -->
---
description: Inspect ingestion logs, rejected rows, and warehouse data freshness (NOC-oriented)
---

# /check-pipeline

Inspects the NOPIS data pipeline health across landing ingestion logs, rejected directories, and warehouse database freshness.

## Usage
```text
/check-pipeline
```

## Behind the Scenes
Executes:
```bash
python Phase_7/c_tasks/project_commands.py check-pipeline
```

## Checks Performed
1. **Warehouse Freshness**: Inspects `dim_time` for the maximum loaded timestamp.
2. **Fact Table Status**: Verifies record counts in `fact_network_activity`.
3. **Ingestion Log**: Checks `logs/ingestion_log.csv` for valid vs. invalid ingestion runs.
4. **Rejections**: Verifies whether any rejected files exist in `data/rejected/`.

## Output Sections
- **PIPELINE STATUS**: `HEALTHY`, `DEGRADED`, or `UNHEALTHY`
- **Warehouse Metrics**: Latest timestamp, total fact records
- **Ingestion Metrics**: Valid batches, invalid batches, rejected files
- **Quality Assessment**: Summary of operational data quality
