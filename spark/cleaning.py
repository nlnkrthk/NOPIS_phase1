"""
Cleaning module — standardizes, validates, and curates raw telecom data.

Derived from SP2 (sp2_cleaning.py / NetworkDataCleaner).
"""

import logging

from pyspark.sql.functions import (
    col,
    coalesce,
    lit,
    when,
    to_date,
    hour,
    dayofweek,
)

logger = logging.getLogger(__name__)

# Canonical activity column names (after renaming)
ACTIVITY_COLUMNS = [
    "sms_in",
    "sms_out",
    "call_in",
    "call_out",
    "internet_activity",
]

# Column rename mapping: raw name → canonical name
_RENAME_MAP = {
    "datetime":    "timestamp",
    "CellID":      "grid_id",
    "countrycode": "country_code",
    "smsin":       "sms_in",
    "smsout":      "sms_out",
    "callin":      "call_in",
    "callout":     "call_out",
    "internet":    "internet_activity",
}


def clean(spark, raw_df):
    """
    Clean and standardize a raw telecom DataFrame.

    Steps:
      1. Rename columns to canonical names.
      2. Cast activity columns to double.
      3. Quarantine rows with null grid_id/timestamp or negative
         activity values.
      4. Apply null-to-zero on activity columns (curated-layer rule).
      5. Derive total_sms, total_calls, total_activity.
      6. Derive date, hour, day_of_week.

    Parameters
    ----------
    spark : pyspark.sql.SparkSession
    raw_df : pyspark.sql.DataFrame
        DataFrame returned by ``ingestion.read_raw()``.

    Returns
    -------
    curated_df : pyspark.sql.DataFrame
        Cleaned DataFrame ready for aggregation.
    rejected_count : int
        Number of rows quarantined.
    nulls_handled : dict
        Mapping of column name → count of nulls that were set to zero.
    """
    input_rows = raw_df.count()
    logger.info("Cleaning — input rows: %d", input_rows)

    # ── 1. Rename columns ──────────────────────────────────────────
    df = raw_df
    for old_name, new_name in _RENAME_MAP.items():
        df = df.withColumnRenamed(old_name, new_name)

    # Drop the traceability column (will be re-added if needed downstream)
    if "input_file_name" in df.columns:
        df = df.drop("input_file_name")

    # ── 2. Cast activity columns ───────────────────────────────────
    for c in ACTIVITY_COLUMNS:
        df = df.withColumn(c, col(c).cast("double"))

    df = df.withColumn("timestamp", col("timestamp").cast("timestamp"))

    # ── 3. Profile nulls BEFORE cleaning ───────────────────────────
    nulls_handled = {}
    for c in ACTIVITY_COLUMNS:
        null_count = df.filter(col(c).isNull()).count()
        nulls_handled[c] = null_count
        logger.info("Nulls in %-20s: %d", c, null_count)

    # ── 4. Quarantine bad rows ─────────────────────────────────────
    reject_condition = (
        col("grid_id").isNull()
        | col("timestamp").isNull()
        | (coalesce(col("sms_in"), lit(0.0)) < 0)
        | (coalesce(col("sms_out"), lit(0.0)) < 0)
        | (coalesce(col("call_in"), lit(0.0)) < 0)
        | (coalesce(col("call_out"), lit(0.0)) < 0)
        | (coalesce(col("internet_activity"), lit(0.0)) < 0)
    )

    rejected_count = df.filter(reject_condition).count()
    logger.info("Rejected rows (null key / negative activity): %d", rejected_count)

    curated_df = df.filter(~reject_condition)

    # ── 5. Null-to-zero rule ───────────────────────────────────────
    for c in ACTIVITY_COLUMNS:
        curated_df = curated_df.withColumn(
            c,
            when(col(c).isNull(), 0.0).otherwise(col(c)),
        )

    # ── 6. Derived activity features ──────────────────────────────
    curated_df = (
        curated_df
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

    # ── 7. Derived time features ──────────────────────────────────
    curated_df = (
        curated_df
        .withColumn("date", to_date(col("timestamp")))
        .withColumn("hour", hour(col("timestamp")))
        .withColumn("day_of_week", dayofweek(col("timestamp")))
    )

    output_rows = curated_df.count()
    logger.info("Cleaning — output rows: %d", output_rows)

    return curated_df, rejected_count, nulls_handled
