<!-- 299. Package them into a project or team plugin. -->
---
description: Validate the canonical (grid_id, timestamp) grain across hourly_grid_summary (Engineering-oriented)
---

# /network-health

Validates the canonical grain of the analytics dataset. The golden NOPIS data model requires strictly unique records for every `(grid_id, timestamp)` pair after country-code aggregation.

## Usage
```text
/network-health [optional_dataset_path]
```

### Examples
```text
/network-health
/network-health tmp/test_hourly_grid_summary
```

## Behind the Scenes
Executes:
```bash
python Phase_7/c_tasks/project_commands.py network-health [optional_dataset_path]
```

## Checks Performed
- Evaluates `data/analytics/hourly_grid_summary` Parquet dataset (or specified path).
- Performs duplicate check matching `spark/aggregation.py`: `df.duplicated(subset=['grid_id', 'timestamp'])`.
- Falls back to MySQL `fact_network_activity` validation if parquet is not present.

## Expected Output
- **Status**: `PASS` (0 duplicates) or `FAIL` (>0 duplicates)
- **Target Dataset**: Path evaluated
- **Canonical Grain**: `(grid_id, timestamp)`
- **Records Checked**: Total count of evaluated records
- **Duplicate Keys**: Number of violating combinations
- **Violation Samples**: Specific grid and timestamp pairs if grain violation is detected
