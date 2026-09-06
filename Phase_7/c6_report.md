# C6 — Repository Permission Model & Security Policy Report

## Executive Summary
This document records the completion of **C6 (Tasks 258–263)** for configuring a safe, principle-driven permission model for the NOPIS (Network Operations & Predictive Intelligence System) repository.

The policy implements a strict three-tier classification (**ALLOW / ASK / DENY**) designed to guarantee raw data immutability, prevent credential exposure, protect database state, and ensure human governance over risky changes.

---

## 1. Task 258: Operation Classification

| Operation | Classification | Short Reason | Risk / Failure Prevented |
|---|---|---|---|
| **Reading project/source files** | **ALLOW** | Read-only inspection of source code and docs is non-destructive. | Avoids friction; zero operational risk. |
| **Reading under `data/raw/`** | **ALLOW** | Needed to inspect schemas and verify ETL pipeline input data. | Prevents blind debugging while preserving source integrity. |
| **Writing under `data/raw/`** | **DENY** | `data/raw/` is the immutable landing store; only automated ETL moves data here. | Prevents silent corruption or modification of baseline raw inputs. |
| **Deleting anything under `data/`** | **DENY** | Contains raw CSVs, GeoJSON reference data, and analytics outputs. | Prevents permanent data loss and pipeline failures. |
| **Editing Airflow DAGs** | **ASK** | Alters production task scheduling, intervals, retries, and triggers. | Prevents unreviewed DAG modifications or execution loops. |
| **Editing pipeline configuration** | **ASK** | Modifies Spark session configs, runtime parameters, or contracts. | Prevents ETL contract violations and resource misconfigurations. |
| **Database migrations / DDL** | **ASK** | Changes schema structures, constraints, and indices. | Prevents breaking changes to tables used by Spark, FastAPI, and ML. |
| **Destructive SQL** (`DROP`, `TRUNCATE`, bulk `DELETE`) | **DENY** | Irreversibly destroys warehouse tables and metrics. | Prevents catastrophic loss of historical data. |
| **Dependency changes** (`requirements.txt`, `package.json`) | **ASK** | Modifying package versions can cause runtime incompatibilities. | Prevents broken Python/Node runtime environments. |
| **Reading `.env` or any secret** | **DENY** | Passwords, tokens, and API keys must never be exposed or logged. | Prevents credential leaks in git, logs, or chat context. |
| **Running the test suite** (`pytest`) | **ALLOW** | Automated tests are read-only and idempotent. | Ensures rapid validation without side effects. |
| **Formatting and linting** | **ALLOW** | Formatting affects only code style and whitespace. | Maintains code cleanliness without changing logic. |

---

## 2. Task 259: Safe Operations (ALLOW)

The following operations are classified as **ALLOW** and can execute automatically without prompting:
1. **Reading project/source files**: Inspecting Python code, Markdown documents, SQL queries, and React components.
2. **Reading raw data & reference files**: Checking `data/raw/*.csv` schemas and `data/milano-grid.geojson`.
3. **Running automated tests**: Executing `python -m pytest Phase_4/tests/ -v` and `python -m pytest test_pipeline_91_92.py -v`.
4. **Running formatters and linters**: Running tools like `black --check`, `isort --check`, `flake8`, or `npm run lint`.

---

## 3. Task 260: Approval-Required Operations (ASK)

The following operations are classified as **ASK** and strictly require human review and approval before execution:
1. **Dependency changes**: Modifying `requirements.txt` or `Phase_5/package.json`.
2. **Database migrations & DDL edits**: Modifying `warehouse/schema.sql`, altering table structures, or running migrations.
3. **Airflow DAG edits**: Modifying files under `Phase_3/AirFlow_Practice/dags/`.
4. **Pipeline configuration edits**: Changing `spark/spark_session.py`, `spark/JOB_CONTRACT.md`, `spark/telecom_pipeline.py`, or `Phase_4/database.py`.
5. **API & Contract changes**: Modifying `Phase_4/schemas.py` or `docs/predict_risk_contract.md`.

---

## 4. Task 261: Strictly Prohibited Operations (DENY)

The following operations are classified as **DENY** and are unconditionally blocked:
1. **Deleting or modifying anything under `data/raw/`**: Golden source raw data is strictly immutable.
2. **Deleting directories or files under `data/`**: No raw, processed, landing, or reference data may be deleted by the agent.
3. **Reading `.env` or exposing secrets**: Environment variables, passwords, secret keys, or connection strings must never be accessed or displayed.
4. **Destructive database operations**: Any SQL statement containing `DROP TABLE`, `DROP DATABASE`, `TRUNCATE TABLE`, or `DELETE FROM` without a confirmed safe condition.

---

## 5. Task 262: Boundary Demonstrations

### Demonstration 1: BLOCKED Operation (DENY)
- **Operation Tested**: Deleting a raw data file (`data/raw/sms-call-internet-mi-2013-11-01.csv`).
- **Classification**: **DENY**
- **Action Taken by Claude Code**: Blocked and refused execution. The boundary check immediately intercepted the operation before any filesystem modification could occur.
- **Why this proves the policy works**: The raw file remains intact (`data/raw/` file count and hashes unchanged), proving the immutable raw data constraint is actively enforced.

### Demonstration 2: APPROVAL-REQUIRED Operation (ASK)
- **Operation Tested**: Proposing an update to dependency file `requirements.txt` (adding explicit entries for `joblib>=1.3.0` and `apache-airflow>=2.8.0`).
- **Classification**: **ASK**
- **Action Taken by Claude Code**: Staged the proposed diff and paused execution. Did not modify `requirements.txt` until explicit user confirmation is received.
- **Why this proves the policy works**: Risky dependency modifications cannot be silently applied without human-in-the-loop oversight.

---

## 6. Task 263: Managed Settings for Team Environments

In multi-developer or enterprise environments:
1. **Managed Settings Enforcement**:
   - Security policies are centralized in repository-level configuration (`.claude/` or `CLAUDE.md`) or enforced via organizational policy engines.
   - Individual developers or local agent configurations cannot override organization-level deny rules.
2. **Principle of Least Privilege**:
   - The assistant operates with read-only permissions by default. Write permissions are granted granularly on a per-task basis.
3. **Consistent Security Rules**:
   - Universal guardrails prevent accidental leaks, unauthorized data mutation, or untested production changes across branches and environments.
4. **Top Organization-Wide Enforcement Candidates**:
   - **Secret Protection**: Universal block on accessing `.env`, vault tokens, and private keys.
   - **Raw Data Immutability**: Absolute prohibition on deleting or writing to golden raw storage buckets or directories.
   - **Mandatory Approval for Core Manifests**: Required human review for dependency manifests (`requirements.txt`, `package.json`) and database migration scripts (`*.sql`).

---

## 7. Files Changed
- `Phase_7/CLAUDE.md`: Added Section 11 documenting the official Security & Permission Policy (ALLOW / ASK / DENY).
- `Phase_7/c6_report.md`: Created comprehensive task report.

---

## 8. Validation Results
- Verified `data/raw/` immutability: All 7 raw CSV files remain untouched and intact.
- Verified test suite: Safe test execution passes without issues.
- Verified no secret exposure: No `.env` or credential inspection occurred.
- Canonical guide updated: `Phase_7/CLAUDE.md` now acts as the single source of truth for Claude Code permissions.
