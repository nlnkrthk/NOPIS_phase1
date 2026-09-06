import pytest
from Phase_7.c_tasks.c9_orchestration import (
    DataPipelineAgent,
    NetworkAnalysisAgent,
    MLAnalysisAgent,
    APIAgent,
    SupervisorOrchestrator,
)


def test_data_pipeline_agent_structure():
    agent = DataPipelineAgent()
    res = agent.investigate()
    assert res["agent"] == "Data Pipeline Agent"
    assert "status" in res
    assert "data_trustworthy" in res
    assert isinstance(res["findings"], list)
    assert isinstance(res["limitations_and_uncertainty"], list)
    assert len(res["findings"]) > 0


def test_network_analysis_agent_cluster():
    agent = NetworkAnalysisAgent()
    res = agent.investigate(grid_id=4821)
    assert res["agent"] == "Network Analysis Agent"
    assert res["grid_id"] == 4821
    assert "current_total_activity" in res
    assert "cluster_comparison" in res
    assert len(res["cluster_comparison"]["neighbors"]) == 4
    assert res["cluster_comparison"]["neighbor_average_activity"] > 0


def test_ml_analysis_agent_baselines_and_risk():
    agent = MLAnalysisAgent()
    res = agent.investigate(grid_id=4821)
    assert res["agent"] == "ML Analysis Agent"
    assert res["grid_id"] == 4821
    assert "current_anomaly_score" in res
    assert "historical_surges" in res
    assert "ml2_features" in res
    assert "ml_classifier" in res
    assert res["ml_classifier"]["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")


def test_api_agent_endpoint_probes():
    agent = APIAgent()
    res = agent.investigate(grid_id=4821)
    assert res["agent"] == "API Agent"
    assert res["tested_endpoints_count"] == 6
    assert res["overall_api_health"] == "ALL_HEALTHY"
    for ep in res["endpoint_results"]:
        assert ep["status_code"] == 200


def test_supervisor_orchestrator_surfaces_disagreements():
    supervisor = SupervisorOrchestrator()
    report = supervisor.run_investigation(grid_id=4821)
    assert report["investigation_target"] == "Grid 4821"
    assert "overall_severity" in report
    assert len(report["disagreements_and_uncertainties"]) >= 1
    
    formatted = supervisor.format_report(report)
    assert "C9 MULTI-AGENT INVESTIGATION REPORT" in formatted
    assert "DATA PIPELINE AGENT FINDINGS" in formatted
    assert "NETWORK ANALYSIS AGENT FINDINGS" in formatted
    assert "ML ANALYSIS AGENT FINDINGS" in formatted
    assert "API AGENT FINDINGS" in formatted
    assert "SURFACED DISAGREEMENTS & UNCERTAINTIES" in formatted
    assert "RECOMMENDED NEXT CHECKS" in formatted


def test_nopis_terminology_constraints():
    supervisor = SupervisorOrchestrator()
    report = supervisor.run_investigation(grid_id=4821)
    formatted = supervisor.format_report(report).lower()
    
    # Must not claim confirmed congestion
    assert "confirmed congestion" not in formatted
    # Must not use MB or Megabytes as activity units
    assert "megabytes" not in formatted
