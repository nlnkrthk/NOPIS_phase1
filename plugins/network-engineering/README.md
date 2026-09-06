<!-- 299. Package them into a project or team plugin. -->
# Network Engineering Claude Plugin

The **Network Engineering Claude Plugin** bundles team-standard engineering rules, slash commands, diagnostic skills, quality hooks, and approved Model Context Protocol (MCP) server configurations for the NOPIS (Network Operations & Predictive Intelligence System) platform.

This plugin standardizes operational procedures across all engineers working on telecom telemetry, anomaly detection, batch ETL, and REST APIs.

---

## 1. Plugin Architecture & Inventory

The plugin packages or references 5 core engineering asset types:

```text
Network Engineering Claude Plugin
│
├── Project Rules      → C4 (rules/rules.md)
├── Skills             → C8 (skills/)
├── Commands           → C7 (commands/)
├── Hooks              → C10 (hooks/)
└── MCP Configuration  → C12 (mcp/)
```

### Origin Mapping

| Plugin Asset | Source Activity | Original Repository Location | Purpose |
| ------------ | --------------- | ---------------------------- | ------- |
| `rules/rules.md` | C4 Rules | `CLAUDE.md` | Non-negotiable domain rules, terminology, and architecture |
| `commands/check-pipeline.md` | C7 Commands | `.claude/commands/check-pipeline.md` | Inspect ETL logs, rejections, and warehouse freshness |
| `commands/explain-grid.md` | C7 Commands | `.claude/commands/explain-grid.md` | Structured 4-section grid incident triage |
| `commands/network-health.md` | C7 Commands | `.claude/commands/network-health.md` | Canonical `(grid_id, timestamp)` grain validation |
| `commands/review-anomaly.md` | C7 Commands | `.claude/commands/review-anomaly.md` | Cross-examination of alerts, ML risk, and anomalies |
| `commands/test-api.md` | C7 Commands | `.claude/commands/test-api.md` | Deterministic API test suite execution |
| `skills/network-anomaly-analysis` | C8 Skills | `.claude/skills/network-anomaly-analysis/` | Evidence-based anomaly investigation |
| `skills/pipeline-troubleshooting` | C8 Skills | `.claude/skills/pipeline-troubleshooting/` | Spark ETL failure diagnosis & recovery |
| `skills/telecom-data-quality` | C8 Skills | `.claude/skills/telecom-data-quality/` | Data grain & schema quality assurance |
| `hooks/hooks.json` | C10 Hooks | `.claude/hooks.json` | Hook event declarations (PreToolUse & PostToolUse) |
| `hooks/run_pre_action_check.py` | C10 Hooks | `.claude/hooks/run_pre_action_check.py` | Pre-edit safety gate on sensitive DAGs & schemas |
| `hooks/run_post_edit_checks.py` | C10 Hooks | `.claude/hooks/run_post_edit_checks.py` | Post-edit automated grain & feature leakage tests |
| `mcp/mcp_config.json` | C12 MCP | `.claude/mcp_config.json` | Approved MCP registration schema (stdio transport) |
| `mcp/README.md` | C12 MCP | `.claude/mcp_server.py` | MCP tool specifications and security boundary documentation |

---

## 2. Preserved NOPIS Engineering Rules

All assets strictly preserve the core NOPIS engineering and data principles:

1. **Activity Values are Measures, Not Counts or MB**: `total_activity`, `internet_activity`, etc., are proportional activity measures, not raw call counts, SMS counts, or data volume (MB).
2. **High Activity is Not Confirmed Congestion**: High or elevated activity must never be described as "congestion" or "bandwidth exhaustion" without actual capacity/utilization telemetry.
3. **Grid is a Geographic Cell, Not a Tower**: A grid is a 1–10,000 spatial square in Milan, never an antenna, base station, or cellular tower.
4. **Canonical Analytics Grain**: Exactly **one grid per hourly timestamp** after country-code aggregation.
5. **Geographic Joins**: Always join GeoJSON geometry using `properties.cellId -> grid_id` (never `featureid`).
6. **Raw Data Immutability**: Raw landing and raw CSV data are strictly immutable.
7. **Existing APIs as Single Source of Truth**: MCP tools and commands call existing FastAPI endpoints (`http://127.0.0.1:8000`), never reimplementing business logic.
8. **Thin Wrapper MCP Design**: MCP does not compute anomaly scores, execute SQL queries, or connect directly to databases.
9. **Missing Evidence Must Be Reported**: If required metrics are missing, agents must report `INSUFFICIENT EVIDENCE`, never fabricate or guess numbers.

---

## 3. Security Boundaries & Excluded Secrets

To safeguard the environment and maintain security compliance:

* **Strictly Excluded**:
  * `.env` files
  * Database passwords (`DB_PASSWORD`, MySQL connection strings)
  * LLM API keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`)
  * Bearer tokens, passwords, and service account credentials
* **Environment Variable Handling**:
  * MCP configuration specifies only the environment variable name (`NOPIS_API_BASE_URL`), never hard-coded credentials or secrets.

---

<!-- 302. Discuss versioning and ownership. -->
## 4. Versioning Strategy & Ownership Model

### Versioning Strategy (Semantic Versioning)

The plugin follows standard Semantic Versioning: `MAJOR.MINOR.PATCH`

* **MAJOR (x.0.0)**:
  * Breaking changes to non-negotiable project rules.
  * Incompatible changes to command syntax, slash command names, or outputs.
  * Changes to plugin directory structure or required environment variable contracts.
  * Incompatible hook signature or matcher modifications.
* **MINOR (1.x.0)**:
  * Adding new slash commands (e.g., `/export-report`, `/geo-cluster`).
  * Adding new skills or troubleshooting playbooks.
  * Adding new hooks or approved MCP read-only tool wrappers.
  * Backwards-compatible rule additions or documentation enhancements.
* **PATCH (1.0.x)**:
  * Bug fixes in hook execution scripts or path resolution.
  * Clarifications in skill prompts, markdown descriptions, or examples.
  * Minor configuration tuning (timeouts, error message wording).

### Proposed Ownership Model

| Role | Responsibility | Appointed Stakeholder (Proposed) |
| ---- | -------------- | -------------------------------- |
| **Plugin Owner** | Overall governance, architecture alignment, and release sign-off | Lead Telecom Data Engineer / NOC System Architect |
| **Contributors** | Propose improvements, bug fixes, new skills, or commands | All Data Engineers, ML Engineers, Backend Engineers, NOC Operators |
| **Reviewers** | Review PRs against NOPIS rules, thin-wrapper constraints, and security standards | Senior Data Engineer (ETL/Hooks), NOC Lead (Commands), Platform Engineer (MCP) |
| **Release Approver** | Approves PR merge, cuts Git release tags, and publishes version updates | Plugin Owner |

#### Change Proposal and Release Workflow:
1. **Proposal**: A team member creates a feature branch and submits a Pull Request detailing the proposed change.
2. **Automated Verification**: CI runs linting, path checks, and validates that no secrets or `.env` files are present.
3. **Peer Review**: At least one designated reviewer evaluates the PR against NOPIS rules and thin-wrapper constraints.
4. **Approval & Tagging**: The Plugin Owner approves the PR, merges to `main`, and tags the commit (`vX.Y.Z`).
5. **Distribution**: Updated plugin is synchronized or installed across team workspaces.
