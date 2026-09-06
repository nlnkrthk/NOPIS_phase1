"""C16 read-only comparison of raw and curated investigation context."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Mapping

from sqlalchemy import create_engine, text

DATABASE_URL = "mysql+pymysql://root:root@localhost/nopis"
ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = Path(__file__).with_name("c16_context_cost_results.json")


def _engine():
    return create_engine(DATABASE_URL, connect_args={"connect_timeout": 10}, pool_pre_ping=True)


def _json_size(value) -> dict[str, int]:
    serialized = json.dumps(value, default=str, separators=(",", ":"))
    characters = len(serialized)
    utf8_bytes = len(serialized.encode("utf-8"))
    return {
        "serialized_characters": characters,
        "serialized_bytes": utf8_bytes,
        # Estimate only: tokenization depends on the selected model/tokenizer.
        "estimated_tokens_at_4_chars": (characters + 3) // 4,
    }


def _pipeline_status() -> dict:
    log_path = ROOT_DIR / "logs" / "ingestion_log.csv"
    rejected_path = ROOT_DIR / "data" / "rejected"
    valid = invalid = 0
    if log_path.exists():
        lines = [line.strip() for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        for line in lines[1:]:
            parts = line.split(",", 4)
            if len(parts) >= 4:
                if parts[1] == "VALID":
                    valid += 1
                else:
                    invalid += 1
    rejected = sorted(path.name for path in rejected_path.glob("*.csv")) if rejected_path.exists() else []
    return {"status": "DEGRADED" if invalid or rejected else "HEALTHY", "valid_ingestions": valid, "invalid_ingestions": invalid, "rejected_files": len(rejected)}


def _row_mapping(row):
    if row is None:
        return None
    if isinstance(row, Mapping):
        return dict(row)
    return dict(row._mapping)


def run() -> dict:
    engine = _engine()
    try:
        with engine.connect() as conn:
            # 1. Estimate the context size of a raw multi-grid extract using the project's real row counts.
            raw_count, raw_grid_count, raw_time_count = conn.execute(text("""
                SELECT COUNT(*), COUNT(DISTINCT f.grid_id), COUNT(DISTINCT f.time_key)
                FROM fact_network_activity f
            """)).one()
            raw_sample_started = time.perf_counter()
            raw_sample = [_row_mapping(row) for row in conn.execute(text("""
                SELECT f.grid_id, t.timestamp, f.total_activity, f.internet_share,
                       f.total_sms, f.total_calls
                FROM fact_network_activity f
                JOIN dim_time t ON f.time_key = t.time_key
                ORDER BY t.timestamp, f.grid_id
                LIMIT 100
            """))]
            raw_sample_latency_ms = round((time.perf_counter() - raw_sample_started) * 1000, 3)

            raw_context = [{key: row[key] for key in row} for row in raw_sample]
            full_row_estimate = {
                "row_count": int(raw_count),
                "grid_count": int(raw_grid_count),
                "hour_count": int(raw_time_count),
                "sample_rows_used_for_safe_experiment": len(raw_context),
                "sample_size": _json_size(raw_context),
                "estimated_full_context_size": {
                    "serialized_characters": round(_json_size(raw_context)["serialized_characters"] * raw_count / len(raw_context)),
                    "estimated_tokens_at_4_chars": round(_json_size(raw_context)["estimated_tokens_at_4_chars"] * raw_count / len(raw_context)),
                    "method": "100-row serialized JSON sample scaled by measured total row count; estimate, not a tokenizer measurement",
                },
            }

            # 2. Create a curated evidence package containing approximately 10-20 relevant records for the question: "Which grids need operational attention right now, and why?"
            curated_query_started = time.perf_counter()
            latest_anomaly = conn.execute(text("SELECT MAX(feature_timestamp) FROM network_anomaly_scores")).scalar()
            anomaly_rows = conn.execute(text("""
                SELECT grid_id, feature_timestamp, current_value, baseline_value,
                       deviation, anomaly_score, direction, reason
                FROM network_anomaly_scores
                WHERE feature_timestamp = :latest_anomaly
                ORDER BY anomaly_score DESC, grid_id ASC
                LIMIT 10
            """), {"latest_anomaly": latest_anomaly}).mappings().all()

            curated_records = []
            for anomaly in anomaly_rows:
                grid_id = anomaly["grid_id"]
                activity = conn.execute(text("""
                    SELECT t.timestamp, f.total_activity, f.internet_activity, f.internet_share
                    FROM fact_network_activity f
                    JOIN dim_time t ON f.time_key = t.time_key
                    WHERE f.grid_id = :grid_id AND t.timestamp <= :as_of
                    ORDER BY t.timestamp DESC LIMIT 1
                """), {"grid_id": grid_id, "as_of": anomaly["feature_timestamp"]}).mappings().first()
                features = conn.execute(text("""
                    SELECT feature_timestamp, avg_activity, activity_growth, active_hours,
                           peak_ratio, variability, internet_share, data_quality_status
                    FROM grid_features WHERE grid_id = :grid_id
                    ORDER BY feature_timestamp DESC LIMIT 1
                """), {"grid_id": grid_id}).mappings().first()
                risk = conn.execute(text("""
                    SELECT feature_timestamp, risk_score, risk_level, model_version
                    FROM network_risk_scores
                    WHERE grid_id = :grid_id
                    ORDER BY feature_timestamp DESC LIMIT 1
                """), {"grid_id": grid_id}).mappings().first()
                curated_records.append({
                    "grid_id": int(grid_id),
                    "anomaly": _row_mapping(anomaly),
                    "latest_activity_at_or_before_anomaly": _row_mapping(activity),
                    "latest_stored_features": _row_mapping(features),
                    "latest_stored_risk": _row_mapping(risk),
                })
            curated_query_latency_ms = round((time.perf_counter() - curated_query_started) * 1000, 3)

            curated_context = {
                "question": "Which grids need operational attention right now, and why?",
                "pipeline_status": _pipeline_status(),
                "anomaly_as_of": latest_anomaly,
                "grid_evidence_records": curated_records,
                "source_contracts": {
                    "activity": "fact_network_activity JOIN dim_time; canonical grain is one grid per hourly timestamp",
                    "anomaly": "network_anomaly_scores",
                    "features": "grid_features",
                    "risk": "network_risk_scores; latest stored risk snapshot",
                    "pipeline": "logs/ingestion_log.csv and data/rejected/; equivalent API is GET /network/pipeline/status",
                },
            }
            curated_started = time.perf_counter()
            curated_size = _json_size(curated_context)
            curated_latency_ms = round((time.perf_counter() - curated_started) * 1000, 3)

            # 3. Run and compare two designs: Design A raw context and Design B curated context.
            raw_answer = _answer_from_raw_sample(raw_context, raw_count)
            curated_answer = _answer_from_curated(curated_context)
            result = {
                "measured_at_utc": datetime.now(timezone.utc).isoformat(),
                "data_counts": {
                    "fact_network_activity": int(raw_count),
                    "dim_grid": int(conn.execute(text("SELECT COUNT(*) FROM dim_grid")).scalar()),
                    "dim_time": int(conn.execute(text("SELECT COUNT(*) FROM dim_time")).scalar()),
                    "network_anomaly_scores": int(conn.execute(text("SELECT COUNT(*) FROM network_anomaly_scores")).scalar()),
                    "grid_features": int(conn.execute(text("SELECT COUNT(*) FROM grid_features")).scalar()),
                    "network_risk_scores": int(conn.execute(text("SELECT COUNT(*) FROM network_risk_scores")).scalar()),
                },
                "design_a_raw_context": {
                    **full_row_estimate,
                    "observed_sample_query_latency_ms": raw_sample_latency_ms,
                    "answer": raw_answer,
                    "quality_assessment": "Low for the operational question: the safe sample is not a complete ranking and the full estimate is too large to send.",
                },
                "design_b_curated_context": {
                    "record_count": len(curated_records),
                    "context_size": curated_size,
                    "query_latency_not_including_model_ms": curated_query_latency_ms,
                    "answer": curated_answer,
                    "package": curated_context,
                    "quality_assessment": "Higher relevance: one record per top latest-anomaly grid plus pipeline context, with source fields retained.",
                },
                "comparison": {
                    "latency_note": "Measured database query timing is recorded for Design A; model latency and token billing were not measured because no model request was made.",
                    "cost_note": "Design A cost is proportional to the estimated full token count; Design B cost is proportional to the measured curated token estimate. Provider prices were not assumed.",
                    "reliability_note": "Design B preserves timestamps and source tables but remains limited by stale/missing feature or risk snapshots and pipeline status.",
                },
            }
            OUTPUT_PATH.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
            return result
    finally:
        engine.dispose()


def _answer_from_raw_sample(rows, total_rows: int) -> str:
    if not rows:
        return f"No answer: the raw sample contained no rows; measured total rows={total_rows}."
    top = max(rows, key=lambda row: float(row.get("total_activity") or 0.0))
    return (f"The safe raw experiment sample contains {len(rows)} rows out of {total_rows} measured rows. "
            f"Its largest observed proportional activity value is grid {top['grid_id']} at {top['timestamp']} "
            f"with total_activity={top['total_activity']}. This is sample-only evidence, not a complete attention ranking.")


def _answer_from_curated(curated_context: dict) -> str:
    records = curated_context["grid_evidence_records"]
    high = [record for record in records if record["anomaly"].get("direction") == "HIGH"]
    grid_ids = ", ".join(str(record["grid_id"]) for record in high)
    return (f"At anomaly timestamp {curated_context['anomaly_as_of']}, the curated package identifies "
            f"{len(high)} grids with HIGH anomaly direction: {grid_ids}. "
            "The reasons are the observed current-versus-baseline activity and anomaly scores in each record. "
            "Pipeline status and feature/risk timestamps must be checked before treating this as a complete current assessment.")


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, default=str))
