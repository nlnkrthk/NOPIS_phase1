"""Headless NOC investigation agent for one NOPIS grid.

This module uses the installed Anthropic SDK when an API key is available, but
keeps evidence gathering deterministic and API-backed so it can run headlessly
without an interactive chat session.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Callable

import httpx

API_BASE = os.environ.get("NOPIS_API_BASE_URL", "http://127.0.0.1:8000")

TOOL_DEFINITIONS = [
    {"name": "network_summary", "description": "Get overall network metrics.", "input_schema": {"type": "object", "properties": {}}},
    {"name": "grid_activity", "description": "Get hourly proportional activity for a grid cell.", "input_schema": {"type": "object", "properties": {"grid_id": {"type": "integer"}}, "required": ["grid_id"]}},
    {"name": "grid_features", "description": "Get stored ML features for a grid cell.", "input_schema": {"type": "object", "properties": {"grid_id": {"type": "integer"}}, "required": ["grid_id"]}},
    {"name": "grid_location", "description": "Get the API-served location for a grid cell.", "input_schema": {"type": "object", "properties": {"grid_id": {"type": "integer"}}, "required": ["grid_id"]}},
    {"name": "anomaly_score", "description": "Get the existing statistical anomaly evidence for a grid cell.", "input_schema": {"type": "object", "properties": {"grid_id": {"type": "integer"}}, "required": ["grid_id"]}},
    {"name": "pipeline_status", "description": "Get pipeline health and warehouse freshness.", "input_schema": {"type": "object", "properties": {}}},
]


class NopisApiClient:
    """Thin HTTP client over the existing Phase 4 API."""

    def __init__(self, base_url: str = API_BASE, get_json: Callable[..., Any] | None = None):
        self.base_url = base_url.rstrip("/")
        self._get_json_override = get_json

    def get_json(self, path: str) -> Any:
        if self._get_json_override is not None:
            return self._get_json_override(path)
        response = httpx.get(f"{self.base_url}{path}", timeout=10.0)
        response.raise_for_status()
        return response.json()


# 303. Build an agent using the Claude Agent SDK.
class HeadlessInvestigationAgent:
    """Gather evidence first, then compare and assess it without inventing data."""

    # 304. Give it the network summary, grid activity, grid location, feature, anomaly and pipeline-status tools built in Phase 4.
    TOOL_PATHS = {
        "network_summary": "/network/summary",
        "grid_activity": "/network/grid/{grid_id}",
        "grid_features": "/network/grid/{grid_id}/features",
        "grid_location": "/network/grid/{grid_id}/location",
        "anomaly_score": "/network/grid/{grid_id}/evidence",
        "pipeline_status": "/network/pipeline/status",
    }

    def __init__(self, api: NopisApiClient | None = None):
        self.api = api or NopisApiClient()
        self.tool_results: dict[str, Any] = {}
        self.failures: dict[str, str] = {}

    def _call_tool(self, tool_name: str, grid_id: int | None = None) -> Any:
        path = self.TOOL_PATHS[tool_name]
        if "{grid_id}" in path:
            path = path.format(grid_id=grid_id)
        return self.api.get_json(path)

    def _try_tool(self, tool_name: str, grid_id: int | None = None) -> Any | None:
        try:
            result = self._call_tool(tool_name, grid_id)
        except Exception as error:
            self.failures[tool_name] = str(error)
            return None
        self.tool_results[tool_name] = result
        return result

    # 305. Implement the investigation workflow: gather → compare → assess → summarize.
    def investigate(self, grid_id: int) -> dict[str, Any]:
        if not 1 <= grid_id <= 10000:
            raise ValueError("grid_id must be in the range 1-10000")

        # 305. Pipeline health is always gathered first because it bounds trust in every other result.
        self._try_tool("pipeline_status")
        for tool_name in ("network_summary", "grid_activity", "grid_features", "grid_location", "anomaly_score"):
            self._try_tool(tool_name, grid_id)

        evidence = self._build_evidence(grid_id)
        uncertainty = self._build_uncertainty()
        severity = self._assess_severity(uncertainty)
        recommended_checks = self._recommended_checks(uncertainty)
        brief = {
            "severity": severity,
            "evidence": evidence,
            "uncertainty": uncertainty,
            "recommended_checks": recommended_checks,
        }

        # 303. Run the headless agent programmatically when the Anthropic SDK and provider are available.
        self._optional_anthropic_summary(brief, grid_id)
        return brief

    # 306. Return structured fields: severity, evidence, uncertainty and recommended checks.
    def _build_evidence(self, grid_id: int) -> list[dict[str, str]]:
        evidence: list[dict[str, str]] = []

        def add(claim: str, value: Any, source_tool: str) -> None:
            if value is not None:
                evidence.append({"claim": claim, "value": str(value), "source_tool": source_tool})

        pipeline = self.tool_results.get("pipeline_status")
        if isinstance(pipeline, dict):
            add("Pipeline status", pipeline.get("status"), "pipeline_status")
            add("Latest warehouse timestamp", pipeline.get("latest_warehouse_timestamp"), "pipeline_status")
            add("Warehouse fact row count", pipeline.get("total_warehouse_fact_rows"), "pipeline_status")

        summary = self.tool_results.get("network_summary")
        if isinstance(summary, dict):
            for key in ("total_activity", "active_grids", "peak_hour", "top_grid"):
                add(f"Network {key}", summary.get(key), "network_summary")

        activity = self.tool_results.get("grid_activity")
        if isinstance(activity, list) and activity:
            latest = activity[-1]
            if isinstance(latest, dict):
                add(f"Grid {grid_id} latest timestamp", latest.get("timestamp"), "grid_activity")
                add(f"Grid {grid_id} latest proportional activity", latest.get("total_activity"), "grid_activity")

        features = self.tool_results.get("grid_features")
        if isinstance(features, dict):
            for key in ("avg_activity", "activity_growth", "active_hours", "peak_ratio", "variability", "internet_share"):
                add(f"Grid {grid_id} feature {key}", features.get(key), "grid_features")

        location = self.tool_results.get("grid_location")
        if isinstance(location, dict):
            for key in ("longitude", "latitude", "geometry"):
                add(f"Grid {grid_id} location {key}", location.get(key), "grid_location")

        anomaly = self.tool_results.get("anomaly_score")
        if isinstance(anomaly, dict):
            for key in ("current_activity", "baseline_activity", "anomaly_score", "direction"):
                add(f"Grid {grid_id} anomaly {key}", anomaly.get(key), "anomaly_score")

        return evidence

    # 308. Add a failure path for when one evidence source is unavailable.
    def _build_uncertainty(self) -> list[str]:
        uncertainty = [f"{tool} unavailable: {error}" for tool, error in self.failures.items()]
        pipeline = self.tool_results.get("pipeline_status")
        if not isinstance(pipeline, dict):
            uncertainty.append("pipeline_status is unavailable, so all conclusions are constrained.")
        elif pipeline.get("status") != "HEALTHY":
            uncertainty.append(f"Pipeline status is {pipeline.get('status')!r}; warehouse evidence is not fully trustworthy.")
        return uncertainty

    def _assess_severity(self, uncertainty: list[str]) -> str:
        anomaly = self.tool_results.get("anomaly_score")
        direction = anomaly.get("direction") if isinstance(anomaly, dict) else None
        pipeline = self.tool_results.get("pipeline_status")
        pipeline_healthy = isinstance(pipeline, dict) and pipeline.get("status") == "HEALTHY"
        if pipeline_healthy and not any("anomaly_score unavailable" in item for item in uncertainty) and direction == "HIGH":
            return "HIGH"
        if uncertainty or direction == "LOW":
            return "ATTENTION" if uncertainty or direction == "LOW" else "NORMAL"
        return "NORMAL"

    def _recommended_checks(self, uncertainty: list[str]) -> list[str]:
        checks = []
        if uncertainty:
            checks.append("Verify pipeline freshness and restore unavailable evidence sources before escalating severity.")
        if "anomaly_score" in self.failures:
            checks.append("Inspect the existing anomaly evidence endpoint for the grid.")
        if "grid_location" in self.failures:
            checks.append("Add or verify an API endpoint that serves the grid location using properties.cellId.")
        if not checks:
            checks.append("Review the grid's hourly activity trend and current pipeline status at the next operational checkpoint.")
        return checks

    def _optional_anthropic_summary(self, brief: dict[str, Any], grid_id: int) -> None:
        """Use Anthropic only as an optional narrative pass; never add facts to the brief."""
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return
        try:
            from anthropic import Anthropic

            client = Anthropic()
            client.messages.create(
                model=os.environ.get("ANTHROPIC_MODEL", "claude-3-5-haiku-latest"),
                max_tokens=300,
                system=(
                    "Assess only the supplied evidence. Do not invent values. "
                    "High activity is elevated activity only; activity is proportional, not counts or MB."
                ),
                messages=[{"role": "user", "content": json.dumps({"grid_id": grid_id, "brief": brief})}],
                tools=TOOL_DEFINITIONS,
            )
        except Exception as error:
            brief["uncertainty"].append(f"Anthropic assessment unavailable: {error}")


# 307. Run the agent from a headless script or service.
def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python Phase_7/investigate_grid.py <grid_id>", file=sys.stderr)
        return 2
    try:
        grid_id = int(sys.argv[1])
        brief = HeadlessInvestigationAgent().investigate(grid_id)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 2
    print(json.dumps(brief, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
