"""
.claude/mcp_server.py
NOPIS C12 — MCP Server for Network Intelligence

NOTE ON MCP VERSION:
  This server uses mcp v2.x (MCPServer, formerly FastMCP).
  Import: from mcp.server.mcpserver import MCPServer

# 293. Implement or configure a small MCP server around the existing APIs —
#      it must call API1–API6, not reimplement them.

This server is a THIN wrapper.
Every tool:
  1. Receives validated input.
  2. Calls the existing NOPIS FastAPI endpoint via HTTP.
  3. Returns the API result unchanged.

The MCP server does NOT:
  - Query the database directly.
  - Calculate or rank anomaly scores.
  - Apply thresholds, aggregate data, or interpret network conditions.
  - Claim congestion.
  - Reimplement any existing API logic.

Architecture:
  Claude / Claude Code
        |
     MCP Server  (this file — only validates input and calls API)
        |
  Existing NOPIS APIs  (FastAPI at http://127.0.0.1:8000)
        |
  Existing NOPIS business logic / MySQL warehouse

Start the FastAPI server first:
  cd Phase_4
  uvicorn main:app --host 127.0.0.1 --port 8000 --reload

Then start this MCP server (stdio transport, used by Claude Code):
  python .claude/mcp_server.py

The base URL of the FastAPI server can be overridden with the
environment variable NOPIS_API_BASE_URL.
"""

import os
import httpx
# mcp v2.x: FastMCP was renamed to MCPServer — see migration guide:
# https://py.sdk.modelcontextprotocol.io/v2/migration/#fastmcp-renamed-to-mcpserver
from mcp.server.mcpserver import MCPServer

# ---------------------------------------------------------------------------
# Configuration — base URL of the existing NOPIS FastAPI server.
# The MCP server never talks to the database directly.
# ---------------------------------------------------------------------------
API_BASE = os.environ.get("NOPIS_API_BASE_URL", "http://127.0.0.1:8000")

# ---------------------------------------------------------------------------
# MCP server instance
# ---------------------------------------------------------------------------
mcp = MCPServer(
    name="NOPIS Network Intelligence",
    instructions=(
        "Tools for querying the NOPIS telecom network. "
        "Each tool calls the existing NOPIS REST API — no data is invented. "
        "Activity values are proportional measures, NOT call counts or MB. "
        "High activity does NOT mean confirmed congestion. "
        "A grid is a geographic cell, NOT a tower."
    ),
)


# ---------------------------------------------------------------------------
# Shared HTTP helper — calls the existing API and returns parsed JSON.
# All tools use this helper; no tool accesses the database or files directly.
# ---------------------------------------------------------------------------

def _call_api(path: str, params: dict | None = None) -> dict | list:
    """Call the existing NOPIS FastAPI endpoint and return the parsed JSON.

    Args:
        path:   URL path relative to API_BASE (e.g. '/network/summary').
        params: Optional query parameters dict.

    Returns:
        Parsed JSON from the API (dict or list).

    Raises:
        RuntimeError: if the API returns a non-2xx status.
        RuntimeError: if the FastAPI server is not reachable.
    """
    url = f"{API_BASE}{path}"
    try:
        response = httpx.get(url, params=params, timeout=10.0)
    except httpx.ConnectError:
        raise RuntimeError(
            f"Cannot reach the NOPIS FastAPI server at {API_BASE}. "
            "Start it with: cd Phase_4 && uvicorn main:app --host 127.0.0.1 --port 8000 --reload"
        )
    if not response.is_success:
        raise RuntimeError(
            f"API returned {response.status_code} for {url}: {response.text}"
        )
    return response.json()


# ---------------------------------------------------------------------------
# Activity 292 / 293 — MCP Tools
# ---------------------------------------------------------------------------

# 292. Design MCP tools and resources for network summary, hotspots, grid
#      metrics, grid location and nearby hotspots, alerts, and pipeline status.
# 293. Implement or configure a small MCP server around the existing APIs —
#      it must call API1–API6, not reimplement them.

@mcp.tool()
def network_summary(
    from_dt: str | None = None,
    to_dt: str | None = None,
    as_of: str | None = None,
) -> dict:
    """Return overall network metrics: total activity, active grids, peak hour,
    and top grid.

    Calls: GET /network/summary

    Args:
        from_dt: Optional start datetime (ISO format: YYYY-MM-DDTHH:MM:SS).
                 If omitted, defaults to oldest timestamp in analytics.
        to_dt:   Optional end datetime (ISO format: YYYY-MM-DDTHH:MM:SS).
                 If omitted, defaults to MAX(timestamp) in analytics.
        as_of:   Optional point-in-time reference (ISO format).
                 Mutually exclusive with from_dt/to_dt.

    Returns:
        dict with keys: total_activity, active_grids, peak_hour, top_grid,
        from_dt, to_dt.

    Note:
        Activity values are proportional measures, not call counts or MB.
        High activity does not indicate confirmed congestion.
    """
    # 297. Build query params — only include keys that were actually provided.
    params: dict = {}
    if from_dt is not None:
        params["from_dt"] = from_dt
    if to_dt is not None:
        params["to_dt"] = to_dt
    if as_of is not None:
        params["as_of"] = as_of

    # Delegate entirely to the existing API — no logic added here.
    return _call_api("/network/summary", params or None)


@mcp.tool()
def grid_activity(
    grid_id: int,
    date: str | None = None,
    hour: int | None = None,
    as_of: str | None = None,
    from_dt: str | None = None,
    to_dt: str | None = None,
) -> list:
    """Return the hourly activity time-series for a single grid cell.

    Calls: GET /network/grid/{grid_id}

    Args:
        grid_id: Integer grid identifier. Must be in the range 1-10000.
        date:    Optional date filter (YYYY-MM-DD).
        hour:    Optional hour filter (0-23).
        as_of:   Optional cumulative end timestamp (ISO format).
        from_dt: Optional inclusive range start timestamp (ISO format).
        to_dt:   Optional inclusive range end timestamp (ISO format).

    Returns:
        List of hourly activity points. Each item has: grid_id, timestamp,
        date, hour, sms_in, sms_out, call_in, call_out, internet_activity,
        total_sms, total_calls, total_activity, internet_share.

    Note:
        A grid is a geographic cell, not a tower.
        Activity values are proportional measures, not raw counts or MB.
    """
    # 297. Validate grid_id before calling the API.
    if not (1 <= grid_id <= 10000):
        raise ValueError(
            f"grid_id must be in the range 1-10000. Got: {grid_id}"
        )

    params: dict = {}
    if date is not None:
        params["date"] = date
    if hour is not None:
        if not (0 <= hour <= 23):
            raise ValueError(f"hour must be 0-23. Got: {hour}")
        params["hour"] = hour
    if as_of is not None:
        params["as_of"] = as_of
    if from_dt is not None:
        params["from_dt"] = from_dt
    if to_dt is not None:
        params["to_dt"] = to_dt

    return _call_api(f"/network/grid/{grid_id}", params or None)


@mcp.tool()
def grid_features(
    grid_id: int,
    as_of: str | None = None,
) -> dict:
    """Return the ML feature vector for a single grid cell.

    Calls: GET /network/grid/{grid_id}/features

    The feature vector contains the six ML2 features computed by the feature
    engineering pipeline: avg_activity, activity_growth, active_hours,
    peak_ratio, variability, internet_share.

    Args:
        grid_id: Integer grid identifier. Must be in the range 1-10000.
        as_of:   Optional feature window end timestamp (ISO format).

    Returns:
        dict with keys: grid_id, feature_timestamp, avg_activity,
        activity_growth, active_hours, peak_ratio, variability,
        internet_share, data_quality_status, freshness_hours, is_fresh.
    """
    # 297. Validate grid_id before calling the API.
    if not (1 <= grid_id <= 10000):
        raise ValueError(
            f"grid_id must be in the range 1-10000. Got: {grid_id}"
        )

    params: dict = {}
    if as_of is not None:
        params["as_of"] = as_of

    return _call_api(f"/network/grid/{grid_id}/features", params or None)


@mcp.tool()
def hotspots(
    limit: int = 10,
    severity: str | None = None,
    as_of: str | None = None,
) -> list:
    """Return the highest-activity grid cells (hotspots).

    Calls: GET /network/hotspots

    Args:
        limit:    Maximum number of hotspot entries to return (1-500).
                  Default: 10.
        severity: Optional filter by severity level.
                  Accepted values: CRITICAL, HIGH, MEDIUM, LOW.
        as_of:    Optional reporting timestamp (ISO format).

    Returns:
        List of hotspot items. Each item has: grid_id, timestamp,
        total_activity, sms_activity, call_activity, internet_activity,
        severity, reason, risk_score, risk_level, model_version.

    Note:
        Activity values are proportional measures, not raw counts or MB.
        High activity does not indicate confirmed congestion.
    """
    # 297. Validate limit before calling the API.
    if not (1 <= limit <= 500):
        raise ValueError(f"limit must be between 1 and 500. Got: {limit}")

    # 297. Validate severity if provided.
    valid_severities = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
    if severity is not None and severity.upper() not in valid_severities:
        raise ValueError(
            f"severity must be one of {sorted(valid_severities)}. Got: {severity!r}"
        )

    params: dict = {"limit": limit}
    if severity is not None:
        params["severity"] = severity.upper()
    if as_of is not None:
        params["as_of"] = as_of

    return _call_api("/network/hotspots", params)


@mcp.tool()
def alerts(
    limit: int = 20,
    severity: str | None = None,
    as_of: str | None = None,
) -> list:
    """Return rule-triggered network alerts.

    Calls: GET /network/alerts

    Args:
        limit:    Maximum number of alerts to return (1-500).
                  Default: 20.
        severity: Optional filter by severity level.
                  Accepted values: CRITICAL, HIGH, MEDIUM, LOW, INFO.
        as_of:    Optional reporting timestamp (ISO format).

    Returns:
        List of alert items. Each item has: grid_id, timestamp,
        alert_type, severity, total_activity, sms_activity,
        call_activity, internet_activity, reason, risk_score,
        risk_level, model_version.
    """
    # 297. Validate limit before calling the API.
    if not (1 <= limit <= 500):
        raise ValueError(f"limit must be between 1 and 500. Got: {limit}")

    # 297. Validate severity if provided.
    valid_severities = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}
    if severity is not None and severity.upper() not in valid_severities:
        raise ValueError(
            f"severity must be one of {sorted(valid_severities)}. Got: {severity!r}"
        )

    params: dict = {"limit": limit}
    if severity is not None:
        params["severity"] = severity.upper()
    if as_of is not None:
        params["as_of"] = as_of

    return _call_api("/network/alerts", params)


@mcp.tool()
def pipeline_status() -> dict:
    """Return the pipeline health status: ingestion log validity counts,
    rejected file count, and warehouse freshness.

    Calls: GET /network/pipeline/status

    Returns:
        dict with keys: command, status, latest_warehouse_timestamp,
        total_warehouse_fact_rows, valid_ingestions_count,
        invalid_ingestions_count, rejected_files_count,
        rejected_files, log_path.

    Status values:
        HEALTHY   -- no rejected files or invalid ingestions; warehouse is fresh.
        DEGRADED  -- some rejected files or invalid ingestions exist.
        UNHEALTHY -- warehouse is empty or has no timestamps.

    Note:
        Do not infer pipeline health from anomaly scores or activity data.
        This tool always calls the pipeline status endpoint directly.
    """
    # 293. Thin wrapper — call the existing API endpoint, return result as-is.
    return _call_api("/network/pipeline/status")


# ---------------------------------------------------------------------------
# Gap Report Tools — capabilities NOT in the existing API.
# These tools document the gaps rather than inventing missing logic.
# ---------------------------------------------------------------------------

@mcp.tool()
def grid_location(grid_id: int) -> dict:
    """[GAP REPORT] Grid geographic location data is not available via the API.

    The existing NOPIS FastAPI does NOT provide a
    GET /network/grid/{grid_id}/location endpoint.

    The GeoJSON data (data/milano-grid.geojson) exists in the repository
    but no API endpoint serves per-grid geographic data.

    To enable this capability, the following would need to be added to the
    existing API:
      - A new GET /network/grid/{grid_id}/location endpoint in
        Phase_4/routers/network.py
      - A new service function in Phase_4/services.py that reads
        data/milano-grid.geojson and returns geometry for the given
        grid_id using the properties.cellId join key (NOT the 0-based
        featureid field).

    This MCP tool does NOT invent the missing capability.
    """
    # 297. Still validate grid_id so invalid inputs are caught early.
    if not (1 <= grid_id <= 10000):
        raise ValueError(
            f"grid_id must be in the range 1-10000. Got: {grid_id}"
        )

    return {
        "gap": True,
        "tool": "grid_location",
        "grid_id": grid_id,
        "message": (
            "The GET /network/grid/{grid_id}/location endpoint does not exist "
            "in the current NOPIS FastAPI. The GeoJSON file exists at "
            "data/milano-grid.geojson but is not served per grid_id via the API. "
            "Add a location endpoint to Phase_4/routers/network.py to enable "
            "this capability."
        ),
        "missing_api_capability": "GET /network/grid/{grid_id}/location",
    }


@mcp.tool()
def nearby_hotspots(grid_id: int, radius_km: float = 5.0) -> dict:
    """[GAP REPORT] Nearby hotspots capability is not implemented in the existing API.

    The existing NOPIS FastAPI does NOT provide any endpoint for
    finding hotspots near a given grid cell.

    To enable this capability, the following would need to be added:
      - A new GET /network/hotspots/nearby/{grid_id} endpoint in
        Phase_4/routers/network.py
      - A new service function that joins grid geometry from
        data/milano-grid.geojson with hotspot data from the warehouse
        to find grids within the specified radius using the
        properties.cellId join key.

    This MCP tool does NOT invent the missing capability.
    """
    # 297. Validate inputs even though the capability is missing.
    if not (1 <= grid_id <= 10000):
        raise ValueError(
            f"grid_id must be in the range 1-10000. Got: {grid_id}"
        )
    if radius_km <= 0:
        raise ValueError(f"radius_km must be > 0. Got: {radius_km}")

    return {
        "gap": True,
        "tool": "nearby_hotspots",
        "grid_id": grid_id,
        "radius_km": radius_km,
        "message": (
            "The NOPIS FastAPI does not implement a nearby hotspots endpoint. "
            "No existing API provides this capability. "
            "Add a proximity-based hotspot endpoint to Phase_4/routers/network.py "
            "to enable this tool."
        ),
        "missing_api_capability": "GET /network/hotspots/nearby/{grid_id}",
    }


# ---------------------------------------------------------------------------
# Entry point — run with stdio transport (Claude Code default)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # stdio transport is the standard Claude Code MCP integration.
    # Claude Code starts this process and communicates via stdin/stdout.
    mcp.run(transport="stdio")
