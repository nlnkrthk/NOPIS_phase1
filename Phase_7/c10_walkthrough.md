# C10 — Hooks & Event-Driven Workflows Walkthrough

## What Was Done

C10 configured Claude Code hooks so that important engineering checks run
automatically at the right moment — immediately after a Python edit to `spark/`
or `ml/`, and before any edit to sensitive pipeline configuration.

---

## Files Created

### `.claude/hooks.json`
The Claude Code hook configuration file. Registers two hooks:
- **PostToolUse** → runs grain/duplicate + ML2 leakage checks after Python edits
- **PreToolUse** → blocks edits to Airflow DAGs / sensitive pipeline files

### `.claude/hooks/run_post_edit_checks.py`
Post-edit runner. Reads the edited file path from stdin (JSON), checks if it
is under `spark/` or `ml/`, and if so runs:
1. `pytest test_pipeline_91_92.py -k TestSparkFailurePath`
2. `pytest Phase_4/tests/test_c10_ml2_leakage.py`

Prints PASS/FAIL for each check and logs to `logs/hook_log.csv`.

### `.claude/hooks/run_pre_action_check.py`
Pre-action gate. Reads the about-to-be-edited file path, matches against
the sensitive file list, and exits code 2 (block) with a clear
`APPROVAL REQUIRED` message if the file is sensitive.

Sensitive list:
- `Phase_3/AirFlow_Practice/dags/` (Airflow DAGs)
- `spark/spark_session.py`, `spark/JOB_CONTRACT.md`, `spark/telecom_pipeline.py`
- `warehouse/schema.sql`, `Phase_4/schemas.py`

### `Phase_4/tests/test_c10_ml2_leakage.py`
New standalone ML2 feature-leakage test (9 tests). No MySQL or Spark needed.
Tests:
- Feature names match the canonical ML2 spec
- Future timestamps do not leak into computed features (temporal isolation)
- `feature_timestamp` equals `max_ts` (the AS_OF boundary)
- All 6 features are always present
- Activity values are finite floats in valid ranges (NOPIS Rule 4)

### `logs/hook_log.csv`
Hook outcome log. Appended after every hook execution. Columns:
`datetime, hook_name, trigger_file, checks_performed, result, details`

---

## Files Modified

### `CLAUDE.md` (root) and `Phase_7/CLAUDE.md`
Added **Section 14 — C10 Hooks** documenting hook locations, trigger conditions,
sensitive file list, and log location.

### `spark/cleaning.py`
A safe docstring comment was added for the passing demo, then **reverted**.
The file is back to its original state.

---

## Demonstrations

### Passing Hook (actual output)

```
[C10 Hook] post-edit:spark_ml_checks
[C10 Hook] Triggered by: spark/cleaning.py
[C10 Hook] Grain/duplicate check: PASS
[C10 Hook] ML2 leakage test:         PASS
[C10 Hook] Overall hook: PASS
Exit code: 0
```

### Failing Hook (actual output)

```
[C10 Hook] post-edit:spark_ml_checks  [FAILING DEMO]
[C10 Hook] Triggered by: ml/features.py
[C10 Hook] Grain/duplicate check: FAIL
[C10 Hook]   Reason: duplicate (grid_id, timestamp) — 1 failed in 0.06s
[C10 Hook] ML2 leakage test:         PASS
[C10 Hook] Overall hook: FAIL
Exit code: 2
```

The controlled failure fixture was **deleted** after the demo. Repository restored.
18/18 tests pass in the clean state.

### Pre-Action Gate (actual output)

```
[C10 BLOCKED] Edit to 'Phase_3/AirFlow_Practice/dags/nopis_pipeline_dag.py'
              requires explicit human approval.
Exit code: 2
```

---

## Test Results

| Suite | Tests | Result |
|---|---|---|
| `test_pipeline_91_92.py` | 9 | ✅ All passed |
| `test_c10_ml2_leakage.py` | 9 | ✅ All passed |
| **Total** | **18** | **✅ 18 passed** |

---

## Manual Action Required

None from the repository side. The hooks are configured and verified.

> **Note on Claude Code integration**: `.claude/hooks.json` is the standard
> location Claude Code reads for project hooks. When you open this repository
> in Claude Code, the hooks will be active automatically. The hook scripts are
> called by Claude Code via the shell — they require Python 3.9+ in the PATH
> (the same Python used to run `pytest`).
