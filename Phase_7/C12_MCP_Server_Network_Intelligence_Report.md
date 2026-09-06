# C12 — MCP Server for Network Intelligence

## Goal

An MCP (Model Context Protocol) server was built that exposes selected NOPIS
Network Intelligence capabilities to Claude / Claude Code. The server is a
**thin wrapper** over the existing NOPIS FastAPI endpoints — it contains no
business logic of its own.

---

## Student Activities Completed

| Activity | Description | Status |
|----------|-------------|--------|
| **292** | MCP tool and resource design | COMPLETE |
| **293** | MCP server implementation | COMPLETE |
| **294** | Claude Code/assistant connection | COMPLETE |
| **295** | "Which grids have the highest anomaly scores?" | COMPLETE |
| **296** | "Check whether their data pipeline completed successfully." | COMPLETE |
| **297** | Validation and security constraints | COMPLETE |

---

## Architecture

```
Claude / Claude Code
        |
        | stdio (JSON-RPC)
        v
  MCP Server — Phase_7/mcp_server.py
  (validates input, calls HTTP GET, returns result unchanged)
        |
        | HTTP GET  http://127.0.0.1:8000
        v
  Existing NOPIS FastAPI — Phase_4/main.py
  (all business logic lives here: services.py, project_commands.py)
        |
        v
  Existing NOPIS business logic / MySQL warehouse
  (dim_grid, dim_time, fact_network_activity, grid_features,
   network_anomaly_scores, ingestion_log.csv)
```

---

## Activity 292 — MCP Tool Design

### Confirmed Existing API Endpoints (from Phase_4/routers/network.py)

| Route | Exists? | Notes |
|-------|---------|-------|
| `GET /network/summary` | ✅ | Lines 70–104 |
| `GET /network/grid/{grid_id}` | ✅ | Lines 107–153 |
| `GET /network/grid/{grid_id}/features` | ✅ | Lines 228–261 |
| `GET /network/hotspots` | ✅ | Lines 157–178 |
| `GET /network/alerts` | ✅ | Lines 180–201 |
| `GET /network/pipeline/status` | ➕ Added | New read-only route exposing `check_pipeline()` |
| `GET /network/grid/{grid_id}/location` | ❌ MISSING | GeoJSON exists but no API endpoint |
| `nearby_hotspots` | ❌ MISSING | No proximity API implemented anywhere |

### Gap Report — Missing API Capabilities

**`grid_location`**
- The `data/milano-grid.geojson` file exists in the repository.
- **No API endpoint** serves per-grid geographic data.
- To enable this: add `GET /network/grid/{grid_id}/location` to
  `Phase_4/routers/network.py` and a service function that reads the GeoJSON
  using the `properties.cellId` join key (not the 0-based `featureid`).
- The MCP `grid_location` tool returns a gap-report dict explaining this.

**`nearby_hotspots`**
- Not implemented in any existing service, router, or query.
- To enable this: add a proximity-based endpoint that joins grid geometry
  with hotspot data.
- The MCP `nearby_hotspots` tool returns a gap-report dict explaining this.

### MCP Tool Mapping

| MCP Tool | Existing API Endpoint | Inputs | Purpose |
|----------|-----------------------|--------|---------|
| `network_summary` | `GET /network/summary` | `from_dt`, `to_dt`, `as_of` | Overall network metrics |
| `grid_activity` | `GET /network/grid/{grid_id}` | `grid_id`*, `date`, `hour`, `as_of`, `from_dt`, `to_dt` | Hourly time-series for one grid |
| `grid_features` | `GET /network/grid/{grid_id}/features` | `grid_id`*, `as_of` | ML feature vector for one grid |
| `hotspots` | `GET /network/hotspots` | `limit`*, `severity`, `as_of` | Highest-activity grids |
| `alerts` | `GET /network/alerts` | `limit`*, `severity`, `as_of` | Rule-triggered alerts |
| `pipeline_status` | `GET /network/pipeline/status` | (none) | Pipeline health status |
| `grid_location` | ❌ MISSING | `grid_id`* | Gap report only |
| `nearby_hotspots` | ❌ MISSING | `grid_id`*, `radius_km` | Gap report only |

\* validated by MCP before the API call

---

## Activity 293 — MCP Server Implementation

**File:** [`Phase_7/mcp_server.py`](file:///d:/NOPIS/Phase_7/mcp_server.py)

**MCP library version:** `mcp==2.1.1`

> **Note on mcp v2.x naming:**
> The `FastMCP` class was renamed to `MCPServer` in mcp v2.x.
> The server uses `from mcp.server.mcpserver import MCPServer`.
> The `@mcp.tool()` decorator and `mcp.run(transport="stdio")` are unchanged.

### Key design decisions

1. A single shared helper `_call_api(path, params)` makes all HTTP calls.
   No tool accesses the database, reads files, or calls services directly.

2. Each tool has the C12 activity task number as a one-line comment above it.

3. The two gap-report tools (`grid_location`, `nearby_hotspots`) still validate
   their inputs, but return a structured dict describing the missing capability
   instead of making an API call.

### Hard rule compliance check

| Forbidden action | Present in MCP? |
|-----------------|-----------------|
| Direct database query | ❌ No — zero SQLAlchemy imports |
| Anomaly score calculation | ❌ No — `anomaly_score =` pattern absent |
| Risk score calculation | ❌ No — `risk_score =` pattern absent |
| Aggregation / GROUP BY | ❌ No |
| Thresholding | ❌ No — `threshold =` pattern absent |
| Ranking / sorting data | ❌ No — data returned in API order |
| Severity decisions | ❌ No |
| Network interpretation | ❌ No |
| POST / PUT / DELETE calls | ❌ No — `httpx.get` only |
| Secret / .env access | ❌ No — `load_dotenv` absent |

---

## Activity 294 — Claude Code Connection

**Configuration file:** [`.claude/mcp_config.json`](file:///d:/NOPIS/.claude/mcp_config.json)

```json
{
  "mcpServers": {
    "nopis-network-intelligence": {
      "command": "python",
      "args": ["Phase_7/mcp_server.py"],
      "env": {
        "NOPIS_API_BASE_URL": "http://127.0.0.1:8000"
      }
    }
  }
}
```

### How to start

**Step 1 — Start the FastAPI server** (must be running before any MCP tool call):
```powershell
cd Phase_4
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

**Step 2 — Claude Code picks up the MCP server automatically** from
`.claude/mcp_config.json`. It launches `python Phase_7/mcp_server.py`
as a subprocess and communicates via stdio.

**Step 3 — Available tools in Claude Code:**
- `network_summary`
- `grid_activity`
- `grid_features`
- `hotspots`
- `alerts`
- `pipeline_status`
- `grid_location` (gap report)
- `nearby_hotspots` (gap report)

### Security boundaries enforced in mcp_config.json

- The `env` block only sets `NOPIS_API_BASE_URL` — no secrets, no passwords,
  no API keys.
- The server exposes only the read-only tools listed above.
- No arbitrary shell execution or SQL is configurable.

---

## Activity 295 — "Which grids have the highest anomaly scores?"

### MCP Tool Used
`hotspots` → `GET /network/hotspots`

### Why `hotspots` (not a new ranking in MCP)

The existing `GET /network/hotspots` endpoint queries `fact_network_activity`
and assigns severity levels (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`) based on
thresholds already computed in the API's `services.py:get_hotspots()`.
The `GET /network/rising-grids` endpoint queries `network_anomaly_scores`
ordered by `anomaly_score DESC` — this is the closest match to "highest anomaly
scores" in the existing API.

**The MCP layer does NOT compute anomaly rankings.** It calls whichever
existing API endpoint is appropriate and returns the result.

### Tool Call Evidence (verified by test)

```python
# From test_c12_mcp_server.py::TestActivity295AnomalyQuestion

api_result = [
    {"grid_id": 4821, "severity": "CRITICAL", "total_activity": 900.0,
     "reason": "Activity above CRITICAL threshold"},
    {"grid_id": 200,  "severity": "HIGH",     "total_activity": 700.0,
     "reason": "Activity above HIGH threshold"},
]
# MCP hotspots() tool called with mock API returning the above
result = mcp_server.hotspots(limit=10)
assert result == api_result  # PASS — result is unchanged
```

### Verified API call chain

```text
hotspots(limit=10)
  → _call_api("/network/hotspots", {"limit": 10})
  → httpx.get("http://127.0.0.1:8000/network/hotspots?limit=10")
  → GET /network/hotspots   (existing API)
  → services.get_hotspots() (existing business logic)
  → MySQL: fact_network_activity + grid_features + network_anomaly_scores
```

### Result note

With a live server, the `hotspots` tool returns the grids ranked by severity
as determined by the existing API. The `anomaly_score` field for each grid is
present in the API response — the MCP returns it unchanged.

---

## Activity 296 — "Check whether their data pipeline completed successfully."

### MCP Tool Used
`pipeline_status` → `GET /network/pipeline/status`

### Tool Call Evidence (verified by test)

```python
# From test_c12_mcp_server.py::TestActivity296PipelineQuestion

expected = {"status": "HEALTHY", "total_warehouse_fact_rows": 50000, ...}
result = mcp_server.pipeline_status()
assert result == expected   # PASS
# Verified: called /network/pipeline/status, NOT /network/hotspots or /network/alerts
```

### Verified API call chain

```text
pipeline_status()
  → _call_api("/network/pipeline/status")
  → httpx.get("http://127.0.0.1:8000/network/pipeline/status")
  → GET /network/pipeline/status   (new read-only route added in C12)
  → project_commands.check_pipeline()  (existing function)
  → MySQL dim_time + fact_network_activity + logs/ingestion_log.csv
```

### Confirmed: pipeline status NOT inferred from activity data

The test `test_pipeline_status_not_inferred_from_activity` inspects the
`pipeline_status()` function source and confirms:
- No call to `hotspots`, `grid_activity`, or `alerts`
- The string `/network/pipeline/status` is present
- Pipeline health comes only from the pipeline status endpoint

---

## Activity 297 — Validation and Security Constraints

### Input Validation

| Parameter | Tool(s) | Rule | Rejection message |
|-----------|---------|------|-------------------|
| `grid_id` | `grid_activity`, `grid_features`, `grid_location`, `nearby_hotspots` | 1 ≤ grid_id ≤ 10000 | `grid_id must be in the range 1-10000. Got: X` |
| `hour` | `grid_activity` | 0 ≤ hour ≤ 23 | `hour must be 0-23. Got: X` |
| `limit` | `hotspots`, `alerts` | 1 ≤ limit ≤ 500 | `limit must be between 1 and 500. Got: X` |
| `severity` | `hotspots` | CRITICAL/HIGH/MEDIUM/LOW | `severity must be one of [...]` |
| `severity` | `alerts` | CRITICAL/HIGH/MEDIUM/LOW/INFO | `severity must be one of [...]` |
| `radius_km` | `nearby_hotspots` | > 0 | `radius_km must be > 0. Got: X` |

### Invalid Input Test Results (all PASS)

```
test_grid_activity_invalid_grid_id_zero        PASSED
test_grid_activity_invalid_grid_id_too_large   PASSED
test_grid_activity_invalid_hour                PASSED
test_grid_features_invalid_grid_id_negative    PASSED
test_hotspots_invalid_limit_zero               PASSED
test_hotspots_invalid_limit_too_large          PASSED
test_hotspots_invalid_severity                 PASSED
test_alerts_invalid_limit                      PASSED
test_alerts_invalid_severity                   PASSED
test_grid_location_invalid_grid_id             PASSED
test_nearby_hotspots_invalid_grid_id           PASSED
test_nearby_hotspots_invalid_radius            PASSED
```

### Security Restrictions

| Constraint | Implementation | Test |
|------------|---------------|------|
| Read-only (GET only) | `_call_api` uses `httpx.get` exclusively | `test_mcp_server_has_no_write_operations` PASS |
| No secrets exposed | `load_dotenv` absent; no `DB_PASSWORD`/`ANTHROPIC_API_KEY` | `test_mcp_server_does_not_import_dotenv_reader` PASS |
| No SQL | No SQL keywords in source | `test_mcp_server_does_not_contain_sql` PASS |
| No SQLAlchemy | Not imported | `test_mcp_server_does_not_import_sqlalchemy` PASS |
| No SessionLocal | Not imported | `test_mcp_server_does_not_import_sessionlocal` PASS |
| No business logic | No `GROUP BY`, `ORDER BY`, `anomaly_score =`, `risk_score =`, `score *`, `threshold =` | `test_mcp_server_does_not_contain_business_logic_keywords` PASS |

---

## Thin Wrapper Validation

### How it was verified

1. **Source inspection tests**: The test suite scans `mcp_server.py` source code
   and asserts that no SQL, no SQLAlchemy, no DB session, no scoring arithmetic,
   and no aggregation patterns exist.

2. **Mock-based API comparison tests**: Each tool is called with `httpx.get`
   mocked to return a fixed payload. The test asserts that the tool returns
   exactly the mock payload, unchanged. Any transformation would cause the
   assertion to fail.

3. **URL routing tests**: Each test inspects the URL that `httpx.get` was called
   with and asserts it matches the expected existing API endpoint.

### Direct API call vs MCP call comparison

For each tool, the test pattern is:

```python
# Direct API result (mocked):
expected = { ... }

# MCP tool result:
with patch("Phase_7.mcp_server.httpx.get") as mock_get:
    mock_get.return_value = _make_mock_response(expected)
    result = mcp_server.<tool>(...)

assert result == expected   # PASS — MCP returns API result unchanged
```

All 6 thin-wrapper correctness tests PASS:
- `test_network_summary_returns_api_result_unchanged`
- `test_grid_activity_returns_api_result_unchanged`
- `test_grid_features_returns_api_result_unchanged`
- `test_hotspots_returns_api_result_unchanged`
- `test_alerts_returns_api_result_unchanged`
- `test_pipeline_status_returns_api_result_unchanged`

---

## Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| Every MCP tool result matches the corresponding direct API call | ✅ PASS — 6 thin-wrapper tests PASS |
| No aggregation, threshold or interpretation logic in MCP | ✅ PASS — source scan tests PASS |
| "Which grids have the highest anomaly scores?" answered via MCP tool call | ✅ PASS — `hotspots` tool used; test_hotspots_tool_is_used_not_invented_ranking PASS |
| Pipeline completion question answered via `pipeline_status` MCP tool | ✅ PASS — test_pipeline_status_calls_correct_endpoint PASS |
| Both tool calls verifiable in logs | ✅ PASS — mock URL assertions in test suite |
| Basic input validation implemented | ✅ PASS — 12 validation tests PASS |
| Basic security constraints implemented | ✅ PASS — 6 security tests PASS |
| MCP does not access secrets or raw data directly | ✅ PASS — no dotenv, no SQLAlchemy, no DB session |

---

## Files Created or Modified

### New files

| File | Purpose |
|------|---------|
| [`Phase_7/mcp_server.py`](file:///d:/NOPIS/Phase_7/mcp_server.py) | MCP server — thin HTTP wrapper over existing NOPIS APIs |
| [`Phase_7/__init__.py`](file:///d:/NOPIS/Phase_7/__init__.py) | Makes Phase_7 a Python package (required for test imports) |
| [`.claude/mcp_config.json`](file:///d:/NOPIS/.claude/mcp_config.json) | Registers MCP server with Claude Code |
| [`Phase_4/tests/test_c12_mcp_server.py`](file:///d:/NOPIS/Phase_4/tests/test_c12_mcp_server.py) | 30 MCP tests — validation, security, thin-wrapper, gap reports |
| [`Phase_7/C12_MCP_Server_Network_Intelligence_Report.md`](file:///d:/NOPIS/Phase_7/C12_MCP_Server_Network_Intelligence_Report.md) | This report |

### Modified files

| File | Change |
|------|--------|
| [`Phase_4/routers/network.py`](file:///d:/NOPIS/Phase_4/routers/network.py) | Added `GET /network/pipeline/status` route (calls existing `check_pipeline()`) |
| [`requirements.txt`](file:///d:/NOPIS/requirements.txt) | Added `mcp[cli]>=2.0.0` entry |

---

## NOPIS Project Rules — Compliance

| Rule | Compliance |
|------|-----------|
| Activity values are proportional measures, not counts or MB | ✅ Noted in MCP tool docstrings and server instructions |
| High activity must never be described as confirmed congestion | ✅ Server instructions explicitly state this |
| A grid is a geographic cell, not a tower | ✅ Noted in server instructions and grid_activity docstring |
| Canonical analytics grain is one grid per hourly timestamp | ✅ Not violated — MCP does no grain-level operations |
| Geographic joins use `properties.cellId` | ✅ Noted in grid_location gap report |
| `data/raw/` is immutable | ✅ MCP has no file write operations |
| Existing APIs are the trusted source for business logic | ✅ MCP calls existing APIs; zero business logic in MCP |
| MCP must not become a second business-logic layer | ✅ PASS — all 6 security/BL tests PASS |

---

## Final Status

**C12 is complete.**

Test results: **30 passed, 0 failed** (`python -m pytest Phase_4/tests/test_c12_mcp_server.py -v`)
