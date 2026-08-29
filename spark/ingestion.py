"""
Ingestion module — reads raw telecom CSV files into a Spark DataFrame.

Derived from SP1 (sp1_ingestion.py).
"""

import logging
from pathlib import Path

from pyspark.sql.functions import input_file_name
from pyspark.sql.types import (
    StructType,
    StructField,
    TimestampType,
    IntegerType,
    DoubleType,
)

logger = logging.getLogger(__name__)

# ── Schema matching the raw CSV layout ──────────────────────────────
RAW_SCHEMA = StructType([
    StructField("datetime",    TimestampType(), True),
    StructField("CellID",     IntegerType(),   True),
    StructField("countrycode", IntegerType(),   True),
    StructField("smsin",       DoubleType(),    True),
    StructField("smsout",      DoubleType(),    True),
    StructField("callin",      DoubleType(),    True),
    StructField("callout",     DoubleType(),    True),
    StructField("internet",    DoubleType(),    True),
])

CSV_GLOB_PATTERN = "sms-call-internet-mi-*.csv"


def read_raw(spark, input_path):
    """
    Read all raw telecom CSV files from *input_path*.

    Parameters
    ----------
    spark : pyspark.sql.SparkSession
    input_path : str
        Directory containing ``sms-call-internet-mi-*.csv`` files.

    Returns
    -------
    pyspark.sql.DataFrame
        Raw DataFrame with an added ``input_file_name`` column.

    Raises
    ------
    FileNotFoundError
        If zero CSV files match the expected pattern.
    """
    data_folder = Path(input_path)

    files = sorted(
        str(f) for f in data_folder.glob(CSV_GLOB_PATTERN)
    )

    # ── Fail loudly when there is nothing to process (task #72) ─────
    if not files:
        msg = (
            f"No files matching '{CSV_GLOB_PATTERN}' found "
            f"in {data_folder}"
        )
        logger.error(msg)
        raise FileNotFoundError(msg)

    logger.info("Files found: %d", len(files))
    for f in files:
        logger.info("  %s", f)

    raw_df = (
        spark.read
        .option("header", True)
        .schema(RAW_SCHEMA)
        .csv(files)
    )

    # Traceability column (SP1 Q5)
    raw_df = raw_df.withColumn(
        "input_file_name",
        input_file_name(),
    )

    row_count = raw_df.count()
    logger.info("Raw input rows: %d", row_count)

    return raw_df
