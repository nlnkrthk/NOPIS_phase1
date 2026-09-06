#!/usr/bin/env python3
"""
NOPIS Project Slash Commands Implementation (C7 Tasks 264-268)

Provides reusable, deterministic CLI tools backing the Claude Code slash commands:
  - /check-pipeline
  - /explain-grid
  - /review-anomaly
  - /test-api
  - /network-health
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

# Ensure project root is in path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from Phase_4.database import SessionLocal
from Phase_4.services import (
    get_grid_activity,
    get_alerts,
    get_grid_features,
    predict_grid_risk,
)
from sqlalchemy import text


# =============================================================================
# 1. /check-pipeline (NOC-oriented)
# =============================================================================
def check_pipeline() -> Dict[str, Any]:
    """Inspects ingestion logs, rejected files, and warehouse freshness."""
    db = SessionLocal()
    try:
        # Warehouse dim_time freshness
        latest_ts_row = db.execute(text("SELECT MAX(timestamp) FROM dim_time")).first()
        latest_ts = str(latest_ts_row[0]) if latest_ts_row and latest_ts_row[0] else None

        # Count total records in fact_network_activity
        fact_count_row = db.execute(text("SELECT COUNT(*) FROM fact_network_activity")).first()
        total_fact_rows = fact_count_row[0] if fact_count_row else 0
    finally:
        db.close()

    # Ingestion log inspection
    log_file = ROOT_DIR / "logs" / "ingestion_log.csv"
    valid_ingestions = 0
    invalid_ingestions = 0
    recent_entries = []
    if log_file.exists():
        with open(log_file, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
            header = lines[0].split(",") if lines else []
            for line in lines[1:]:
                parts = line.split(",", 4)
                if len(parts) >= 4:
                    status = parts[1]
                    if status == "VALID":
                        valid_ingestions += 1
                    else:
                        invalid_ingestions += 1
                recent_entries.append(line)

    # Rejected directory inspection
    rejected_dir = ROOT_DIR / "data" / "rejected"
    rejected_files = list(rejected_dir.glob("*.csv")) if rejected_dir.exists() else []

    status_str = "HEALTHY"
    if invalid_ingestions > 0 or len(rejected_files) > 0:
        status_str = "DEGRADED"
    if not latest_ts or total_fact_rows == 0:
        status_str = "UNHEALTHY"

    return {
        "command": "/check-pipeline",
        "status": status_str,
        "latest_warehouse_timestamp": latest_ts,
        "total_warehouse_fact_rows": total_fact_rows,
        "valid_ingestions_count": valid_ingestions,
        "invalid_ingestions_count": invalid_ingestions,
        "rejected_files_count": len(rejected_files),
        "rejected_files": [f.name for f in rejected_files],
        "log_path": str(log_file.relative_to(ROOT_DIR)) if log_file.exists() else None,
    }


def format_check_pipeline(data: Dict[str, Any]) -> str:
    out = []
    out.append("=================================================================")
    out.append(f"PIPELINE STATUS: {data['status']}")
    out.append("=================================================================")
    out.append(f"- Latest Warehouse Timestamp : {data['latest_warehouse_timestamp'] or 'NONE'}")
    out.append(f"- Total Fact Records Loaded  : {data['total_warehouse_fact_rows']:,}")
    out.append(f"- Valid Ingestion Batches    : {data['valid_ingestions_count']}")
    out.append(f"- Invalid Ingestions Logged  : {data['invalid_ingestions_count']}")
    out.append(f"- Files in data/rejected/    : {data['rejected_files_count']}")
    if data["rejected_files"]:
        out.append(f"  Rejected Files: {', '.join(data['rejected_files'])}")
    out.append("\nQuality Assessment:")
    if data["status"] == "HEALTHY":
        out.append("  [OK] Ingestion pipeline and warehouse data are current and validated.")
    elif data["status"] == "DEGRADED":
        out.append("  [WARNING] Rejected rows or invalid files detected in landing history.")
    else:
        out.append("  [CRITICAL] Warehouse is empty or missing timestamps.")
    return "\n".join(out)


# =============================================================================
# 2. /explain-grid (NOC-oriented)
# =============================================================================
def explain_grid(grid_id: int, as_of: Optional[str] = None) -> Dict[str, Any]:
    """Gathers activity, features, anomalies, and location to produce 4 standard sections."""
    db = SessionLocal()
    try:
        # Location
        loc_row = db.execute(
            text("SELECT centroid_lon, centroid_lat FROM dim_grid WHERE grid_id = :gid"),
            {"gid": grid_id}
        ).first()
        coords = (float(loc_row[0]), float(loc_row[1])) if loc_row else (None, None)

        # Statistical anomaly score
        nas_row = db.execute(
            text("""
                SELECT current_value, baseline_value, deviation, anomaly_score, direction
                FROM network_anomaly_scores
                WHERE grid_id = :gid
                ORDER BY feature_timestamp DESC
                LIMIT 1
            """),
            {"gid": grid_id}
        ).mappings().first()

        # ML Features
        parsed_as_of = datetime.fromisoformat(as_of) if as_of else None
        features = get_grid_features(db, grid_id=grid_id, as_of=parsed_as_of)

        # Recent activity
        activity_history = get_grid_activity(db, grid_id=grid_id, as_of=parsed_as_of)
        latest_point = activity_history[-1] if activity_history else {}

        # ML Risk
        from Phase_4.schemas import PredictRiskRequest
        risk_req = PredictRiskRequest(grid_id=grid_id, as_of=parsed_as_of)
        risk_resp = predict_grid_risk(db, risk_req)
    finally:
        db.close()

    # Determine overall severity
    risk_level = risk_resp.get("risk_level", "LOW") if risk_resp else "LOW"
    anomaly_dir = nas_row.get("direction", "NORMAL") if nas_row else "NORMAL"
    
    if risk_level in ("HIGH", "CRITICAL") or anomaly_dir == "HIGH":
        severity = "ELEVATED" if risk_level != "CRITICAL" else "CRITICAL"
    else:
        severity = "NORMAL"

    return {
        "grid_id": grid_id,
        "severity": severity,
        "coordinates": coords,
        "latest_activity": latest_point,
        "features": features,
        "statistical_anomaly": dict(nas_row) if nas_row else None,
        "ml_risk": risk_resp,
    }


def format_explain_grid(data: Dict[str, Any]) -> str:
    gid = data["grid_id"]
    coords = data["coordinates"]
    latest = data["latest_activity"] or {}
    feats = data["features"] or {}
    nas = data["statistical_anomaly"] or {}
    risk = data["ml_risk"] or {}

    out = []
    out.append("=================================================================")
    out.append(f"EXPLAIN GRID: {gid}")
    out.append("=================================================================\n")

    out.append(f"SEVERITY:\n{data['severity']}\n")

    out.append("EVIDENCE:")
    out.append(f"- Coordinates: Lon {coords[0]}, Lat {coords[1]}" if coords[0] else "- Coordinates: Unknown")
    out.append(f"- Timestamp: {latest.get('timestamp', 'N/A')}")
    out.append(f"- Observed Total Activity: {latest.get('total_activity', 0.0):.2f} (Proportional activity units)")
    out.append(f"  * Internet Activity: {latest.get('internet_activity', 0.0):.2f} (Share: {latest.get('internet_share', 0.0)*100:.1f}%)")
    out.append(f"  * Total SMS: {latest.get('total_sms', 0.0):.2f} | Total Calls: {latest.get('total_calls', 0.0):.2f}")
    if feats:
        out.append(f"- ML2 Features:")
        out.append(f"  * 24h Average Activity: {feats.get('avg_activity', 0.0):.2f}")
        out.append(f"  * Activity Growth Ratio: {feats.get('activity_growth', 0.0):.2f}")
        out.append(f"  * Peak-to-Mean Ratio: {feats.get('peak_ratio', 0.0):.2f}")
        out.append(f"  * Coefficient of Variation: {feats.get('variability', 0.0):.2f}")
    if nas:
        out.append(f"- Historical Baseline: {nas.get('baseline_value', 0.0):.2f} (Deviation: {nas.get('deviation', 0.0):+.2f}, {nas.get('anomaly_score', 0.0):+.1f}%)")
        out.append(f"- Anomaly Direction: {nas.get('direction', 'NORMAL')}")
    if risk:
        out.append(f"- ML Classifier Risk Score: {risk.get('risk_score', 0.0):.4f} ({risk.get('risk_level', 'LOW')})")
    out.append("")

    out.append("INTERPRETATION:")
    tot_act = latest.get("total_activity", 0.0)
    base_act = nas.get("baseline_value", 0.0)
    growth = feats.get("activity_growth", 1.0)
    if nas.get("direction") == "HIGH":
        out.append(f"- Grid {gid} is exhibiting activity {nas.get('anomaly_score', 0.0):.1f}% above its historical median for this hour.")
    elif tot_act > 0:
        out.append(f"- Grid {gid} is operating within normal baseline activity levels.")
    else:
        out.append(f"- Grid {gid} shows zero or negligible recorded telemetry.")
    if growth > 1.5:
        out.append(f"- Activity growth ratio ({growth:.2f}) indicates a sharp upward acceleration over the last 12 hours.")
    out.append("- NOTE: High activity values represent proportional traffic intensity, NOT confirmed congestion or physical capacity overload.")
    out.append("")

    out.append("NEXT CHECKS:")
    out.append(f"1. Compare Grid {gid} against neighboring cells in the cluster to identify localized vs. sector-wide patterns.")
    out.append("2. Inspect CDR/call drop counters in OMC/RAN operations before concluding any degradation.")
    out.append("3. Review /review-anomaly for signal convergence across rule-based and ML models.")

    return "\n".join(out)


# =============================================================================
# 3. /review-anomaly (NOC-oriented)
# =============================================================================
def review_anomaly(grid_id: int, as_of: Optional[str] = None) -> Dict[str, Any]:
    """Compares rule-based alerts, ML classifier output, and statistical anomaly scores."""
    db = SessionLocal()
    try:
        parsed_as_of = datetime.fromisoformat(as_of) if as_of else None

        # 1. Rule-based alert
        all_alerts = get_alerts(db, limit=100, as_of=parsed_as_of) or []
        grid_alerts = [a for a in all_alerts if a["grid_id"] == grid_id]
        rule_alert = grid_alerts[0] if grid_alerts else None

        # 2. Classifier output
        from Phase_4.schemas import PredictRiskRequest
        risk_req = PredictRiskRequest(grid_id=grid_id, as_of=parsed_as_of)
        risk_resp = predict_grid_risk(db, risk_req)

        # 3. Anomaly score from network_anomaly_scores
        nas_row = db.execute(
            text("""
                SELECT feature_timestamp, current_value, baseline_value, deviation, anomaly_score, direction
                FROM network_anomaly_scores
                WHERE grid_id = :gid
                ORDER BY feature_timestamp DESC
                LIMIT 1
            """),
            {"gid": grid_id}
        ).mappings().first()
    finally:
        db.close()

    rule_signal = rule_alert.get("alert_type") if rule_alert else "NONE"
    rule_severity = rule_alert.get("severity") if rule_alert else "NONE"
    classifier_level = risk_resp.get("risk_level", "LOW") if risk_resp else "LOW"
    classifier_score = risk_resp.get("risk_score", 0.0) if risk_resp else 0.0
    anomaly_direction = nas_row.get("direction", "NORMAL") if nas_row else "NORMAL"
    anomaly_pct = nas_row.get("anomaly_score", 0.0) if nas_row else 0.0

    # Evaluate agreement
    is_rule_active = rule_signal != "NONE"
    is_class_elevated = classifier_level in ("MEDIUM", "HIGH", "CRITICAL")
    is_stat_anomaly = anomaly_direction in ("HIGH", "LOW")

    agreements = []
    disagreements = []

    if is_class_elevated and is_stat_anomaly:
        agreement_status = "AGREEMENT (ELEVATED)"
        agreements.append("Both ML Classifier and Statistical Baseline detect abnormal behavior.")
    elif not is_class_elevated and not is_stat_anomaly and not is_rule_active:
        agreement_status = "AGREEMENT (NORMAL)"
        agreements.append("All signals agree the grid is operating within standard operating bounds.")
    else:
        agreement_status = "PARTIAL DISAGREEMENT"
        if is_stat_anomaly and not is_class_elevated:
            disagreements.append(
                f"Statistical score shows {anomaly_direction} deviation ({anomaly_pct:+.1f}%), "
                f"but ML Classifier predicts {classifier_level} risk (score: {classifier_score:.4f}). "
                "Reason: ML classifier factors in 24h peak_ratio and internet_share, dampening isolated surges."
            )
        if is_rule_active and not is_class_elevated:
            disagreements.append(
                f"Rule alert triggered ({rule_signal} - {rule_severity}), but ML Classifier scored {classifier_score:.4f}. "
                "Reason: Static heuristic thresholds do not account for historical grid-level diurnal baseline."
            )
        if is_class_elevated and not is_stat_anomaly:
            disagreements.append(
                f"ML Classifier predicts {classifier_level} risk, but statistical anomaly score is {anomaly_direction}. "
                "Reason: Multi-feature risk model detected abnormal feature velocity rather than single-metric deviation."
            )

    return {
        "grid_id": grid_id,
        "rule_alert": {
            "active": is_rule_active,
            "type": rule_signal,
            "severity": rule_severity,
            "reason": rule_alert.get("reason") if rule_alert else None,
        },
        "classifier": {
            "risk_score": classifier_score,
            "risk_level": classifier_level,
            "model_version": risk_resp.get("model_version") if risk_resp else None,
        },
        "statistical_anomaly": {
            "direction": anomaly_direction,
            "anomaly_score_pct": anomaly_pct,
            "current_value": float(nas_row.get("current_value") or 0.0) if nas_row else 0.0,
            "baseline_value": float(nas_row.get("baseline_value") or 0.0) if nas_row else 0.0,
            "deviation": float(nas_row.get("deviation") or 0.0) if nas_row else 0.0,
        },
        "agreement_status": agreement_status,
        "agreements": agreements,
        "disagreements": disagreements,
    }


def format_review_anomaly(data: Dict[str, Any]) -> str:
    gid = data["grid_id"]
    ra = data["rule_alert"]
    cl = data["classifier"]
    sa = data["statistical_anomaly"]

    out = []
    out.append("=================================================================")
    out.append(f"ANOMALY SIGNAL REVIEW FOR GRID: {gid}")
    out.append("=================================================================\n")

    out.append("1. Rule-Based Alert:")
    out.append(f"   Status  : {'ACTIVE' if ra['active'] else 'NO ALERT'}")
    out.append(f"   Type    : {ra['type']} (Severity: {ra['severity']})")
    if ra.get("reason"):
        out.append(f"   Reason  : {ra['reason']}")
    out.append("")

    out.append("2. ML Risk Classifier:")
    out.append(f"   Risk Level : {cl['risk_level']}")
    out.append(f"   Risk Score : {cl['risk_score']:.4f}")
    out.append(f"   Model Ver  : {cl['model_version'] or 'v1'}")
    out.append("")

    out.append("3. Statistical Anomaly Score:")
    out.append(f"   Direction      : {sa['direction']}")
    out.append(f"   Score (% Dev)  : {sa['anomaly_score_pct']:+.1f}%")
    out.append(f"   Current vs Base: {sa['current_value']:.2f} vs {sa['baseline_value']:.2f} (Delta: {sa['deviation']:+.2f})")
    out.append("")

    out.append("SIGNAL CONVERGENCE:")
    out.append(f"Result: {data['agreement_status']}")
    if data["agreements"]:
        for a in data["agreements"]:
            out.append(f"- {a}")
    if data["disagreements"]:
        out.append("\nEXPLANATION OF DISAGREEMENT:")
        for d in data["disagreements"]:
            out.append(f"- {d}")

    return "\n".join(out)


# =============================================================================
# 4. /test-api (Engineering-oriented)
# =============================================================================
def test_api(target_test: Optional[str] = None) -> Dict[str, Any]:
    """Runs the API test suite and produces a concise summary."""
    test_target = target_test or "Phase_4/tests/"
    cmd = [sys.executable, "-m", "pytest", test_target, "-v"]
    
    start_time = datetime.now()
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True
    )
    duration = (datetime.now() - start_time).total_seconds()

    output = proc.stdout + "\n" + proc.stderr
    
    passed = 0
    failed = 0
    warnings = 0
    for line in output.splitlines():
        if " passed" in line and (" in " in line or line.endswith("passed")):
            # Pytest summary line e.g. "==== 42 passed, 16 warnings in 10.5s ===="
            parts = line.replace("=", "").strip().split(",")
            for p in parts:
                p = p.strip()
                if "passed" in p:
                    try:
                        passed = int(p.split()[0])
                    except ValueError:
                        pass
                elif "failed" in p:
                    try:
                        failed = int(p.split()[0])
                    except ValueError:
                        pass
                elif "warning" in p:
                    try:
                        warnings = int(p.split()[0])
                    except ValueError:
                        pass

    return {
        "command": " ".join(cmd),
        "exit_code": proc.returncode,
        "status": "PASS" if proc.returncode == 0 else "FAIL",
        "passed": passed,
        "failed": failed,
        "warnings": warnings,
        "duration_seconds": round(duration, 2),
        "raw_output": output,
    }


def format_test_api(data: Dict[str, Any]) -> str:
    out = []
    out.append("=================================================================")
    out.append(f"API TEST SUITE SUMMARY: {data['status']}")
    out.append("=================================================================")
    out.append(f"- Command  : {data['command']}")
    out.append(f"- Passed   : {data['passed']}")
    out.append(f"- Failed   : {data['failed']}")
    out.append(f"- Warnings : {data['warnings']}")
    out.append(f"- Duration : {data['duration_seconds']}s")
    out.append(f"- Exit Code: {data['exit_code']}")
    if data["failed"] > 0:
        out.append("\nFAILURES IDENTIFIED:")
        for line in data["raw_output"].splitlines():
            if line.startswith("FAILED "):
                out.append(f"  * {line}")
    else:
        out.append("\nAll executed API tests passed without regression.")
    return "\n".join(out)


# =============================================================================
# 5. /network-health (Engineering-oriented)
# =============================================================================
def network_health(target_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Checks the canonical (grid_id, timestamp) grain on hourly_grid_summary.
    Detects any duplicate combinations and returns PASS or FAIL.
    """
    path_to_check = Path(target_path) if target_path else ROOT_DIR / "data" / "analytics" / "hourly_grid_summary"
    
    duplicate_count = 0
    total_records = 0
    duplicate_samples = []

    # Check Parquet dataset if directory exists
    if path_to_check.exists():
        import pyarrow.parquet as pq
        import pandas as pd
        
        try:
            table = pq.read_table(str(path_to_check), columns=["grid_id", "timestamp"])
            df = table.to_pandas()
            total_records = len(df)
            
            dupes = df[df.duplicated(subset=["grid_id", "timestamp"], keep=False)]
            if not dupes.empty:
                unique_dupes = dupes.drop_duplicates(subset=["grid_id", "timestamp"])
                duplicate_count = len(unique_dupes)
                for _, row in unique_dupes.head(5).iterrows():
                    duplicate_samples.append({
                        "grid_id": int(row["grid_id"]),
                        "timestamp": str(row["timestamp"])
                    })
        except Exception as e:
            return {
                "status": "ERROR",
                "target_path": str(path_to_check),
                "error": str(e),
                "duplicate_count": -1,
            }
    else:
        # Fallback to MySQL fact_network_activity
        db = SessionLocal()
        try:
            row_count = db.execute(text("SELECT COUNT(*) FROM fact_network_activity")).scalar()
            total_records = row_count or 0
            dupe_query = text("""
                SELECT f.grid_id, f.time_key, COUNT(*) as cnt
                FROM fact_network_activity f
                GROUP BY f.grid_id, f.time_key
                HAVING COUNT(*) > 1
                LIMIT 5
            """)
            rows = db.execute(dupe_query).fetchall()
            duplicate_count = len(rows)
            for r in rows:
                duplicate_samples.append({"grid_id": r[0], "time_key": r[1], "count": r[2]})
        finally:
            db.close()

    is_pass = (duplicate_count == 0)
    return {
        "command": "/network-health",
        "target_path": str(path_to_check.relative_to(ROOT_DIR)) if path_to_check.is_relative_to(ROOT_DIR) else str(path_to_check),
        "canonical_grain": "(grid_id, timestamp)",
        "total_evaluated_records": total_records,
        "duplicate_count": duplicate_count,
        "status": "PASS" if is_pass else "FAIL",
        "duplicate_samples": duplicate_samples,
    }


def format_network_health(data: Dict[str, Any]) -> str:
    out = []
    out.append("=================================================================")
    out.append(f"NETWORK GRAIN HEALTH CHECK: {data['status']}")
    out.append("=================================================================")
    out.append(f"- Evaluated Target : {data.get('target_path')}")
    out.append(f"- Canonical Grain  : {data.get('canonical_grain')}")
    out.append(f"- Records Checked  : {data.get('total_evaluated_records', 0):,}")
    out.append(f"- Duplicate Keys   : {data.get('duplicate_count', 0)}")
    
    if data["status"] == "PASS":
        out.append("\nGrain Integrity Verified: Every (grid_id, timestamp) pair is unique.")
    else:
        out.append("\nGRAIN VIOLATION DETECTED: Found duplicate (grid_id, timestamp) combinations:")
        for sample in data.get("duplicate_samples", []):
            out.append(f"  * Grid {sample.get('grid_id')} at {sample.get('timestamp') or sample.get('time_key')}")
    return "\n".join(out)


# =============================================================================
# CLI Dispatcher
# =============================================================================
def main():
    if len(sys.argv) < 2:
        print("Usage: python project_commands.py <command-name> [args...]")
        print("Available commands: check-pipeline, explain-grid, review-anomaly, test-api, network-health")
        sys.exit(1)

    cmd = sys.argv[1].lower().lstrip("/")

    if cmd == "check-pipeline":
        res = check_pipeline()
        print(format_check_pipeline(res))

    elif cmd == "explain-grid":
        if len(sys.argv) < 3:
            print("Error: grid_id is required. Example: python project_commands.py explain-grid 4821")
            sys.exit(1)
        grid_id = int(sys.argv[2])
        as_of = sys.argv[3] if len(sys.argv) > 3 else None
        res = explain_grid(grid_id, as_of)
        print(format_explain_grid(res))

    elif cmd == "review-anomaly":
        if len(sys.argv) < 3:
            print("Error: grid_id is required. Example: python project_commands.py review-anomaly 4821")
            sys.exit(1)
        grid_id = int(sys.argv[2])
        as_of = sys.argv[3] if len(sys.argv) > 3 else None
        res = review_anomaly(grid_id, as_of)
        print(format_review_anomaly(res))

    elif cmd == "test-api":
        target = sys.argv[2] if len(sys.argv) > 2 else None
        res = test_api(target)
        print(format_test_api(res))
        sys.exit(res["exit_code"])

    elif cmd == "network-health":
        target = sys.argv[2] if len(sys.argv) > 2 else None
        res = network_health(target)
        print(format_network_health(res))
        sys.exit(0 if res["status"] == "PASS" else 1)

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
