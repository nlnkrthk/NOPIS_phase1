# C14 — Headless NOC Investigation Agent Report

## 1. Goal

C14 adds a programmatic investigation agent that accepts a `grid_id`, gathers evidence from the existing Phase 4 REST API, compares the available results, assesses severity conservatively, and returns a structured investigation brief.

The implementation uses the installed `anthropic` Python SDK as an optional assessment pass. The unavailable `claude_agent_sdk` package was not silently substituted: the direct Anthropic SDK substitution was approved before implementation. Evidence gathering remains deterministic and API-backed.

## 2. Activities 303–308

- **303:** Created `HeadlessInvestigationAgent` and a command-line entry point.
- **304:** Added six named tools and mapped them to Phase 4 API paths.
- **305:** Enforced the workflow `gather -> compare -> assess -> summarize`; `pipeline_status` is always called first.
- **306:** Returned `severity`, `evidence`, `uncertainty`, and `recommended_checks`.
- **307:** Added `python Phase_7/investigate_grid.py <grid_id>`.
- **308:** Continued after individual API failures and recorded unavailable sources in `uncertainty`.

## 3. Architecture

```text
CLI grid_id
    |
    v
HeadlessInvestigationAgent
    |
    +--> Phase 4 REST API tools through NopisApiClient
    |
    +--> evidence traceability and failure bookkeeping
    |
    +--> bounded local severity assessment
    |
    +--> optional Anthropic SDK assessment pass
    |
    v
Structured JSON investigation brief
```

The agent does not query MySQL, read warehouse tables, calculate anomaly scores, or duplicate pipeline logic.

## 4. Tool-to-API Mapping

| Tool | Existing API path | Notes |
|---|---|---|
| `network_summary` | `GET /network/summary` | Overall proportional activity metrics |
| `grid_activity` | `GET /network/grid/{grid_id}` | Hourly activity time series |
| `grid_features` | `GET /network/grid/{grid_id}/features` | Stored ML feature vector |
| `grid_location` | `GET /network/grid/{grid_id}/location` | Attempted; C12 documents that this route is not currently implemented |
| `anomaly_score` | `GET /network/grid/{grid_id}/evidence` | Existing curated evidence containing anomaly fields |
| `pipeline_status` | `GET /network/pipeline/status` | Pipeline and warehouse health |

## 5. Workflow and Pipeline Rule

The agent calls `pipeline_status` before any grid-specific tool. Pipeline health is included in evidence when successful. A non-`HEALTHY` status or a failed pipeline call adds uncertainty and prevents an unjustified `HIGH` result.

After gathering, the agent compares only successful responses. It then assesses severity using the observed anomaly direction while applying pipeline and missing-source constraints. The final summary contains only values received from successful API responses.

## 6. Output Structure

```json
{
  "severity": "NORMAL | ATTENTION | HIGH",
  "evidence": [
    {
      "claim": "Observed fact",
      "value": "Actual API value",
      "source_tool": "tool_name"
    }
  ],
  "uncertainty": ["Missing or untrusted evidence"],
  "recommended_checks": ["Next human checks"]
}
```

Activity values remain proportional activity measures. They are not counts or MB. A grid is a geographic cell, and the output does not make claims unsupported by capacity or utilization evidence.

## 7. Graceful Degradation

Each tool call is isolated. If one API fails, the agent:

1. records the tool and error in `uncertainty`;
2. continues with the other tools;
3. excludes the failed source from `evidence`;
4. constrains severity to `ATTENTION` unless the remaining evidence and pipeline state justify more certainty;
5. adds a human follow-up check.

No fallback value is generated for a failed source.

## 8. Grid 4821 Normal Run

Command:

```powershell
python Phase_7/investigate_grid.py 4821
```

The command completed without interactive input. The local FastAPI server was not listening, so the connection was refused for all six API calls. The returned brief was valid:

- `severity`: `ATTENTION`
- `evidence`: empty, because no API response succeeded
- `uncertainty`: explicitly named `pipeline_status`, `network_summary`, `grid_activity`, `grid_features`, `grid_location`, and `anomaly_score`
- `recommended_checks`: restore the API, verify pipeline freshness, and inspect the unavailable evidence paths

This result is correctly constrained by unavailable pipeline and network evidence.

## 9. Failure Test Result

`Phase_7/test_investigate_grid.py` simulates an anomaly API outage and a missing location endpoint while allowing the other tools to succeed.

Result: **2 passed**.

The test verified that:

- `pipeline_status` was called first;
- the investigation completed;
- severity became `ATTENTION`;
- `anomaly_score` was named as unavailable;
- no anomaly value was emitted;
- successful evidence retained `source_tool` for every item.

## 10. Evidence Traceability

Every evidence object is created with exactly `claim`, `value`, and `source_tool`. Values are added only when the corresponding API response succeeds and contains that field. Failed calls are represented only in `uncertainty`.

## 11. Files Created

- `Phase_7/investigate_grid.py`
- `Phase_7/test_investigate_grid.py`
- `Phase_7/C14_Headless_NOC_Investigation_Agent_Report.md`

No existing production API files were modified.

## 12. Limitations and Future Improvements

- The direct Anthropic SDK pass is optional and requires `ANTHROPIC_API_KEY`; the deterministic agent still returns a valid brief when it is absent.
- The Phase 4 API must be running for live evidence.
- `grid_location` remains unavailable until Phase 4 exposes the documented route using `properties.cellId`.
- A future iteration could use Anthropic structured output validation, while continuing to treat API responses as the only source of facts.
