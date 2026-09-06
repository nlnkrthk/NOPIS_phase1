# C10 — Hooks & Event-Driven Workflows

## Activity

C10 — Hooks & Event-Driven Workflows

## Tasks Completed

* **Task 281** — Post-edit hook for Python changes under `spark/` and `ml/`
* **Task 282** — Pre-action check for sensitive pipeline/Airflow configuration
* **Task 283** — Hook outcome logging to `logs/hook_log.csv`
* **Task 284** — Passing and failing hook demonstrations (actual test output)
* **Task 285** — Hooks versus CI discussion

---

## Hook Configuration

### Location

| File | Purpose |
|---|---|
| `.claude/hooks.json` | Claude Code hook configuration (event → runner mapping) |
| `.claude/hooks/run_post_edit_checks.py` | Post-edit runner script |
| `.claude/hooks/run_pre_action_check.py` | Pre-action gate script |

### Trigger Conditions

| Hook | Event | Trigger |
|---|---|---|
| Post-edit | `PostToolUse` on `Edit` / `Write` / `MultiEdit` | Python file path starts with `spark/` or `ml/` |
| Pre-action gate | `PreToolUse` on `Edit` / `Write` / `MultiEdit` | File path matches Airflow DAGs or sensitive pipeline files |

### Sensitive files guarded by the pre-action gate

- `Phase_3/AirFlow_Practice/dags/` (all DAG files)
- `spark/spark_session.py`
- `spark/JOB_CONTRACT.md`
- `spark/telecom_pipeline.py`
- `warehouse/schema.sql`
- `Phase_4/schemas.py`

### Tests/checks executed by post-edit hook

1. **Grain/duplicate check** — `python -m pytest test_pipeline_91_92.py -k TestSparkFailurePath -v --tb=short`
2. **ML2 feature-leakage test** — `python -m pytest Phase_4/tests/test_c10_ml2_leakage.py -v --tb=short`

### Approval behavior (pre-action gate)

- Claude Code sends the about-to-be-edited file path to `run_pre_action_check.py` via stdin.
- If the path is sensitive: script exits code 2 → Claude Code blocks the edit.
- A full `APPROVAL REQUIRED` message is printed to stderr.
- A short `[C10 BLOCKED]` summary is printed to stdout for Claude's context.
- The blocked attempt is logged to `logs/hook_log.csv`.
- To proceed, the user must explicitly say "I approve this edit to \<file\>."

### Logging behavior

Every hook execution appends one row to `logs/hook_log.csv`:

```
datetime,hook_name,trigger_file,checks_performed,result,details
```

- `result` is one of: `PASS`, `FAIL`, `BLOCKED`, `APPROVAL REQUIRED`
- The directory `logs/` already existed (contains `ingestion_log.csv`)

---

## Task 281 Results — Post-Edit Hook

### ML2 Feature-Leakage Test (new)

No existing ML2 leakage test was found in the repository. A new standalone test was created at `Phase_4/tests/test_c10_ml2_leakage.py`. It is pure Python, requires no MySQL or Spark, and runs in ~1 s.

Tests:

| Test | What it checks |
|---|---|
| `test_ml2_feature_names_match_spec` | The six ML2 feature names in `ml/features.py` match the canonical spec exactly |
| `test_ml2_no_future_data_used` | Future rows (timestamp > max_ts) do NOT influence computed features (temporal leakage) |
| `test_ml2_no_future_data_used_detects_leakage` | The harness itself is effective — confirms poison rows *would* change results if not filtered |
| `test_ml2_feature_timestamp_equals_max_ts` | `feature_timestamp` equals `max_ts`, never a future timestamp |
| `test_ml2_all_six_features_present` | All 6 feature keys present in every record |
| `test_ml2_feature_timestamp_present` | `feature_timestamp` is included |
| `test_ml2_activity_values_are_finite_floats` | All float features are finite (no NaN/Inf) — NOPIS Rule 4 |
| `test_ml2_avg_activity_nonnegative` | `avg_activity >= 0` |
| `test_ml2_internet_share_bounded` | `internet_share` in [0, 1] |

All 9 tests pass.

### Grain/Duplicate Check

Reuses the existing `TestSparkFailurePath` class in `test_pipeline_91_92.py`.
The hook calls this directly — no duplication.

---

## Task 282 Results — Pre-Action Gate

Demonstrated against the Airflow DAG:

```
STDOUT: [C10 BLOCKED] Edit to 'Phase_3/AirFlow_Practice/dags/nopis_pipeline_dag.py'
        requires explicit human approval.
        Reason: Airflow DAG directory: Phase_3/AirFlow_Practice/dags/

STDERR:
============================================================
[C10 Hook] pre-action:sensitive_pipeline_gate
[C10 Hook] APPROVAL REQUIRED
============================================================

  File:   Phase_3/AirFlow_Practice/dags/nopis_pipeline_dag.py
  Reason: Airflow DAG directory: Phase_3/AirFlow_Practice/dags/

  This file is classified as SENSITIVE PIPELINE CONFIGURATION
  under the NOPIS C6 permission policy (CLAUDE.md §11, ASK tier).

  Claude Code has BLOCKED this edit.

  To proceed:
    1. Review the proposed change yourself.
    2. Explicitly tell Claude: 'I approve this edit to
       Phase_3/AirFlow_Practice/dags/nopis_pipeline_dag.py.'
    3. Claude will then make the change under your direction.

  This check does NOT bypass C6. It enforces the ASK tier.
============================================================

Exit code: 2
```

The gate does NOT silently approve. It exits code 2, which Claude Code treats as a block signal.

---

## Task 283 Results — Hook Outcome Logging

`logs/hook_log.csv` is appended after every hook execution.

Example entries from actual demonstration runs:

```
datetime,hook_name,trigger_file,checks_performed,result,details
2026-09-05T15:09:06Z,post-edit:spark_ml_checks,spark/cleaning.py,grain_duplicate_check|ml2_leakage_test,PASS,grain_check PASS | ml2_leakage PASS
2026-09-05T15:10:31Z,post-edit:spark_ml_checks,ml/features.py,grain_duplicate_check|ml2_leakage_test,FAIL,grain_check FAIL: duplicate (grid_id timestamp) | ml2_leakage PASS
2026-09-05T15:10:47Z,post-edit:spark_ml_checks,spark/cleaning.py,grain_duplicate_check|ml2_leakage_test,PASS,grain_check PASS | ml2_leakage PASS
```

Log format is CSV, minimal, beginner-friendly, and appended rather than overwritten.

---

## Task 284 Results — Passing and Failing Hook Demonstrations

### Passing Hook Demonstration

**Trigger**: A safe docstring comment was added to `spark/cleaning.py`.  
**Hook**: `post-edit:spark_ml_checks` triggered automatically.

**Actual output:**

```
============================================================
[C10 Hook] post-edit:spark_ml_checks
[C10 Hook] Triggered by: spark/cleaning.py
============================================================

[C10 Hook] Running Check 1: Grain/duplicate (grid_id, timestamp) ...
[C10 Hook] Grain/duplicate check: PASS

[C10 Hook] Running Check 2: ML2 feature-leakage ...
[C10 Hook] ML2 leakage test:         PASS

[C10 Hook] ==================================================
[C10 Hook] Overall hook: PASS
[C10 Hook] ==================================================

Exit code: 0
```

### Failing Hook Demonstration

**Trigger**: A controlled edit was simulated against `ml/features.py`.  
**Failure condition**: A temporary test fixture (`Phase_4/tests/fixtures/grain_duplicate_fixture.py`) was created that intentionally simulates 3 duplicate `(grid_id, timestamp)` combinations.

**Actual output:**

```
============================================================
[C10 Hook] post-edit:spark_ml_checks  [FAILING DEMO]
[C10 Hook] Triggered by: ml/features.py
============================================================

[C10 Hook] Running Check 1: Grain/duplicate (grid_id, timestamp) ...
[C10 Hook] Grain/duplicate check: FAIL
[C10 Hook]   Reason: duplicate (grid_id, timestamp) — 1 failed in 0.06s

[C10 Hook] Running Check 2: ML2 feature-leakage ...
[C10 Hook] ML2 leakage test:         PASS

[C10 Hook] ==================================================
[C10 Hook] Overall hook: FAIL
[C10 Hook] ==================================================

[Hook logged to logs/hook_log.csv]
Exit code: 2
```

### Restoration

After the failing demo:

1. `Phase_4/tests/fixtures/grain_duplicate_fixture.py` was **deleted**.
2. The demo comment was **removed** from `spark/cleaning.py`.
3. Full test suite was re-run: **18/18 passed** (9 pipeline + 9 ML2 leakage).
4. `data/raw/` was **not touched** at any point.

---

## Task 285 Results — Hooks vs CI

### Core distinction

| Dimension | Hooks | CI |
|---|---|---|
| **When it runs** | Immediately after/before a Claude Code action | On push / pull request / schedule |
| **Latency** | Seconds | Minutes to hours |
| **Who sees it** | The developer pair-programming with Claude | The team / merge reviewers |
| **Scope** | Narrow, targeted at the specific file just changed | Broad, full project |
| **Purpose** | Enforce engineering discipline in the moment | Gate merges and deployments |

### What belongs in hooks (NOPIS)

| Check | Why hooks |
|---|---|
| Grain/duplicate check after `spark/` edits | Immediate feedback if a Spark edit breaks the `(grid_id, timestamp)` grain |
| ML2 leakage test after `spark/` or `ml/` edits | Catches temporal leakage the instant the feature logic is touched |
| Pre-action gate for Airflow DAG edits | Enforces the C6 ASK-tier policy; prevents silent pipeline DAG changes |
| Pre-action gate for `spark/telecom_pipeline.py` | Same — this is the pipeline entry point |
| Quick policy checks (NOPIS Rules 1–6) | Fast, context-specific, can be added incrementally |

These are **fast** (≤ 10 s), **targeted** (file-level), and **fail-fast** — exactly what hooks are for.

### What belongs in CI (NOPIS)

| Check | Why CI |
|---|---|
| Full API test suite (`Phase_4/tests/`) | Requires a running MySQL database — too heavy for a hook |
| End-to-end pipeline run | Requires Spark, real data, and minutes of execution |
| React dashboard build (`npm run build`) | Front-end compilation not relevant to every Python edit |
| Complete `pytest` across all test files | Too slow per edit; better as a merge gate |
| Integration tests (warehouse load, ML scoring) | Require external services |

### Why both are needed

Hooks and CI are **complementary, not competing**. Hooks give Claude Code (and the developer) immediate, in-context feedback during active development. CI provides the final quality gate before code reaches shared history or deployment.

```
Developer edits ml/features.py
        |
        v
Hook runs in 5s → grain + leakage: PASS / FAIL (immediate)
        |
        v
Developer pushes to git
        |
        v
CI runs full suite → all tests + integration + build (comprehensive)
```

The goal is not to move all CI checks into hooks, but to surface the checks most likely to catch the specific class of error just introduced — immediately.

---

## Validation Results

| # | Criterion | Result |
|---|---|---|
| 1 | Editing a Python file under `spark/` triggers the grain/duplicate test automatically | ✅ PASS |
| 2 | Editing a Python file under `ml/` triggers the relevant checks automatically | ✅ PASS |
| 3 | The ML2 feature-leakage test is triggered as required | ✅ PASS |
| 4 | Editing Airflow/pipeline configuration requires explicit confirmation | ✅ PASS — exit code 2, BLOCKED |
| 5 | Hook outcomes are logged | ✅ PASS — `logs/hook_log.csv` confirmed |
| 6 | One hook execution passes | ✅ PASS — `spark/cleaning.py` edit, exit 0 |
| 7 | One hook execution fails | ✅ PASS — controlled fixture, exit 2 |
| 8 | The failing hook clearly reports the failure | ✅ PASS — reason printed, log written |
| 9 | The controlled failure is removed afterward | ✅ PASS — fixture deleted, 18/18 tests pass |
| 10 | Existing C6 security boundaries remain intact | ✅ PASS — `data/raw/` untouched; ASK tier enforced, not bypassed |

---

## Files Created or Modified

| File | Action |
|---|---|
| `.claude/hooks.json` | **NEW** — hook event configuration |
| `.claude/hooks/run_post_edit_checks.py` | **NEW** — post-edit runner |
| `.claude/hooks/run_pre_action_check.py` | **NEW** — pre-action gate |
| `Phase_4/tests/test_c10_ml2_leakage.py` | **NEW** — ML2 leakage test (9 tests) |
| `logs/hook_log.csv` | **NEW** — hook outcome log |
| `spark/cleaning.py` | **MODIFIED then RESTORED** — demo edit reverted |
| `Phase_7/C10_Hooks_Event_Driven_Workflows_Report.md` | **NEW** — this file |
| `Phase_7/c10_walkthrough.md` | **NEW** — walkthrough |
| `CLAUDE.md` | **MODIFIED** — added Section 14 (C10 Hooks) |
| `Phase_7/CLAUDE.md` | **MODIFIED** — added Section 14 (C10 Hooks) |

Fixture `Phase_4/tests/fixtures/grain_duplicate_fixture.py` was created and **deleted** as part of the failing demo. It does not persist.

---

## Final Status

All C10 acceptance criteria: **PASS**.

Hooks are live in `.claude/hooks.json`. The repository is in a valid, clean state.
No `data/raw/` files were modified. No destructive database operations were performed.
The C6 permission policy is enforced (not bypassed) by the pre-action gate.
