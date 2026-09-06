"""
Anomaly scoring module — statistical deviation from hour-of-day baseline.

Ports the ML4 scoring contract used by Phase_4 (`network_anomaly_scores`):

    baseline_value  = median total_activity per (grid_id, hour-of-day)
    deviation       = current_value - baseline_value
    anomaly_score   = (deviation / baseline_value) * 100
    direction       = HIGH  if anomaly_score >=  50
                      LOW   if anomaly_score <= -50
                      NORMAL otherwise
    anomaly_flag    = direction != NORMAL

Warehouse I/O (same contract as Phase_6/ml_4.ipynb):
    READ  fact_network_activity JOIN dim_time
    WRITE network_anomaly_scores  (full replace on each run)

High activity is elevated activity relative to the historical median for that
grid and hour-of-day. It is not a congestion, capacity, or utilization claim.

Grain is one row per (grid_id, timestamp) after country-code aggregation.

Usage::

    python -m spark.anomaly_scoring
"""

import logging
import os

import pandas as pd
from pyspark.sql import DataFrame
from pyspark.sql.functions import (
    abs as spark_abs,
    col,
    expr,
    format_string,
    hour,
    lit,
    when,
)
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)

# Use the same warehouse target as the ETL loader. Override this in Airflow
# with NOPIS_DATABASE_URL when the deployment uses different credentials.
DATABASE_URL = os.environ.get(
    "NOPIS_DATABASE_URL",
    "mysql+pymysql://root:root@localhost:3306/nopis",
)

_ACTIVITY_QUERY = """
SELECT
    f.grid_id,
    t.timestamp,
    f.total_activity,
    CASE WHEN s.grid_id IS NULL THEN 1 ELSE 0 END AS is_new
FROM fact_network_activity f
JOIN dim_time t ON f.time_key = t.time_key
LEFT JOIN network_anomaly_scores s
    ON s.grid_id = f.grid_id
   AND s.feature_timestamp = t.timestamp
ORDER BY f.grid_id, t.timestamp
"""

_CREATE_SCORES_TABLE = """
CREATE TABLE IF NOT EXISTS network_anomaly_scores (
    grid_id INT,
    feature_timestamp DATETIME,
    current_value DOUBLE,
    baseline_value DOUBLE,
    deviation DOUBLE,
    anomaly_score DOUBLE,
    direction VARCHAR(10),
    anomaly_flag BOOLEAN,
    reason TEXT,
    UNIQUE KEY uq_network_anomaly_grid_timestamp (grid_id, feature_timestamp)
)
"""

HIGH_THRESHOLD = 50.0
LOW_THRESHOLD = -50.0

_OUTPUT_COLUMNS = [
    "grid_id",
    "feature_timestamp",
    "current_value",
    "baseline_value",
    "deviation",
    "anomaly_score",
    "direction",
    "anomaly_flag",
    "reason",
]


def calculate_baseline(
    activity_df: DataFrame,
    group_columns=None,
    value_column="total_activity",
    statistic="median",
) -> DataFrame:
    """
    Compute a baseline using a configurable grouping key.

    Default grouping is (grid_id, hour) — the ML4 hour-of-day baseline.
    ``statistic`` is ``median`` (default) or ``mean``.
    """
    if group_columns is None:
        group_columns = ["grid_id", "hour"]

    if statistic == "median":
        agg_expr = expr(f"percentile({value_column}, 0.5)").alias("baseline_value")
    elif statistic == "mean":
        agg_expr = expr(f"avg({value_column})").alias("baseline_value")
    else:
        raise ValueError("statistic must be either 'median' or 'mean'")

    return activity_df.groupBy(*group_columns).agg(agg_expr)


def score_anomalies(
    activity_df: DataFrame,
    timestamp_col="timestamp",
    value_column="total_activity",
    high_threshold=HIGH_THRESHOLD,
    low_threshold=LOW_THRESHOLD,
    incremental=True,
) -> DataFrame:
    """
    Score each (grid_id, timestamp) row against its hour-of-day median baseline.

    Parameters
    ----------
    activity_df : pyspark.sql.DataFrame
        Canonical grain: one row per (grid_id, hourly timestamp).
        Must include ``grid_id`` and ``total_activity`` (or ``value_column``).
        ``timestamp`` is used unless already present as ``hour``.
    timestamp_col : str
        Timestamp column used to derive hour-of-day when ``hour`` is absent.
    value_column : str
        Activity measure to score (default ``total_activity``).
    high_threshold, low_threshold : float
        Percentage-deviation cutoffs for HIGH / LOW direction.

    Returns
    -------
    pyspark.sql.DataFrame
        Columns matching ``network_anomaly_scores``:
        grid_id, feature_timestamp, current_value, baseline_value,
        deviation, anomaly_score, direction, anomaly_flag, reason.
    """
    input_rows = activity_df.count()
    logger.info("Anomaly scoring — input rows: %d", input_rows)

    scored = activity_df
    if "hour" not in scored.columns:
        scored = scored.withColumn("hour", hour(col(timestamp_col)))

    baseline_df = calculate_baseline(
        scored,
        group_columns=["grid_id", "hour"],
        value_column=value_column,
        statistic="median",
    )

    if incremental and "is_new" in scored.columns:
        scored = scored.filter(col("is_new") == lit(1))

    scored = scored.join(baseline_df, on=["grid_id", "hour"], how="left")

    scored = (
        scored
        .withColumnRenamed(timestamp_col, "feature_timestamp")
        .withColumnRenamed(value_column, "current_value")
        .withColumn(
            "deviation",
            col("current_value") - col("baseline_value"),
        )
        .withColumn(
            "anomaly_score",
            when(
                col("baseline_value").isNull() | (col("baseline_value") == 0),
                lit(None).cast("double"),
            ).otherwise(
                (col("deviation") / col("baseline_value")) * 100.0
            ),
        )
    )

    scored = scored.withColumn(
        "direction",
        when(col("anomaly_score") >= lit(high_threshold), lit("HIGH"))
        .when(col("anomaly_score") <= lit(low_threshold), lit("LOW"))
        .otherwise(lit("NORMAL")),
    ).withColumn(
        "anomaly_flag",
        col("direction") != lit("NORMAL"),
    )

    abs_score = spark_abs(col("anomaly_score"))
    scored = scored.withColumn(
        "reason",
        when(
            col("direction") == "HIGH",
            format_string(
                "Activity is %.1f%% above the historical baseline (%.2f vs %.2f).",
                abs_score,
                col("current_value"),
                col("baseline_value"),
            ),
        )
        .when(
            col("direction") == "LOW",
            format_string(
                "Activity is %.1f%% below the historical baseline (%.2f vs %.2f).",
                abs_score,
                col("current_value"),
                col("baseline_value"),
            ),
        )
        .otherwise(
            format_string(
                "Activity is within the historical baseline (%.2f vs %.2f).",
                col("current_value"),
                col("baseline_value"),
            ),
        ),
    )

    result = scored.select(*_OUTPUT_COLUMNS)
    logger.info("Anomaly scoring — output rows: %d", result.count())
    return result


def _spark_tmp_dir():
    tmp_dir = os.environ.get(
        "NOPIS_SPARK_TMP",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "tmp", "spark_temp"),
    )
    os.makedirs(tmp_dir, exist_ok=True)
    return tmp_dir


def _get_engine():
    return create_engine(
        DATABASE_URL,
        connect_args={"connect_timeout": 10},
        pool_pre_ping=True,
    )


def _ensure_scores_table(engine):
    with engine.begin() as conn:
        conn.execute(text(_CREATE_SCORES_TABLE))
        try:
            conn.execute(text(
                "ALTER TABLE network_anomaly_scores "
                "ADD UNIQUE KEY uq_network_anomaly_grid_timestamp "
                "(grid_id, feature_timestamp)"
            ))
        except Exception:
            pass


def fetch_activity_from_warehouse(spark) -> DataFrame:
    """
    Load canonical-grain activity from MySQL into a Spark DataFrame.

    Reads ``fact_network_activity`` joined to ``dim_time`` so each row is
    one (grid_id, hourly timestamp) with ``total_activity``.
    """
    logger.info("Reading fact_network_activity JOIN dim_time from warehouse")
    engine = _get_engine()
    try:
        _ensure_scores_table(engine)
        activity_pdf = pd.read_sql_query(_ACTIVITY_QUERY, engine)
    finally:
        engine.dispose()

    if activity_pdf.empty:
        raise ValueError(
            "fact_network_activity JOIN dim_time returned no rows. "
            "Load the warehouse before scoring anomalies."
        )

    activity_pdf["timestamp"] = pd.to_datetime(activity_pdf["timestamp"])
    logger.info("Warehouse activity rows: %d", len(activity_pdf))

    # Parquet round-trip avoids Spark createDataFrame() from Python rows
    # (same Windows-safe pattern as spark/enrichment.py).
    tmp_path = os.path.join(_spark_tmp_dir(), "anomaly_activity.parquet")
    activity_pdf.to_parquet(tmp_path, index=False)
    return spark.read.parquet(tmp_path)


def write_anomaly_scores(scored_df: DataFrame) -> int:
    """
    Replace MySQL ``network_anomaly_scores`` with the scored Spark result.

    Creates the table if it does not exist, then truncates and inserts —
    the same full-refresh contract as Phase_6/ml_4.ipynb.
    """
    tmp_path = os.path.join(_spark_tmp_dir(), "anomaly_scores_out")
    (
        scored_df
        .select(*_OUTPUT_COLUMNS)
        .write
        .mode("overwrite")
        .parquet(tmp_path)
    )
    scores_pdf = pd.read_parquet(tmp_path)

    if scores_pdf.empty:
        logger.info("No unscored activity rows found; anomaly table is unchanged.")
        return 0

    scores_pdf["anomaly_flag"] = scores_pdf["anomaly_flag"].astype(bool)
    row_count = len(scores_pdf)
    logger.info("Writing %d rows to network_anomaly_scores", row_count)

    engine = _get_engine()
    try:
        _ensure_scores_table(engine)
        score_insert = text("""
            INSERT INTO network_anomaly_scores
                (grid_id, feature_timestamp, current_value, baseline_value,
                 deviation, anomaly_score, direction, anomaly_flag, reason)
            VALUES
                (:grid_id, :feature_timestamp, :current_value, :baseline_value,
                 :deviation, :anomaly_score, :direction, :anomaly_flag, :reason)
            ON DUPLICATE KEY UPDATE
                current_value = VALUES(current_value),
                baseline_value = VALUES(baseline_value),
                deviation = VALUES(deviation),
                anomaly_score = VALUES(anomaly_score),
                direction = VALUES(direction),
                anomaly_flag = VALUES(anomaly_flag),
                reason = VALUES(reason)
        """)
        with engine.begin() as conn:
            for start in range(0, len(scores_pdf), 5000):
                records = [
                    {str(key): value for key, value in record.items()}
                    for record in scores_pdf.iloc[start:start + 5000]
                    .to_dict("records")
                ]
                conn.execute(
                    score_insert,
                    records,
                )
    finally:
        engine.dispose()

    logger.info("network_anomaly_scores stored successfully (%d rows)", row_count)
    return row_count


def _create_spark_session():
    """Create the configured local Spark session in either launch mode."""
    if __package__:
        from .spark_session import create_spark_session
    else:
        from spark_session import create_spark_session

    return create_spark_session(app_name="NOPIS_Anomaly_Scoring")


def run_from_warehouse(spark=None) -> int:
    """
    Fetch warehouse activity, score it, and persist ``network_anomaly_scores``.
    """
    own_session = spark is None
    if own_session:
        spark = _create_spark_session()

    try:
        activity_df = fetch_activity_from_warehouse(spark)
        scored_df = score_anomalies(activity_df)
        return write_anomaly_scores(scored_df)
    finally:
        if own_session:
            spark.stop()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    run_from_warehouse()

