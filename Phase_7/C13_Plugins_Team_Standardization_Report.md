# C13 — Plugins for Team Standardization Report

## 1. Goal

Standardize engineering rules, slash commands, diagnostic skills, quality hooks, and approved MCP configuration across the NOPIS telecom network engineering team by packaging them into a reusable, self-contained plugin with an established versioning strategy and ownership governance.

---

## 2. Scope: Implemented vs Excluded Activities

| Activity | Description | Status |
| -------- | ----------- | ------ |
| **298** | Identify team-standard assets: rules, skills, commands, hooks, and approved MCP | **Implemented** |
| **299** | Package assets into a reusable Network Engineering Claude Plugin | **Implemented** |
| **300** | Install and use the plugin in a clean project environment | **Excluded (Deferred)** |
| **301** | Verify the same engineering safeguards and commands are available | **Excluded (Deferred)** |
| **302** | Discuss versioning and ownership models | **Implemented** |

> [!NOTE]
> As instructed, Activities **300 and 301 are intentionally excluded** and documented as remaining work.

---

<!-- 298. Identify the team-standard assets: rules, skills, commands, hooks and approved MCP configuration. -->
## 3. Team-Standard Asset Inventory

### Location Summary Mapping

```text id="5a4c9m"
C4 Rules → CLAUDE.md
C7 Commands → .claude/commands/
C8 Skills → .claude/skills/
C10 Hooks → .claude/hooks.json, .claude/hooks/
C12 MCP → .claude/mcp_config.json, .claude/mcp_server.py
```

### Detailed Asset Breakdown

1. **Rules (C4)**: Located in [`CLAUDE.md`](file:///d:/NOPIS/CLAUDE.md). Codifies non-negotiable domain rules:
   - Proportional activity measures (never raw counts or MB).
   - High activity is not confirmed congestion (no capacity/utilization data exists).
   - A grid is a 1–10,000 spatial cell, not a cell tower.
   - Canonical grain is strictly one grid per hourly timestamp (after country-code aggregation).
   - Geographic join key is `properties.cellId` (never `featureid`).
   - Raw data is immutable.
   - Existing APIs are the single source of truth.
2. **Commands (C7)**: Located in [`.claude/commands/`](file:///d:/NOPIS/.claude/commands/) (backed by [`Phase_4/project_commands.py`](file:///d:/NOPIS/Phase_4/project_commands.py)):
   - `/network-health`: Evaluates canonical grain uniqueness across datasets.
   - `/test-api`: Automated execution of FastAPI endpoint test suite.
   - `/check-pipeline`: NOC pipeline health inspection (ingestion logs, rejections, freshness).
   - `/review-anomaly`: Cross-examines rule alerts, ML risk score, and statistical anomaly score.
   - `/explain-grid`: 4-section structured incident triage (`SEVERITY`, `EVIDENCE`, `INTERPRETATION`, `NEXT CHECKS`).
3. **Skills (C8)**: Located in [`.claude/skills/`](file:///d:/NOPIS/.claude/skills/):
   - `network-anomaly-analysis`: Triage of grid activity surges and anomaly metrics without guessing.
   - `pipeline-troubleshooting`: Spark ETL failure investigation and atomic recovery.
   - `telecom-data-quality`: Enforces grain consistency, null checks, and spatial join integrity.
4. **Hooks (C10)**: Located in [`.claude/hooks.json`](file:///d:/NOPIS/.claude/hooks.json) and [`.claude/hooks/`](file:///d:/NOPIS/.claude/hooks/):
   - `run_pre_action_check.py` (`PreToolUse`): Blocks unapproved edits to sensitive Airflow DAGs and pipeline configurations.
   - `run_post_edit_checks.py` (`PostToolUse`): Automatically triggers grain duplicate and ML feature leakage checks after edits in `spark/` or `ml/`.
5. **Approved MCP Configuration (C12)**: Located in [`.claude/mcp_config.json`](file:///d:/NOPIS/.claude/mcp_config.json) and [`.claude/mcp_server.py`](file:///d:/NOPIS/.claude/mcp_server.py):
   - Stdio transport wrapper calling existing FastAPI endpoints (`/network/summary`, `/network/grid/{id}`, `/network/hotspots`, `/network/pipeline/status`).
   - Security boundaries: Read-only (GET exclusively), zero SQL, no direct DB connections, no `.env` access, zero duplicate business logic.

---

<!-- 299. Package them into a project or team plugin. -->
## 4. Plugin Directory Structure

The reusable plugin is packaged under [`plugins/network-engineering/`](file:///d:/NOPIS/plugins/network-engineering/):

```text id="a8jxlg"
plugins/network-engineering/
├── plugin.json
├── README.md
├── rules/
│   └── rules.md
├── commands/
│   ├── check-pipeline.md
│   ├── explain-grid.md
│   ├── network-health.md
│   ├── review-anomaly.md
│   └── test-api.md
├── skills/
│   ├── network-anomaly-analysis/
│   │   └── SKILL.md
│   ├── pipeline-troubleshooting/
│   │   └── SKILL.md
│   └── telecom-data-quality/
│       └── SKILL.md
├── hooks/
│   ├── hooks.json
│   ├── run_post_edit_checks.py
│   └── run_pre_action_check.py
└── mcp/
    ├── mcp_config.json
    └── README.md
```

---

## 5. Asset Mapping Table

| Asset | Source Activity | Original Location | Plugin Location |
| ----- | --------------- | ----------------- | --------------- |
| Project Rules & Domain Terminology | C4 Rules | [`CLAUDE.md`](file:///d:/NOPIS/CLAUDE.md) | [`plugins/network-engineering/rules/rules.md`](file:///d:/NOPIS/plugins/network-engineering/rules/rules.md) |
| `/check-pipeline` command | C7 Commands | [`.claude/commands/check-pipeline.md`](file:///d:/NOPIS/.claude/commands/check-pipeline.md) | [`plugins/network-engineering/commands/check-pipeline.md`](file:///d:/NOPIS/plugins/network-engineering/commands/check-pipeline.md) |
| `/explain-grid` command | C7 Commands | [`.claude/commands/explain-grid.md`](file:///d:/NOPIS/.claude/commands/explain-grid.md) | [`plugins/network-engineering/commands/explain-grid.md`](file:///d:/NOPIS/plugins/network-engineering/commands/explain-grid.md) |
| `/network-health` command | C7 Commands | [`.claude/commands/network-health.md`](file:///d:/NOPIS/.claude/commands/network-health.md) | [`plugins/network-engineering/commands/network-health.md`](file:///d:/NOPIS/plugins/network-engineering/commands/network-health.md) |
| `/review-anomaly` command | C7 Commands | [`.claude/commands/review-anomaly.md`](file:///d:/NOPIS/.claude/commands/review-anomaly.md) | [`plugins/network-engineering/commands/review-anomaly.md`](file:///d:/NOPIS/plugins/network-engineering/commands/review-anomaly.md) |
| `/test-api` command | C7 Commands | [`.claude/commands/test-api.md`](file:///d:/NOPIS/.claude/commands/test-api.md) | [`plugins/network-engineering/commands/test-api.md`](file:///d:/NOPIS/plugins/network-engineering/commands/test-api.md) |
| `network-anomaly-analysis` skill | C8 Skills | [`.claude/skills/network-anomaly-analysis/`](file:///d:/NOPIS/.claude/skills/network-anomaly-analysis/) | [`plugins/network-engineering/skills/network-anomaly-analysis/SKILL.md`](file:///d:/NOPIS/plugins/network-engineering/skills/network-anomaly-analysis/SKILL.md) |
| `pipeline-troubleshooting` skill | C8 Skills | [`.claude/skills/pipeline-troubleshooting/`](file:///d:/NOPIS/.claude/skills/pipeline-troubleshooting/) | [`plugins/network-engineering/skills/pipeline-troubleshooting/SKILL.md`](file:///d:/NOPIS/plugins/network-engineering/skills/pipeline-troubleshooting/SKILL.md) |
| `telecom-data-quality` skill | C8 Skills | [`.claude/skills/telecom-data-quality/`](file:///d:/NOPIS/.claude/skills/telecom-data-quality/) | [`plugins/network-engineering/skills/telecom-data-quality/SKILL.md`](file:///d:/NOPIS/plugins/network-engineering/skills/telecom-data-quality/SKILL.md) |
| Hooks definition | C10 Hooks | [`.claude/hooks.json`](file:///d:/NOPIS/.claude/hooks.json) | [`plugins/network-engineering/hooks/hooks.json`](file:///d:/NOPIS/plugins/network-engineering/hooks/hooks.json) |
| Pre-Action gate runner | C10 Hooks | [`.claude/hooks/run_pre_action_check.py`](file:///d:/NOPIS/.claude/hooks/run_pre_action_check.py) | [`plugins/network-engineering/hooks/run_pre_action_check.py`](file:///d:/NOPIS/plugins/network-engineering/hooks/run_pre_action_check.py) |
| Post-Edit check runner | C10 Hooks | [`.claude/hooks/run_post_edit_checks.py`](file:///d:/NOPIS/.claude/hooks/run_post_edit_checks.py) | [`plugins/network-engineering/hooks/run_post_edit_checks.py`](file:///d:/NOPIS/plugins/network-engineering/hooks/run_post_edit_checks.py) |
| MCP server configuration | C12 MCP | [`.claude/mcp_config.json`](file:///d:/NOPIS/.claude/mcp_config.json) | [`plugins/network-engineering/mcp/mcp_config.json`](file:///d:/NOPIS/plugins/network-engineering/mcp/mcp_config.json) |
| MCP tool & security documentation | C12 MCP | [`.claude/mcp_server.py`](file:///d:/NOPIS/.claude/mcp_server.py) | [`plugins/network-engineering/mcp/README.md`](file:///d:/NOPIS/plugins/network-engineering/mcp/README.md) |

---

## 6. Security-Sensitive Files Excluded

To ensure safe distribution across teams, the plugin strictly excludes all credentials, tokens, and secrets:

* **Excluded Files & Keys**:
  * `.env` file and local environment profiles
  * Database passwords (`DB_PASSWORD`, MySQL connection strings)
  * LLM API keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`)
  * Bearer tokens, passwords, and private certificates
* **Environment Variable Declarations**:
  * In `plugin.json` and `mcp/mcp_config.json`, only the variable name `NOPIS_API_BASE_URL` is referenced (`${NOPIS_API_BASE_URL}`), never secret values.

---

<!-- 302. Discuss versioning and ownership. -->
## 7. Versioning Strategy

The plugin adopts standard Semantic Versioning:

```text id="4s6rgv"
MAJOR.MINOR.PATCH
```

* **MAJOR (x.0.0)**: Breaking changes to non-negotiable project rules, command invocation interfaces, schema structures, or backward-incompatible hook matchers.
* **MINOR (1.x.0)**: New slash commands, diagnostic skills, hooks, or approved MCP tool capabilities added without altering existing contracts.
* **PATCH (1.0.x)**: Small bug fixes, script path resolution corrections, or documentation/explanation updates.

---

## 8. Proposed Ownership Model

| Role | Proposed Responsibility | Appointed Stakeholder |
| ---- | ----------------------- | --------------------- |
| **Plugin Owner** | Overall governance, architecture sign-off, and release publication | Lead Telecom Data Engineer / Architect |
| **Change Proposers** | Propose new skills, slash commands, or hook refinements via PR | All Data, ML, Backend Engineers & NOC Operators |
| **Code Reviewers** | Validate compliance with NOPIS non-negotiables, thin-wrapper constraints, and security | Senior Data Engineer (ETL), NOC Lead (Commands), Platform Engineer (MCP) |
| **Release Approver** | Approves PR merge and cuts Semantic Version Git tag (`vX.Y.Z`) | Plugin Owner |

### Release Workflow:
1. Feature branch created and PR opened.
2. Automated CI validates no secrets/`.env` files exist.
3. Designated reviewer signs off on compliance with NOPIS rules.
4. Plugin Owner approves merge and tags release (`vX.Y.Z`).

---

## 9. Activities 300 and 301 Not Performed

In strict accordance with the project scope:
* **Activity 300** (*Install and use the plugin in a clean project environment*) was **NOT performed**.
* **Activity 301** (*Verify the same engineering safeguards and commands are available*) was **NOT performed**.

Both activities remain designated as future work once a staging testbed environment is provisioned.

---

## 10. Files Created or Modified

### Files Created (Plugin Package & Report)
* [`plugins/network-engineering/plugin.json`](file:///d:/NOPIS/plugins/network-engineering/plugin.json)
* [`plugins/network-engineering/README.md`](file:///d:/NOPIS/plugins/network-engineering/README.md)
* [`plugins/network-engineering/rules/rules.md`](file:///d:/NOPIS/plugins/network-engineering/rules/rules.md)
* [`plugins/network-engineering/commands/check-pipeline.md`](file:///d:/NOPIS/plugins/network-engineering/commands/check-pipeline.md)
* [`plugins/network-engineering/commands/explain-grid.md`](file:///d:/NOPIS/plugins/network-engineering/commands/explain-grid.md)
* [`plugins/network-engineering/commands/network-health.md`](file:///d:/NOPIS/plugins/network-engineering/commands/network-health.md)
* [`plugins/network-engineering/commands/review-anomaly.md`](file:///d:/NOPIS/plugins/network-engineering/commands/review-anomaly.md)
* [`plugins/network-engineering/commands/test-api.md`](file:///d:/NOPIS/plugins/network-engineering/commands/test-api.md)
* [`plugins/network-engineering/skills/network-anomaly-analysis/SKILL.md`](file:///d:/NOPIS/plugins/network-engineering/skills/network-anomaly-analysis/SKILL.md)
* [`plugins/network-engineering/skills/pipeline-troubleshooting/SKILL.md`](file:///d:/NOPIS/plugins/network-engineering/skills/pipeline-troubleshooting/SKILL.md)
* [`plugins/network-engineering/skills/telecom-data-quality/SKILL.md`](file:///d:/NOPIS/plugins/network-engineering/skills/telecom-data-quality/SKILL.md)
* [`plugins/network-engineering/hooks/hooks.json`](file:///d:/NOPIS/plugins/network-engineering/hooks/hooks.json)
* [`plugins/network-engineering/hooks/run_pre_action_check.py`](file:///d:/NOPIS/plugins/network-engineering/hooks/run_pre_action_check.py)
* [`plugins/network-engineering/hooks/run_post_edit_checks.py`](file:///d:/NOPIS/plugins/network-engineering/hooks/run_post_edit_checks.py)
* [`plugins/network-engineering/mcp/mcp_config.json`](file:///d:/NOPIS/plugins/network-engineering/mcp/mcp_config.json)
* [`plugins/network-engineering/mcp/README.md`](file:///d:/NOPIS/plugins/network-engineering/mcp/README.md)
* [`Phase_7/C13_Plugins_Team_Standardization_Report.md`](file:///d:/NOPIS/Phase_7/C13_Plugins_Team_Standardization_Report.md)

### Files Modified / Relocated
* Moved `Phase_7/mcp_server.py` → [`.claude/mcp_server.py`](file:///d:/NOPIS/.claude/mcp_server.py) (per explicit user instruction)
* Updated [`.claude/mcp_config.json`](file:///d:/NOPIS/.claude/mcp_config.json) (pointed args to `.claude/mcp_server.py`)
* Updated [`Phase_4/tests/test_c12_mcp_server.py`](file:///d:/NOPIS/Phase_4/tests/test_c12_mcp_server.py) (updated imports and mock patch paths; 30/30 tests PASS)

---

## 11. Final Status

* **Status**: **Complete & Validated**
* All team-standard assets (C4, C7, C8, C10, C12) identified, organized, and packaged.
* NOPIS domain rules preserved.
* Secrets and `.env` excluded.
* Versioning (`MAJOR.MINOR.PATCH`) and proposed ownership model established.
* Activities 300 and 301 confirmed not performed.
