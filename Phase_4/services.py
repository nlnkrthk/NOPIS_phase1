from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import text
from sqlalchemy.orm import Session

# 133. Query the warehouse and analytics layer rather than raw CSV.
def get_network_summary(db: Session, as_of: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
    # 131.Accept an optional as_of query parameter. When absent, default to the configured AS_OF — the maximum timestamp in the analytics layer. Never hardcode a date.
    if as_of is None:
        max_ts_query = text("""
            SELECT MAX(t.timestamp) 
            FROM dim_time t
            JOIN fact_network_activity f ON f.time_key = t.time_key
        """)
        result = db.execute(max_ts_query).scalar()
        if result is None:
            return None
        effective_as_of = result
    else:
        # Round down to nearest hour (data is hourly granularity)
        rounded_as_of = as_of.replace(minute=0, second=0, microsecond=0)
        
        # Check if the requested timestamp exists in the analytics fact table
        check_query = text("""
            SELECT 1 
            FROM dim_time t
            JOIN fact_network_activity f ON f.time_key = t.time_key
            WHERE t.timestamp = :as_of
            LIMIT 1
        """)
        exists = db.execute(check_query, {"as_of": rounded_as_of}).scalar()
        if not exists:
            return None
        effective_as_of = rounded_as_of

    # 130. Return total_activity, active_grids, peak_hour and top_grid.
    # 1. Calculate total_activity across the ENTIRE dataset (not just one hour).
    #    The dashboard KPI answers "how much activity in total" — scoping it to a
    #    single as_of timestamp produces a single-hour sum which is misleading.
    total_activity_query = text("""
        SELECT COALESCE(SUM(total_activity), 0.0)
        FROM fact_network_activity
    """)
    total_activity = float(db.execute(total_activity_query).scalar() or 0.0)

    # 2. Calculate active_grids (distinct grids with activity at effective as_of timestamp)
    active_grids_query = text("""
        SELECT COUNT(DISTINCT f.grid_id)
        FROM fact_network_activity f
        JOIN dim_time t ON f.time_key = t.time_key
        WHERE t.timestamp = :as_of
    """)
    active_grids = int(db.execute(active_grids_query, {"as_of": effective_as_of}).scalar() or 0)

    # 3. Calculate peak_hour (hour of day 0-23 with highest activity across analytics dataset)
    peak_hour_query = text("""
        SELECT t.hour, SUM(f.total_activity) AS activity
        FROM fact_network_activity f
        JOIN dim_time t ON f.time_key = t.time_key
        GROUP BY t.hour
        ORDER BY activity DESC
        LIMIT 1
    """)
    peak_hour_row = db.execute(peak_hour_query).first()
    peak_hour = int(peak_hour_row[0]) if peak_hour_row is not None else 0

    # 4. Calculate top_grid (grid with highest total activity at effective as_of timestamp)
    top_grid_query = text("""
        SELECT f.grid_id, SUM(f.total_activity) AS activity
        FROM fact_network_activity f
        JOIN dim_time t ON f.time_key = t.time_key
        WHERE t.timestamp = :as_of
        GROUP BY f.grid_id
        ORDER BY activity DESC
        LIMIT 1
    """)
    top_grid_row = db.execute(top_grid_query, {"as_of": effective_as_of}).first()
    top_grid = int(top_grid_row[0]) if top_grid_row is not None else 0

    return {
        "total_activity": total_activity,
        "active_grids": active_grids,
        "peak_hour": peak_hour,
        "top_grid": top_grid,
        "as_of": effective_as_of
    }

# 136. Add optional date, hour and as_of query parameters. Default the window to the trailing 24 hourly intervals ending at AS_OF.
# 138. Return 404 for an unknown grid — and treat any grid_id outside 1–10000 as unknown.
def get_grid_activity(
    db: Session, 
    grid_id: int, 
    filter_date: Optional[Any] = None, 
    filter_hour: Optional[int] = None, 
    as_of: Optional[datetime] = None
) -> Optional[list]:
    # Validate grid boundary 1-10000
    if grid_id < 1 or grid_id > 10000:
        return None

    # Verify grid exists in dim_grid
    grid_exists_query = text("SELECT 1 FROM dim_grid WHERE grid_id = :grid_id LIMIT 1")
    if not db.execute(grid_exists_query, {"grid_id": grid_id}).scalar():
        return None

    # Determine effective as_of
    if as_of is None:
        max_ts_query = text("""
            SELECT MAX(t.timestamp) 
            FROM dim_time t
            JOIN fact_network_activity f ON f.time_key = t.time_key
        """)
        effective_as_of = db.execute(max_ts_query).scalar()
        if effective_as_of is None:
            return []
    else:
        # Round down to nearest hour (data is hourly granularity)
        effective_as_of = as_of.replace(minute=0, second=0, microsecond=0)

    # Build query dynamically based on date/hour/default filters
    params = {"grid_id": grid_id, "as_of": effective_as_of}
    where_clauses = ["f.grid_id = :grid_id"]

    if filter_date is not None:
        where_clauses.append("t.date = :filter_date")
        params["filter_date"] = filter_date

    if filter_hour is not None:
        where_clauses.append("t.hour = :filter_hour")
        params["filter_hour"] = filter_hour

    # If no specific date filter is provided, bound by effective_as_of
    if filter_date is None:
        where_clauses.append("t.timestamp <= :as_of")

    # Default window: trailing 24 hourly intervals ending at as_of
    is_default_window = (filter_date is None and filter_hour is None)

    where_sql = " AND ".join(where_clauses)

    if is_default_window:
        query_sql = f"""
            SELECT * FROM (
                SELECT 
                    f.grid_id,
                    t.timestamp,
                    t.date,
                    t.hour,
                    f.sms_in,
                    f.sms_out,
                    f.call_in,
                    f.call_out,
                    f.internet_activity,
                    f.total_sms,
                    f.total_calls,
                    f.total_activity,
                    f.internet_share
                FROM fact_network_activity f
                JOIN dim_time t ON f.time_key = t.time_key
                WHERE {where_sql}
                ORDER BY t.timestamp DESC
                LIMIT 24
            ) sub
            ORDER BY sub.timestamp ASC
        """
    else:
        query_sql = f"""
            SELECT 
                f.grid_id,
                t.timestamp,
                t.date,
                t.hour,
                f.sms_in,
                f.sms_out,
                f.call_in,
                f.call_out,
                f.internet_activity,
                f.total_sms,
                f.total_calls,
                f.total_activity,
                f.internet_share
            FROM fact_network_activity f
            JOIN dim_time t ON f.time_key = t.time_key
            WHERE {where_sql}
            ORDER BY t.timestamp ASC
        """

    rows = db.execute(text(query_sql), params).mappings().all()

    # Convert rows into list of dictionaries matching GridActivityPoint schema
    result = []
    for r in rows:
        result.append({
            "grid_id": int(r["grid_id"]),
            "timestamp": r["timestamp"],
            "date": r["date"],
            "hour": int(r["hour"]),
            "sms_in": float(r["sms_in"] or 0.0),
            "sms_out": float(r["sms_out"] or 0.0),
            "call_in": float(r["call_in"] or 0.0),
            "call_out": float(r["call_out"] or 0.0),
            "internet_activity": float(r["internet_activity"] or 0.0),
            "total_sms": float(r["total_sms"] or 0.0),
            "total_calls": float(r["total_calls"] or 0.0),
            "total_activity": float(r["total_activity"] or 0.0),
            "internet_share": float(r["internet_share"] or 0.0),
        })

    return result

# 140. Create GET /network/hotspots and GET /network/alerts.
# 141.Allow limit, severity and as_of query parameters.
def get_hotspots(
    db: Session,
    limit: int = 10,
    as_of: Optional[datetime] = None
) -> list:
    if as_of is None:
        max_ts_query = text("""
            SELECT MAX(t.timestamp) 
            FROM dim_time t
            JOIN fact_network_activity f ON f.time_key = t.time_key
        """)
        effective_as_of = db.execute(max_ts_query).scalar()
        if effective_as_of is None:
            return []
    else:
        # Round down to nearest hour (data is hourly granularity)
        effective_as_of = as_of.replace(minute=0, second=0, microsecond=0)

    query_sql = text("""
        SELECT 
            f.grid_id,
            t.timestamp,
            f.total_activity,
            f.total_sms AS sms_activity,
            f.total_calls AS call_activity,
            f.internet_activity
        FROM fact_network_activity f
        JOIN dim_time t ON f.time_key = t.time_key
        WHERE t.timestamp = :as_of
        ORDER BY f.total_activity DESC, f.grid_id ASC
        LIMIT :limit
    """)
    rows = db.execute(query_sql, {"as_of": effective_as_of, "limit": limit}).mappings().all()

    results = []
    for r in rows:
        act = float(r["total_activity"] or 0.0)
        if act >= 2000:
            severity = "CRITICAL"
            reason = "Extreme high network load area requiring priority NOC monitoring"
        elif act >= 1000:
            severity = "HIGH"
            reason = "High network traffic volume exceeding operational threshold"
        elif act >= 500:
            severity = "MEDIUM"
            reason = "Elevated network usage hotspot"
        else:
            severity = "LOW"
            reason = "Active operational hotspot"

        results.append({
            "grid_id": int(r["grid_id"]),
            "timestamp": r["timestamp"],
            "total_activity": act,
            "sms_activity": float(r["sms_activity"] or 0.0),
            "call_activity": float(r["call_activity"] or 0.0),
            "internet_activity": float(r["internet_activity"] or 0.0),
            "severity": severity,
            "reason": reason,
            "risk_score": None,
            "risk_level": None,
            "model_version": None,
        })
    return results

# 142. Initially serve the rule-based NP3 alerts.
# 144. Include grid_id, hourly timestamp, the relevant activity measures, status or severity, and a human-readable reason.
def get_alerts(
    db: Session,
    limit: int = 20,
    severity: Optional[str] = None,
    as_of: Optional[datetime] = None
) -> list:
    if as_of is None:
        max_ts_query = text("""
            SELECT MAX(t.timestamp) 
            FROM dim_time t
            JOIN fact_network_activity f ON f.time_key = t.time_key
        """)
        effective_as_of = db.execute(max_ts_query).scalar()
        if effective_as_of is None:
            return []
    else:
        # Round down to nearest hour (data is hourly granularity)
        effective_as_of = as_of.replace(minute=0, second=0, microsecond=0)

    query_sql = text("""
        SELECT 
            f.grid_id,
            t.timestamp,
            f.total_activity,
            f.total_sms AS sms_activity,
            f.total_calls AS call_activity,
            f.internet_activity,
            f.internet_share
        FROM fact_network_activity f
        JOIN dim_time t ON f.time_key = t.time_key
        WHERE t.timestamp = :as_of
          AND f.total_activity >= 300
        ORDER BY f.total_activity DESC, f.grid_id ASC
    """)
    rows = db.execute(query_sql, {"as_of": effective_as_of}).mappings().all()

    alerts = []
    for r in rows:
        act = float(r["total_activity"] or 0.0)
        net_share = float(r["internet_share"] or 0.0)
        net_act = float(r["internet_activity"] or 0.0)

        if act >= 2000:
            alert_type = "HIGH_ACTIVITY"
            sev = "CRITICAL"
            reason = "Extreme network activity spike requiring operational attention"
        elif act >= 1000:
            alert_type = "HIGH_ACTIVITY"
            sev = "HIGH"
            reason = "Elevated activity exceeding high operational threshold"
        elif net_act >= 500 and net_share > 0.85:
            alert_type = "INTERNET_SURGE"
            sev = "MEDIUM"
            reason = "High internet bandwidth surge with elevated data ratio"
        elif act >= 500:
            alert_type = "ACTIVITY_SPIKE"
            sev = "LOW"
            reason = "Noticeable activity surge above standard baseline"
        else:
            alert_type = "ELEVATED_ACTIVITY"
            sev = "INFO"
            reason = "Minor operational variance"

        if severity is not None and sev.upper() != severity.strip().upper():
            continue

        alerts.append({
            "grid_id": int(r["grid_id"]),
            "timestamp": r["timestamp"],
            "alert_type": alert_type,
            "severity": sev,
            "total_activity": act,
            "sms_activity": float(r["sms_activity"] or 0.0),
            "call_activity": float(r["call_activity"] or 0.0),
            "internet_activity": net_act,
            "reason": reason,
            "risk_score": None,
            "risk_level": None,
            "model_version": None,
        })

        if len(alerts) >= limit:
            break

    return alerts

# 146. Return the exact ML2 feature set: avg_activity, activity_growth, active_hours, peak_ratio, variability, internet_share, plus feature_timestamp.
# 148. Return data-quality status and feature freshness alongside the values.
# The API reads stored features; no feature engineering arithmetic is performed here.
def get_grid_features(db: Session, grid_id: int) -> Optional[dict]:
    query_sql = text("""
        SELECT 
            grid_id,
            feature_timestamp,
            avg_activity,
            activity_growth,
            active_hours,
            peak_ratio,
            variability,
            internet_share,
            data_quality_status,
            created_at
        FROM grid_features
        WHERE grid_id = :grid_id
        LIMIT 1
    """)
    row = db.execute(query_sql, {"grid_id": grid_id}).mappings().first()
    if row is None:
        return None

    # Calculate freshness metadata based on feature_timestamp relative to current analytics state
    feat_ts = row["feature_timestamp"]
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    freshness_hrs = round((now - feat_ts).total_seconds() / 3600.0, 2) if feat_ts else 0.0
    is_fresh = bool(row["data_quality_status"] == "VALID")

    return {
        "grid_id": int(row["grid_id"]),
        "feature_timestamp": feat_ts,
        "avg_activity": float(row["avg_activity"]),
        "activity_growth": float(row["activity_growth"]),
        "active_hours": int(row["active_hours"]),
        "peak_ratio": float(row["peak_ratio"]),
        "variability": float(row["variability"]),
        "internet_share": float(row["internet_share"]),
        "data_quality_status": str(row["data_quality_status"]),
        "freshness_hours": freshness_hrs,
        "is_fresh": is_fresh
    }

# 150. Create POST /network/predict-risk with a Pydantic request model.
# 151. Return a stub risk_score, risk_level, model_version and explanation_note stating that the implementation is currently a stub.
# 153. After ML5, replace the stub with the trained model.
# 154. Keep the endpoint contract unchanged when that happens.
def predict_grid_risk(db: Session, request_data: Any) -> Optional[dict]:
    grid_id = request_data.grid_id
    if grid_id < 1 or grid_id > 10000:
        return None

    # Check grid existence in dim_grid
    grid_exists = db.execute(text("SELECT 1 FROM dim_grid WHERE grid_id = :grid_id LIMIT 1"), {"grid_id": grid_id}).scalar()
    if not grid_exists:
        return None

    # Determine activity level from stored features or fact table to generate a realistic stub score
    feat_row = db.execute(text("SELECT avg_activity FROM grid_features WHERE grid_id = :grid_id LIMIT 1"), {"grid_id": grid_id}).mappings().first()
    avg_act = float(feat_row["avg_activity"]) if feat_row else 0.0

    # If avg_activity was explicitly overridden in the request payload
    if request_data.avg_activity is not None:
        avg_act = float(request_data.avg_activity)

    # Heuristic stub scoring
    if avg_act >= 2000:
        risk_score = 0.85
        risk_level = "CRITICAL"
    elif avg_act >= 1000:
        risk_score = 0.65
        risk_level = "HIGH"
    elif avg_act >= 400:
        risk_score = 0.45
        risk_level = "MEDIUM"
    else:
        risk_score = 0.15
        risk_level = "LOW"

    prediction_time = datetime.now(timezone.utc).replace(tzinfo=None)

    return {
        "grid_id": grid_id,
        "risk_score": float(risk_score),
        "risk_level": risk_level,
        "model_version": "stub-v0.1.0",
        "prediction_timestamp": prediction_time,
        "explanation_note": (
            "STUB IMPLEMENTATION: This is a placeholder prediction model contract (stub-v0.1.0). "
            "ML5 will replace this stub with the trained production model while preserving this exact contract."
        ),
        "is_stub": True
    }




