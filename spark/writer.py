"""
Writer module — persists pipeline outputs to Parquet and CSV.

Handles the Spark write step with overwrite mode and a coalesced
CSV summary for quick inspection.
"""

import logging

logger = logging.getLogger(__name__)


def write_outputs(df, output_path):
    """
    Write the enriched DataFrame to Parquet and a single-file CSV.

    Output layout::

        <output_path>/
            enriched_hourly_grid/   ← Parquet (partitioned)
            summary_csv/           ← Single CSV for quick inspection

    Parameters
    ----------
    df : pyspark.sql.DataFrame
        Enriched DataFrame to persist.
    output_path : str
        Base output directory.
    """
    output_rows = df.count()
    logger.info("Writer — output rows: %d", output_rows)

    # ── Parquet output ────────────────────────────────────────────
    parquet_path = f"{output_path}/enriched_hourly_grid"

    logger.info("Writing Parquet to: %s", parquet_path)

    df.write.mode("overwrite").parquet(parquet_path)

    logger.info("Parquet write complete.")

    # ── CSV summary (single file) ────────────────────────────────
    csv_path = f"{output_path}/summary_csv"

    logger.info("Writing CSV summary to: %s", csv_path)

    (
        df
        .coalesce(1)
        .write
        .mode("overwrite")
        .option("header", True)
        .csv(csv_path)
    )

    logger.info("CSV summary write complete.")

    return output_rows
