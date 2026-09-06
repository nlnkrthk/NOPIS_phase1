from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException

# 133. Query the warehouse and analytics layer rather than raw CSV.
def get_network_summary(
    db: Session,
    from_dt: Optional[datetime] = None,
    to_dt: Optional[datetime] = None,
    as_of: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    # 131. Accept optional range or as_of parameters and resolve missing
    # bounds from the analytics layer. Never hardcode a date.
    
    # Determine effective datetime range
    if from_dt is None or to_dt is None:
        # time_key is generated as YYYYMMDDHH, so its indexed bounds identify
        # the first and last timestamps without scanning the joined fact table.
        range_query = text("""
            SELECT MIN(t.timestamp), MAX(t.timestamp)
            FROM dim_time t
            JOIN (
                SELECT MIN(time_key) AS first_time_key,
                       MAX(time_key) AS last_time_key
                FROM fact_network_activity
            ) bounds
              ON t.time_key IN (bounds.first_time_key, bounds.last_time_key)
        """)
        try:
            result = db.execute(range_query).first()
            if result is None or result[0] is None:
                return None
            
            if as_of is not None:
                if from_dt is not None or to_dt is not None:
                    return None
                effective_from = result[0]
                effective_to = as_of
            else:
                effective_from = from_dt if from_dt is not None else result[0]
                effective_to = to_dt if to_dt is not None else result[1]
        except SQLAlchemyError:
            raise
        except Exception:
            # If query fails, return None rather than hanging
            return None
    else:
        if as_of is not None:
            return None
        effective_from = from_dt
        effective_to = to_dt
    
    # Validate range
    if effective_from > effective_to:
        return None

    # 130. Return total_activity, active_grids, peak_hour and top_grid.
    try:
        params = {
            "from_dt": effective_from,
            "to_dt": effective_to,
            "from_key": effective_from.strftime("%Y%m%d%H"),
            "to_key": effective_to.strftime("%Y%m%d%H")
        }
        range_filter = """
            FROM fact_network_activity f
            JOIN dim_time t ON f.time_key = t.time_key
            WHERE f.time_key BETWEEN :from_key AND :to_key
              AND t.timestamp >= :from_dt AND t.timestamp <= :to_dt
        """

        total_activity = db.execute(text(
            "SELECT COALESCE(SUM(f.total_activity), 0.0) " + range_filter
        ), params).scalar()
        active_grids = db.execute(text(
            "SELECT COUNT(DISTINCT f.grid_id) " + range_filter
        ), params).scalar()

        if not active_grids:
            return None

        peak_hour = db.execute(text(
            """
            SELECT t.hour
            """ + range_filter + """
            GROUP BY t.hour
            ORDER BY SUM(f.total_activity) DESC, t.hour ASC
            LIMIT 1
            """
        ), params).scalar()
        top_grid = db.execute(text(
            """
            SELECT f.grid_id
            """ + range_filter + """
            GROUP BY f.grid_id
            ORDER BY SUM(f.total_activity) DESC, f.grid_id ASC
            LIMIT 1
            """
        ), params).scalar()

        return {
            "total_activity": float(total_activity or 0.0),
            "active_grids": int(active_grids),
            "peak_hour": int(peak_hour or 0),
            "top_grid": int(top_grid or 0),
            "from_dt": effective_from,
            "to_dt": effective_to
        }
    except SQLAlchemyError:
        raise
    except Exception:
        # Return None on any database error rather than hanging
        return None

# 136. Add optional date, hour and as_of query parameters. Default the window to the trailing 24 hourly intervals ending at AS_OF.
# 138. Return 404 for an unknown grid — and treat any grid_id outside 1–10000 as unknown.
def get_grid_activity(
    db: Session, 
    grid_id: int, 
    filter_date: Optional[Any] = None, 
    filter_hour: Optional[int] = None, 
    as_of: Optional[datetime] = None,
    from_dt: Optional[datetime] = None,
    to_dt: Optional[datetime] = None,
) -> Optional[list]:
    # Validate grid boundary 1-10000
    if grid_id < 1 or grid_id > 10000:
        return None

    # Verify grid exists in dim_grid
    grid_exists_query = text("SELECT 1 FROM dim_grid WHERE grid_id = :grid_id LIMIT 1")
    if not db.execute(grid_exists_query, {"grid_id": grid_id}).scalar():
        return None

    if as_of is not None and (from_dt is not None or to_dt is not None):
        return None

    if (from_dt is None) != (to_dt is None):
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

    # Build query dynamically based on date/hour/range filters.
    params = {"grid_id": grid_id, "as_of": effective_as_of}
    where_clauses = ["f.grid_id = :grid_id"]

    if from_dt is not None and to_dt is not None:
        from_dt = from_dt.replace(minute=0, second=0, microsecond=0)
        to_dt = to_dt.replace(minute=0, second=0, microsecond=0)
        if from_dt > to_dt:
            return None
        params.update({"from_dt": from_dt, "to_dt": to_dt})
        where_clauses.extend([
            "t.timestamp >= :from_dt",
            "t.timestamp <= :to_dt",
        ])

    if filter_date is not None:
        where_clauses.append("t.date = :filter_date")
        params["filter_date"] = filter_date

    if filter_hour is not None:
        where_clauses.append("t.hour = :filter_hour")
        params["filter_hour"] = filter_hour

    # As-of mode is cumulative from the first available timestamp.
    if as_of is not None:
        where_clauses.append("t.timestamp <= :as_of")

    # Default window: trailing 24 hourly intervals ending at as_of
    is_default_window = (
        filter_date is None
        and filter_hour is None
        and as_of is None
        and from_dt is None
    )

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
#
# Severity is decided purely from total_activity for hotspots:
#   total_activity >= 2000              -> CRITICAL
#   1000 <= total_activity < 2000       -> HIGH
#   500  <= total_activity < 1000       -> MEDIUM
#   total_activity < 500                -> LOW
#
# `limit` is applied to the severity-filtered stream, not as a SQL LIMIT
# before it — grids are heavily skewed toward CRITICAL/HIGH, so cutting off
# at the raw top-N-by-activity row would almost never reach a MEDIUM or LOW
# row. Fetching every grid for the timestamp and filtering by severity in
# Python is what lets a caller ask for "top N MEDIUM" or "top N LOW" and get
# real rows back instead of an empty list.
def get_hotspots(
    db: Session,
    limit: int = 10,
    as_of: Optional[datetime] = None,
    severity: Optional[str] = None
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
    """)
    rows = db.execute(query_sql, {"as_of": effective_as_of}).mappings().all()

    results = []
    for r in rows:
        act = float(r["total_activity"] or 0.0)
        if act >= 2000:
            grid_severity = "CRITICAL"
            reason = "Extreme high network load area requiring priority NOC monitoring"
        elif act >= 1000:
            grid_severity = "HIGH"
            reason = "High network traffic volume exceeding operational threshold"
        elif act >= 500:
            grid_severity = "MEDIUM"
            reason = "Elevated network usage hotspot"
        else:
            grid_severity = "LOW"
            reason = "Active operational hotspot"

        if severity is not None and grid_severity.upper() != severity.strip().upper():
            continue

        results.append({
            "grid_id": int(r["grid_id"]),
            "timestamp": r["timestamp"],
            "total_activity": act,
            "sms_activity": float(r["sms_activity"] or 0.0),
            "call_activity": float(r["call_activity"] or 0.0),
            "internet_activity": float(r["internet_activity"] or 0.0),
            "severity": grid_severity,
            "reason": reason,
            "risk_score": None,
            "risk_level": None,
            "model_version": None,
        })

        if len(results) >= limit:
            break

    return results

# 142. Initially serve the rule-based NP3 alerts.
# 144. Include grid_id, hourly timestamp, the relevant activity measures, status or severity, and a human-readable reason.
#
# Only grids with total_activity >= 300 are considered alert-worthy at all.
# Among those, severity is decided in this order (first match wins):
#   total_activity >= 2000                                   -> CRITICAL (HIGH_ACTIVITY)
#   1000 <= total_activity < 2000                             -> HIGH     (HIGH_ACTIVITY)
#   internet_activity >= 500 AND internet_share > 0.85         -> MEDIUM   (INTERNET_SURGE)
#   500 <= total_activity < 1000 (and not an internet surge)   -> LOW      (ACTIVITY_SPIKE)
#   300 <= total_activity < 500                                -> INFO     (ELEVATED_ACTIVITY)
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


def get_rising_grids(
    db: Session,
    limit: int = 10,
    as_of: Optional[datetime] = None,
    direction: Optional[str] = "HIGH"
) -> list:
    if as_of is None:
        max_ts_query = text("""
            SELECT MAX(feature_timestamp)
            FROM network_anomaly_scores
        """)
        effective_as_of = db.execute(max_ts_query).scalar()
        if effective_as_of is None:
            return []
    else:
        # Round down to nearest hour (data is hourly granularity)
        effective_as_of = as_of.replace(minute=0, second=0, microsecond=0)

    params = {"as_of": effective_as_of, "limit": limit}
    
    where_clauses = ["feature_timestamp <= :as_of"]
    
    # Exclude 'LOW' by default, or filter strictly if specified
    if direction:
        where_clauses.append("direction = :direction")
        params["direction"] = direction.strip().upper()
    else:
        where_clauses.append("direction != 'LOW'")

    where_sql = " AND ".join(where_clauses)

    query_sql = text(f"""
        SELECT 
            grid_id,
            feature_timestamp,
            current_value AS current_activity,
            baseline_value AS baseline_activity,
            deviation AS absolute_delta,
            anomaly_score AS pct_increase,
            direction
        FROM network_anomaly_scores
        WHERE {where_sql}
        ORDER BY anomaly_score DESC
        LIMIT :limit
    """)

    rows = db.execute(query_sql, params).mappings().all()

    results = []
    for r in rows:
        curr_val = r.get("current_activity") if "current_activity" in r else r.get("current_value", 0.0)
        base_val = r.get("baseline_activity") if "baseline_activity" in r else r.get("baseline_value", 0.0)
        abs_delta = r.get("absolute_delta") if "absolute_delta" in r else r.get("deviation", 0.0)
        pct_inc = r.get("pct_increase") if "pct_increase" in r else r.get("anomaly_score", 0.0)
        results.append({
            "grid_id": int(r["grid_id"]),
            "feature_timestamp": r["feature_timestamp"],
            "current_activity": float(curr_val or 0.0),
            "baseline_activity": float(base_val or 0.0),
            "absolute_delta": float(abs_delta or 0.0),
            "pct_increase": float(pct_inc or 0.0),
            "direction": str(r["direction"]),
        })

    return results

# 146. Return the exact ML2 feature set: avg_activity, activity_growth, active_hours, peak_ratio, variability, internet_share, plus feature_timestamp.
# 148. Return data-quality status and feature freshness alongside the values.
# The API reads stored features; no feature engineering arithmetic is performed here.
def get_grid_features(db: Session, grid_id: int, as_of: Optional[datetime] = None) -> Optional[dict]:
    if as_of is not None:
        effective_as_of = as_of.replace(minute=0, second=0, microsecond=0)
        activity_rows = db.execute(text("""
            SELECT t.timestamp, f.total_activity, f.internet_activity
            FROM fact_network_activity f
            JOIN dim_time t ON f.time_key = t.time_key
            WHERE f.grid_id = :grid_id AND t.timestamp <= :as_of
            ORDER BY t.timestamp DESC
            LIMIT 24
        """), {"grid_id": grid_id, "as_of": effective_as_of}).mappings().all()
        if not activity_rows:
            return None

        activities = [float(row["total_activity"] or 0.0) for row in reversed(activity_rows)]
        internet_activities = [float(row["internet_activity"] or 0.0) for row in reversed(activity_rows)]
        count = len(activities)
        average = sum(activities) / count
        variance = sum((value - average) ** 2 for value in activities) / count
        midpoint = count // 2
        first_half = sum(activities[:midpoint]) / midpoint if midpoint else average
        second_half = sum(activities[midpoint:]) / (count - midpoint) if count - midpoint else average
        total_activity = sum(activities)
        feature_timestamp = activity_rows[0]["timestamp"]

        return {
            "grid_id": grid_id,
            "feature_timestamp": feature_timestamp,
            "avg_activity": average,
            "activity_growth": (second_half - first_half) / (first_half + 1e-5),
            "active_hours": sum(value > 0 for value in activities),
            "peak_ratio": max(activities) / (average + 1e-5),
            "variability": (variance ** 0.5) / (average + 1e-5),
            "internet_share": sum(internet_activities) / (total_activity + 1e-5) if total_activity > 0 else 0.0,
            "data_quality_status": "VALID" if count >= 20 else "PARTIAL",
            "freshness_hours": 0.0,
            "is_fresh": count >= 20,
        }

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

# C1 — Task 229. Build the curated evidence object for the Claude Network
# Insight Generator from the grid_features + network_anomaly_scores JOIN.
# Only matched rows are used — an unmatched grid_id returns None rather than
# a fabricated evidence object. No existing table or pipeline is modified.
EVIDENCE_QUERY = text("""
    SELECT
        gf.grid_id            AS grid_id,
        gf.feature_timestamp  AS feature_timestamp,
        nas.current_value     AS current_activity,
        nas.baseline_value    AS baseline_activity,
        gf.activity_growth    AS activity_growth,
        gf.peak_ratio         AS peak_ratio,
        gf.variability        AS variability,
        gf.internet_share     AS internet_share,
        nas.anomaly_score     AS anomaly_score,
        nas.direction         AS direction,
        nas.anomaly_flag      AS anomaly_flag,
        nas.reason            AS reason
    FROM grid_features gf
    JOIN network_anomaly_scores nas
        ON gf.grid_id = nas.grid_id
        AND gf.feature_timestamp = nas.feature_timestamp
    WHERE gf.grid_id = :grid_id
    LIMIT 1
""")


def get_evidence_object(db: Session, grid_id: int) -> Optional[dict]:
    row = db.execute(EVIDENCE_QUERY, {"grid_id": grid_id}).mappings().first()
    if row is None:
        return None

    # rule_alerts is derived only from anomaly_flag/reason — never invented.
    rule_alerts = []
    if row["anomaly_flag"]:
        rule_alerts.append({
            "direction": row["direction"],
            "reason": row["reason"],
        })

    return {
        "grid_id": int(row["grid_id"]),
        "timestamp": row["feature_timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
        "current_activity": float(row["current_activity"]),
        "baseline_activity": float(row["baseline_activity"]),
        "activity_growth": float(row["activity_growth"]),
        "peak_ratio": float(row["peak_ratio"]),
        "variability": float(row["variability"]),
        "internet_share": float(row["internet_share"]),
        "anomaly_score": float(row["anomaly_score"]),
        "direction": row["direction"],
        "rule_alerts": rule_alerts,
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

    # Resolve features (request overrides take precedence over timestamped features)
    req_features = {
        "avg_activity": request_data.avg_activity,
        "activity_growth": request_data.activity_growth,
        "active_hours": request_data.active_hours,
        "peak_ratio": request_data.peak_ratio,
        "variability": request_data.variability,
        "internet_share": request_data.internet_share
    }

    # If any feature is missing, fetch from grid_features
    if any(v is None for v in req_features.values()):
        if request_data.as_of is not None:
            feat_row = get_grid_features(db, grid_id, request_data.as_of)
        else:
            feat_row = db.execute(
                text("""SELECT avg_activity, activity_growth, active_hours, 
                               peak_ratio, variability, internet_share 
                        FROM grid_features WHERE grid_id = :grid_id LIMIT 1"""), 
                {"grid_id": grid_id}
            ).mappings().first()
        
        if feat_row:
            for k in req_features:
                if req_features[k] is None:
                    req_features[k] = float(feat_row[k])
    
    # Final check for missing features
    missing = [k for k, v in req_features.items() if v is None]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Missing required ML features for inference: {', '.join(missing)}"
        )

    # Build canonical feature vector
    try:
        from Phase_4 import ml5_model_service
    except ModuleNotFoundError:
        import ml5_model_service

    feature_vector = [
        req_features["avg_activity"],
        req_features["activity_growth"],
        req_features["active_hours"],
        req_features["peak_ratio"],
        req_features["variability"],
        req_features["internet_share"]
    ]

    # Model inference
    model_version = request_data.model_version or ml5_model_service.MODEL_VERSION
    try:
        risk_score = ml5_model_service.predict(feature_vector, model_version)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    
    if risk_score >= 0.75:
        risk_level = "CRITICAL"
    elif risk_score >= 0.50:
        risk_level = "HIGH"
    elif risk_score >= 0.25:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    # Fetch Anomaly Context (ML4)
    anomaly_row = db.execute(
        text("""SELECT direction, anomaly_score, reason 
                FROM network_anomaly_scores 
                WHERE grid_id = :grid_id 
                ORDER BY feature_timestamp DESC LIMIT 1"""),
        {"grid_id": grid_id}
    ).mappings().first()

    # Get top feature contribution
    top_features = ml5_model_service.get_feature_contributions(model_version)
    top_feature_name, top_feature_val = top_features[0]

    explanation = (
        f"Real ML prediction using {model_version}. "
        f"Most influential feature: {top_feature_name} (weight: {top_feature_val:.3f})."
    )
    if anomaly_row:
        explanation += (
            f" Anomaly context: {anomaly_row['direction']} "
            f"(score: {anomaly_row['anomaly_score']:.1f}%). {anomaly_row['reason']}"
        )

    prediction_time = datetime.now(timezone.utc).replace(tzinfo=None)

    return {
        "grid_id": grid_id,
        "risk_score": float(risk_score),
        "risk_level": risk_level,
        "model_version": model_version,
        "prediction_timestamp": prediction_time,
        "explanation_note": explanation,
        "is_stub": False
    }




