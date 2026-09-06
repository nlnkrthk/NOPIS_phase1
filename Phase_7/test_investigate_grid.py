from Phase_7.investigate_grid import HeadlessInvestigationAgent, NopisApiClient


def test_pipeline_status_is_called_first_and_evidence_is_traceable():
    calls = []
    responses = {
        "/network/pipeline/status": {"status": "HEALTHY", "latest_warehouse_timestamp": "2013-11-07 23:00:00", "total_warehouse_fact_rows": 10},
        "/network/summary": {"total_activity": 100.0, "active_grids": 2, "peak_hour": 18, "top_grid": 4821},
        "/network/grid/4821": [{"timestamp": "2013-11-07 23:00:00", "total_activity": 55.5}],
        "/network/grid/4821/features": {"avg_activity": 50.0, "activity_growth": 1.1, "active_hours": 12, "peak_ratio": 1.2, "variability": 0.2, "internet_share": 0.8},
        "/network/grid/4821/location": {"longitude": 9.2, "latitude": 45.4},
        "/network/grid/4821/evidence": {"current_activity": 55.5, "baseline_activity": 50.0, "anomaly_score": 11.0, "direction": "NORMAL"},
    }

    def get_json(path):
        calls.append(path)
        return responses[path]

    brief = HeadlessInvestigationAgent(NopisApiClient(get_json=get_json)).investigate(4821)

    assert calls[0] == "/network/pipeline/status"
    assert brief["severity"] == "NORMAL"
    assert brief["uncertainty"] == []
    assert brief["evidence"]
    assert all(set(item) == {"claim", "value", "source_tool"} for item in brief["evidence"])


def test_failed_anomaly_source_degrades_without_inventing_a_score():
    calls = []
    responses = {
        "/network/pipeline/status": {"status": "HEALTHY", "latest_warehouse_timestamp": "2013-11-07 23:00:00", "total_warehouse_fact_rows": 10},
        "/network/summary": {"total_activity": 100.0, "active_grids": 2},
        "/network/grid/4821": [{"timestamp": "2013-11-07 23:00:00", "total_activity": 55.5}],
        "/network/grid/4821/features": {"avg_activity": 50.0},
    }

    def get_json(path):
        calls.append(path)
        if path == "/network/grid/4821/evidence":
            raise RuntimeError("simulated anomaly API outage")
        if path == "/network/grid/4821/location":
            raise RuntimeError("location endpoint unavailable")
        return responses[path]

    brief = HeadlessInvestigationAgent(NopisApiClient(get_json=get_json)).investigate(4821)

    assert calls[0] == "/network/pipeline/status"
    assert brief["severity"] == "ATTENTION"
    assert any("anomaly_score unavailable" in item for item in brief["uncertainty"])
    assert not any(item["source_tool"] == "anomaly_score" for item in brief["evidence"])
    assert brief["recommended_checks"]
