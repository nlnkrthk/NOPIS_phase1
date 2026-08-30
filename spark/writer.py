"""
Writer module — persists pipeline outputs to Parquet and CSV.

Writes two output zones:

    Processed Zone  (data/processed/)
        enriched_hourly_grid/   ← Full enriched Parquet, partitioned by date

    Analytics Zone  (data/analytics/)
        hourly_grid_summary/    ← Aggregated KPI Parquet (no geometry)
        summary_csv/            ← Single CSV for quick inspection
"""

import logging

logger = logging.getLogger(__name__)

# Analytics columns — aggregated KPIs without the geometry blob
_ANALYTICS_COLUMNS = [
    "timestamp",
    "grid_id",
    "date",
    "hour",
    "sms_in",
    "sms_out",
    "call_in",
    "call_out",
    "internet_activity",
    "total_sms",
    "total_calls",
    "total_activity",
    "internet_share",
]


def write_outputs(enriched_df, processed_path, analytics_path):
    """
    Write pipeline outputs to the processed and analytics data zones.

    Processed Zone
    --------------
    ``<processed_path>/enriched_hourly_grid/``
        Full enriched Parquet dataset including geometry, partitioned by date.

    Analytics Zone
    --------------
    ``<analytics_path>/hourly_grid_summary/``
        Aggregated KPI Parquet at the (timestamp, grid_id) grain,
        without the geometry column (matches the sp5-6 analytics schema).

    ``<analytics_path>/summary_csv/``
        Single-file CSV for quick inspection.

    Parameters
    ----------
    enriched_df : pyspark.sql.DataFrame
        Enriched DataFrame from ``enrichment.enrich()``.
    processed_path : str
        Base directory for the processed data zone (``data/processed``).
    analytics_path : str
        Base directory for the analytics data zone (``data/analytics``).

    Returns
    -------
    int
        Total number of output rows written.
    """
    output_rows = enriched_df.count()
    logger.info("Writer — output rows: %d", output_rows)

    # ── 1. Processed zone: full enriched dataset ──────────────────
    parquet_path = f"{processed_path}/enriched_hourly_grid"
    logger.info("Writing processed Parquet to: %s", parquet_path)

    (
        enriched_df
        .write
        .mode("overwrite")
        .partitionBy("date")
        .parquet(parquet_path)
    )

    logger.info("Processed Parquet write complete.")

    # ── 2. Analytics zone: KPI summary (no geometry) ─────────────
    # Keep only columns that exist in the DataFrame
    available = set(enriched_df.columns)
    analytics_cols = [c for c in _ANALYTICS_COLUMNS if c in available]

    hourly_grid_summary = enriched_df.select(*analytics_cols)

    analytics_parquet_path = f"{analytics_path}/hourly_grid_summary"
    logger.info("Writing analytics Parquet to: %s", analytics_parquet_path)

    hourly_grid_summary.write.mode("overwrite").parquet(analytics_parquet_path)

    logger.info("Analytics Parquet write complete.")

    # ── 3. Analytics zone: single-file CSV summary ────────────────
    csv_path = f"{analytics_path}/summary_csv"
    logger.info("Writing CSV summary to: %s", csv_path)

    (
        hourly_grid_summary
        .coalesce(1)
        .write
        .mode("overwrite")
        .option("header", True)
        .csv(csv_path)
    )

    logger.info("CSV summary write complete.")

    return output_rows
