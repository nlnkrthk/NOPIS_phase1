"""
Phase_4/tests/test_c12_mcp_server.py
NOPIS C12 — MCP Server Tests

Tests verify:
  1. MCP tool result == direct API result  (thin-wrapper correctness)
  2. Invalid inputs are rejected by MCP validation
  3. pipeline_status uses the pipeline_status tool (not activity/anomaly data)
  4. No business logic exists in the MCP layer

These tests run without a live server for validation/security tests.
For MCP vs API comparison tests, the FastAPI server must be running at
http://127.0.0.1:8000.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure .claude is importable from the repo root
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / ".claude"))

# Import the MCP server module from .claude
import mcp_server



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_response(json_data, status_code=200):
    """Create a mock httpx.Response that returns json_data."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.is_success = (200 <= status_code < 300)
    mock.json.return_value = json_data
    mock.text = str(json_data)
    return mock


# ---------------------------------------------------------------------------
# 297. Input validation tests — invalid inputs must be rejected.
# These tests run without a live server.
# ---------------------------------------------------------------------------

class TestInputValidation:
    """297. Add basic validation and security constraints."""

    def test_grid_activity_invalid_grid_id_zero(self):
        """grid_id = 0 is below the valid range 1-10000."""
        with pytest.raises(ValueError, match="1-10000"):
            mcp_server.grid_activity(grid_id=0)

    def test_grid_activity_invalid_grid_id_too_large(self):
        """grid_id = 10001 is above the valid range 1-10000."""
        with pytest.raises(ValueError, match="1-10000"):
            mcp_server.grid_activity(grid_id=10001)

    def test_grid_activity_invalid_hour(self):
        """hour = 25 is outside the valid range 0-23."""
        with patch("mcp_server.httpx.get") as mock_get:
            # grid_id is valid; hour check happens after
            mock_get.return_value = _make_mock_response([])
            with pytest.raises(ValueError, match="0-23"):
                mcp_server.grid_activity(grid_id=100, hour=25)

    def test_grid_features_invalid_grid_id_negative(self):
        """Negative grid_id must be rejected."""
        with pytest.raises(ValueError, match="1-10000"):
            mcp_server.grid_features(grid_id=-1)

    def test_hotspots_invalid_limit_zero(self):
        """limit = 0 is below the valid range 1-500."""
        with pytest.raises(ValueError, match="1 and 500"):
            mcp_server.hotspots(limit=0)

    def test_hotspots_invalid_limit_too_large(self):
        """limit = 501 is above the valid range 1-500."""
        with pytest.raises(ValueError, match="1 and 500"):
            mcp_server.hotspots(limit=501)

    def test_hotspots_invalid_severity(self):
        """An unrecognised severity value must be rejected."""
        with pytest.raises(ValueError, match="severity must be one of"):
            mcp_server.hotspots(severity="EXTREME")

    def test_alerts_invalid_limit(self):
        """limit = -5 is below the valid range 1-500."""
        with pytest.raises(ValueError, match="1 and 500"):
            mcp_server.alerts(limit=-5)

    def test_alerts_invalid_severity(self):
        """An unrecognised severity value must be rejected."""
        with pytest.raises(ValueError, match="severity must be one of"):
            mcp_server.alerts(severity="UNKNOWN")

    def test_grid_location_invalid_grid_id(self):
        """grid_location validates grid_id even though it is a gap-report tool."""
        with pytest.raises(ValueError, match="1-10000"):
            mcp_server.grid_location(grid_id=99999)

    def test_nearby_hotspots_invalid_grid_id(self):
        """nearby_hotspots validates grid_id even though it is a gap-report tool."""
        with pytest.raises(ValueError, match="1-10000"):
            mcp_server.nearby_hotspots(grid_id=0)

    def test_nearby_hotspots_invalid_radius(self):
        """nearby_hotspots rejects radius_km <= 0."""
        with pytest.raises(ValueError, match="radius_km must be > 0"):
            mcp_server.nearby_hotspots(grid_id=100, radius_km=-1.0)


# ---------------------------------------------------------------------------
# Security constraint tests — MCP must not expose secrets or perform
# destructive operations.
# ---------------------------------------------------------------------------

class TestSecurityConstraints:
    """297. Security constraints — the MCP server is read-only."""

    def test_mcp_server_has_no_write_operations(self):
        """MCP tools must only use GET requests, never POST/PUT/DELETE.
        Verify _call_api uses httpx.get (not .post, .put, .delete, .patch)."""
        import inspect
        source = inspect.getsource(mcp_server._call_api)
        assert "httpx.get" in source, "_call_api must use httpx.get"
        # No write HTTP methods should appear
        for forbidden in ["httpx.post", "httpx.put", "httpx.delete", "httpx.patch"]:
            assert forbidden not in source, f"_call_api must not use {forbidden}"

    def test_mcp_server_does_not_import_dotenv_reader(self):
        """MCP server must not read the .env file or expose secrets.
        It may mention NOPIS_API_BASE_URL in docs but must not load dotenv."""
        import inspect
        source = inspect.getsource(mcp_server)
        # Must not actively load .env file
        assert "load_dotenv" not in source, "mcp_server.py must not call load_dotenv()"
        assert "dotenv" not in source.lower(), "mcp_server.py must not import dotenv"
        # Must not hard-code or expose secret env vars
        assert "DB_PASSWORD" not in source
        assert "ANTHROPIC_API_KEY" not in source

    def test_mcp_server_does_not_contain_sql(self):
        """MCP server must not contain any SQL — no direct DB access."""
        import inspect
        source = inspect.getsource(mcp_server)
        for keyword in ["SELECT ", "INSERT ", "UPDATE ", "DELETE ", "DROP "]:
            assert keyword not in source, (
                f"mcp_server.py must not contain SQL keyword: {keyword}"
            )

    def test_mcp_server_does_not_import_sqlalchemy(self):
        """MCP server must not import SQLAlchemy (no direct DB access)."""
        import inspect
        source = inspect.getsource(mcp_server)
        assert "sqlalchemy" not in source.lower(), (
            "mcp_server.py must not import SQLAlchemy"
        )

    def test_mcp_server_does_not_import_sessionlocal(self):
        """MCP server must not import SessionLocal (the DB session factory)."""
        import inspect
        source = inspect.getsource(mcp_server)
        assert "SessionLocal" not in source, (
            "mcp_server.py must not import SessionLocal (no direct DB access)"
        )

    def test_mcp_server_does_not_contain_business_logic_keywords(self):
        """MCP layer must not contain aggregation or scoring computation logic."""
        import inspect
        source = inspect.getsource(mcp_server)
        # These patterns specifically indicate MCP is COMPUTING values itself.
        # Presence of these strings in doc comments is fine; computation is not.
        forbidden_patterns = [
            "GROUP BY",          # SQL aggregation
            "ORDER BY",          # SQL ranking
            "anomaly_score =",   # computing anomaly score
            "risk_score =",      # computing risk score
            "score * ",          # arithmetic on scores
            "threshold =",       # applying thresholds
        ]
        for pattern in forbidden_patterns:
            assert pattern not in source, (
                f"mcp_server.py must not contain business-logic computation: {pattern!r}"
            )


# ---------------------------------------------------------------------------
# Thin-wrapper correctness tests — MCP result must equal direct API result.
# Each test mocks httpx.get to return a fixed payload and verifies the MCP
# tool returns it unchanged.
# ---------------------------------------------------------------------------

class TestThinWrapperCorrectness:
    """Verify MCP tools return the API response without modification."""

    def test_network_summary_returns_api_result_unchanged(self):
        """network_summary() must return the API response unchanged."""
        expected = {
            "total_activity": 12345.6,
            "active_grids": 100,
            "peak_hour": 18,
            "top_grid": 4821,
            "from_dt": "2013-11-01T00:00:00",
            "to_dt": "2013-11-30T23:00:00",
        }
        with patch("mcp_server.httpx.get") as mock_get:
            mock_get.return_value = _make_mock_response(expected)
            result = mcp_server.network_summary()

        assert result == expected, (
            "network_summary() must return the API response unchanged"
        )
        # Verify the correct API path was called
        called_url = mock_get.call_args[0][0]
        assert called_url.endswith("/network/summary"), (
            f"Expected /network/summary, got: {called_url}"
        )

    def test_grid_activity_returns_api_result_unchanged(self):
        """grid_activity() must return the API response unchanged."""
        expected = [
            {"grid_id": 4821, "timestamp": "2013-11-01T10:00:00",
             "total_activity": 500.0, "hour": 10}
        ]
        with patch("mcp_server.httpx.get") as mock_get:
            mock_get.return_value = _make_mock_response(expected)
            result = mcp_server.grid_activity(grid_id=4821)

        assert result == expected
        called_url = mock_get.call_args[0][0]
        assert "/network/grid/4821" in called_url

    def test_grid_features_returns_api_result_unchanged(self):
        """grid_features() must return the API response unchanged."""
        expected = {
            "grid_id": 4821,
            "feature_timestamp": "2013-11-30T23:00:00",
            "avg_activity": 300.5,
            "activity_growth": 0.12,
            "active_hours": 22,
            "peak_ratio": 1.8,
            "variability": 0.3,
            "internet_share": 0.55,
            "data_quality_status": "VALID",
            "freshness_hours": 48.0,
            "is_fresh": True,
        }
        with patch("mcp_server.httpx.get") as mock_get:
            mock_get.return_value = _make_mock_response(expected)
            result = mcp_server.grid_features(grid_id=4821)

        assert result == expected
        called_url = mock_get.call_args[0][0]
        assert "/network/grid/4821/features" in called_url

    def test_hotspots_returns_api_result_unchanged(self):
        """hotspots() must return the API response unchanged."""
        expected = [
            {"grid_id": 4821, "timestamp": "2013-11-30T18:00:00",
             "total_activity": 800.0, "severity": "HIGH",
             "reason": "Activity above HIGH threshold", "risk_score": None}
        ]
        with patch("mcp_server.httpx.get") as mock_get:
            mock_get.return_value = _make_mock_response(expected)
            result = mcp_server.hotspots(limit=5)

        assert result == expected
        called_url = mock_get.call_args[0][0]
        assert "/network/hotspots" in called_url

    def test_alerts_returns_api_result_unchanged(self):
        """alerts() must return the API response unchanged."""
        expected = [
            {"grid_id": 100, "timestamp": "2013-11-30T12:00:00",
             "alert_type": "HIGH_ACTIVITY", "severity": "CRITICAL",
             "total_activity": 999.0}
        ]
        with patch("mcp_server.httpx.get") as mock_get:
            mock_get.return_value = _make_mock_response(expected)
            result = mcp_server.alerts(limit=10)

        assert result == expected
        called_url = mock_get.call_args[0][0]
        assert "/network/alerts" in called_url

    def test_pipeline_status_returns_api_result_unchanged(self):
        """pipeline_status() must return the API response unchanged."""
        expected = {
            "command": "/check-pipeline",
            "status": "HEALTHY",
            "latest_warehouse_timestamp": "2013-11-30 23:00:00",
            "total_warehouse_fact_rows": 50000,
            "valid_ingestions_count": 30,
            "invalid_ingestions_count": 0,
            "rejected_files_count": 0,
            "rejected_files": [],
            "log_path": "logs/ingestion_log.csv",
        }
        with patch("mcp_server.httpx.get") as mock_get:
            mock_get.return_value = _make_mock_response(expected)
            result = mcp_server.pipeline_status()

        assert result == expected
        called_url = mock_get.call_args[0][0]
        # 296. Verify pipeline_status calls the pipeline_status endpoint,
        #      not the activity or hotspots endpoint.
        assert "/network/pipeline/status" in called_url, (
            f"pipeline_status tool must call /network/pipeline/status, "
            f"not another endpoint. Called: {called_url}"
        )


# ---------------------------------------------------------------------------
# Gap report tests
# ---------------------------------------------------------------------------

class TestGapReports:
    """Verify gap-report tools return gap metadata, not invented data."""

    def test_grid_location_returns_gap_report(self):
        """grid_location must return a gap dict, not invent location data."""
        result = mcp_server.grid_location(grid_id=100)
        assert result["gap"] is True
        assert result["tool"] == "grid_location"
        assert result["grid_id"] == 100
        assert "missing_api_capability" in result

    def test_nearby_hotspots_returns_gap_report(self):
        """nearby_hotspots must return a gap dict, not invent proximity data."""
        result = mcp_server.nearby_hotspots(grid_id=100, radius_km=3.0)
        assert result["gap"] is True
        assert result["tool"] == "nearby_hotspots"
        assert result["grid_id"] == 100
        assert "missing_api_capability" in result


# ---------------------------------------------------------------------------
# Activity 295 — "Which grids have the highest anomaly scores?"
# Verify that answering this question uses the hotspots or alerts tool,
# not invented ranking logic in MCP.
# ---------------------------------------------------------------------------

class TestActivity295AnomalyQuestion:
    """295. The anomaly score question must be answered via an MCP tool call."""

    def test_hotspots_tool_is_used_not_invented_ranking(self):
        """Verify hotspots() returns whatever the API returns — no MCP ranking."""
        # Simulate the API returning grids with severity ratings
        api_result = [
            {"grid_id": 4821, "severity": "CRITICAL", "total_activity": 900.0,
             "reason": "Activity above CRITICAL threshold"},
            {"grid_id": 200, "severity": "HIGH", "total_activity": 700.0,
             "reason": "Activity above HIGH threshold"},
        ]
        with patch("mcp_server.httpx.get") as mock_get:
            mock_get.return_value = _make_mock_response(api_result)
            result = mcp_server.hotspots(limit=10)

        # The MCP result must be the raw API result — no sorting, no scoring
        assert result == api_result, (
            "hotspots() must return the API result unchanged. "
            "MCP must not re-rank or re-score."
        )

    def test_no_anomaly_scoring_in_mcp_source(self):
        """No anomaly score CALCULATION may exist in the MCP source code.
        Doc-strings may mention field names; actual computation must not exist."""
        import inspect
        source = inspect.getsource(mcp_server)
        # These patterns indicate MCP is computing scores itself (not just
        # mentioning field names in docstrings)
        forbidden = [
            "anomaly_score =",  # assignment = computing
            "risk_score =",     # assignment = computing
            "ranking =",        # explicit ranking computation
            "score * ",         # arithmetic on scores
        ]
        for pattern in forbidden:
            assert pattern not in source, (
                f"mcp_server.py must not contain business logic computation: {pattern!r}"
            )


# ---------------------------------------------------------------------------
# Activity 296 — "Check whether their data pipeline completed successfully."
# Verify pipeline_status tool is called, not activity/anomaly tools.
# ---------------------------------------------------------------------------

class TestActivity296PipelineQuestion:
    """296. Pipeline completion must be checked via pipeline_status tool."""

    def test_pipeline_status_calls_correct_endpoint(self):
        """pipeline_status() must call /network/pipeline/status, not any other endpoint."""
        expected = {"status": "HEALTHY", "total_warehouse_fact_rows": 50000}
        with patch("mcp_server.httpx.get") as mock_get:
            mock_get.return_value = _make_mock_response(expected)
            result = mcp_server.pipeline_status()

        assert result == expected
        called_url = mock_get.call_args[0][0]
        # Must call the pipeline status endpoint, not hotspots, alerts, or summary
        assert "/network/pipeline/status" in called_url
        assert "/network/hotspots" not in called_url
        assert "/network/alerts" not in called_url
        assert "/network/summary" not in called_url

    def test_pipeline_status_not_inferred_from_activity(self):
        """Pipeline health must come from pipeline_status, not activity data.
        Verify pipeline_status() does not call grid_activity or hotspots."""
        import inspect
        # pipeline_status function source should only call _call_api with
        # /network/pipeline/status — nothing else
        source = inspect.getsource(mcp_server.pipeline_status)
        assert "hotspots" not in source
        assert "grid_activity" not in source
        assert "alerts" not in source
        assert "/network/pipeline/status" in source
