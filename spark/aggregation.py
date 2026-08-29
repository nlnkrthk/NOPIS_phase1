"""
Aggregation module — collapses country-code dimension and computes KPIs.

Derived from SP3 (sp3_aggregation.py / NetworkDataAggregator).
"""

import logging

from pyspark.sql.functions import (
    col,
    hour,
    to_date,
    when,
    sum as spark_sum,
)

logger = logging.getLogger(__name__)


def aggregate(spark, curated_df):
    """
    Aggregate curated data to the (timestamp, grid_id) grain.

    Country-code dimension is collapsed by summing activity measures
    per grid per hour. Activity KPIs and internet share are derived.

    Parameters
    ----------
    spark : pyspark.sql.SparkSession
    curated_df : pyspark.sql.DataFrame
        Cleaned DataFrame from ``cleaning.clean()``.

    Returns
    -------
    pyspark.sql.DataFrame
        Hourly grid summary at the (timestamp, grid_id) grain.
    """
    input_rows = curated_df.count()
    logger.info("Aggregation — input rows: %d", input_rows)

    # ── 1. Group by (timestamp, grid_id) — collapse country codes ──
    hourly_grid_summary = (
        curated_df
        .groupBy("timestamp", "grid_id")
        .agg(
            spark_sum("sms_in").alias("sms_in"),
            spark_sum("sms_out").alias("sms_out"),
            spark_sum("call_in").alias("call_in"),
            spark_sum("call_out").alias("call_out"),
            spark_sum("internet_activity").alias("internet_activity"),
        )
    )

    # ── 2. Re-derive date and hour ─────────────────────────────────
    hourly_grid_summary = (
        hourly_grid_summary
        .withColumn("date", to_date(col("timestamp")))
        .withColumn("hour", hour(col("timestamp")))
    )

    # ── 3. Activity KPIs ──────────────────────────────────────────
    hourly_grid_summary = (
        hourly_grid_summary
        .withColumn(
            "total_sms",
            col("sms_in") + col("sms_out"),
        )
        .withColumn(
            "total_calls",
            col("call_in") + col("call_out"),
        )
        .withColumn(
            "total_activity",
            col("sms_in")
            + col("sms_out")
            + col("call_in")
            + col("call_out")
            + col("internet_activity"),
        )
    )

    # ── 4. Internet share ─────────────────────────────────────────
    hourly_grid_summary = hourly_grid_summary.withColumn(
        "internet_share",
        when(
            col("total_activity") > 0,
            col("internet_activity") / col("total_activity"),
        ).otherwise(0.0),
    )

    # ── 5. Validate grain — no duplicate (grid_id, timestamp) ────
    duplicate_count = (
        hourly_grid_summary
        .groupBy("grid_id", "timestamp")
        .count()
        .filter(col("count") > 1)
        .count()
    )

    if duplicate_count > 0:
        raise ValueError(
            f"Grain validation FAILED: {duplicate_count} duplicate "
            f"(grid_id, timestamp) combinations found."
        )

    logger.info("Grain validation PASSED — no duplicates.")

    output_rows = hourly_grid_summary.count()
    logger.info("Aggregation — output rows: %d", output_rows)

    assert output_rows < input_rows, (
        "Aggregation should reduce row count. "
        f"Input: {input_rows}, Output: {output_rows}"
    )

    logger.info(
        "Row reduction: %d -> %d (%.1f%% reduction)",
        input_rows,
        output_rows,
        (1 - output_rows / input_rows) * 100,
    )

    return hourly_grid_summary
