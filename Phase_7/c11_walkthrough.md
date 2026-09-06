# C11 — Checkpoints & Safe Rollback: Walkthrough

## Overview

In **C11**, we conducted a controlled operational experiment on the NOPIS network anomaly detection rules:
1. Created a deterministic Git checkpoint before making any changes.
2. Formulated and tested a controlled threshold adjustment from **50.0% to 40.0%** in `Phase_4/services.py` (`get_rising_grids`), nearly doubling flagged grids (+93.2%).
3. Measured actual before-and-after operational impacts: alert volume, top-20 composition, NP3 agreement, and automated tests.
4. Identified regressions based on evidence (alert fatigue, lower signal convergence).
5. Provided evidence-backed KEEP / ROLLBACK recommendations to the learner.
6. The learner selected **ROLLBACK**, which was executed cleanly and verified with zero data loss or residue.

---

## 1. Checkpoint Creation (Task 286)

- **Checkpoint Tag**: `c11-checkpoint-pre-experiment`
- **Commit Object SHA**: `7790f8180b7c2a7baca4982873f34479970f4b4a`
- **Pre-Experiment Baseline**:
  - Full test suite passed (66/66 tests).
  - Statistical Anomaly Alert Volume (`anomaly_score >= 50.0%`): **161 grids** at `2013-11-07 17:30:00`.
  - NP3 Rule Alert Volume (`total_activity >= 300`): **3,691 alerts** at `2013-11-07 23:00:00`.
  - NP3 Agreement: **63.13%** (6,268 / 9,929 grids).

---

## 2. Controlled Anomaly Rule Experiment (Task 287)

- **File Changed**: `Phase_4/services.py`
- **Modification**: Lowered `ANOMALY_HIGH_THRESHOLD` from `50.0%` to `40.0%` in `get_rising_grids()`.
- **Constraint Compliance**:
  - `data/raw/` untouched (remained strictly immutable).
  - No database schema alterations or destructive queries.
  - ML model, feature engineering, and NP3 rule untouched.

---

## 3. Operational Comparison & Verification (Task 288)

| Metric | Baseline (50%) | Experiment (40%) | Post-Rollback (50%) |
| :--- | :--- | :--- | :--- |
| **Active Anomaly Grids** | 161 grids | 311 grids (+93.2%) | **161 grids** |
| **Total Historical Flagged** | 30,692 rows | 46,037 rows (+50.0%) | **30,692 rows** |
| **NP3 Rule Alerts** | 3,691 alerts | 3,691 alerts (0%) | **3,691 alerts** |
| **NP3 Agreement Rate** | 63.13% | 62.69% (-0.44%) | **63.13%** |
| **Top 20 Attention List** | Stable | Stable | **Stable** |
| **Tests Passing** | 66 / 66 | 66 / 66 | **66 / 66** |

---

## 4. Regression Analysis (Task 289)

- **Evidence**:
  - Flagged anomaly count surged by +93.2% (150 additional grids).
  - 64.7% (97 / 150) of newly flagged grids had total activity under 300 proportional units.
  - Signal agreement with NP3 heuristic rules decreased by -0.44%.
- **Interpretation**:
  - Low baseline activity cells experience high percentage deviations without high absolute traffic.
  - High alert volume increases triage overhead without providing actionable operational benefits.

---

## 5. Safe Rollback Execution (Task 290)

- Learner issued **ROLLBACK**.
- Restored `Phase_4/services.py` directly from checkpoint `c11-checkpoint-pre-experiment`:
  ```powershell
  git checkout c11-checkpoint-pre-experiment -- Phase_4/services.py
  ```
- Code verification confirmed `git diff` against checkpoint is **0 bytes**.
- Operational metrics verification confirmed anomaly alert volume returned to **161 grids** and agreement returned to **63.13%**.
- Regression tests confirmed **25/25 passing**.
