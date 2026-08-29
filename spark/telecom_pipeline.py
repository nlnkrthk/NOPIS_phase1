"""
telecom_pipeline.py — Unified ETL pipeline for NOPIS telecom data.

Combines the ingestion (SP1), cleaning (SP2), aggregation (SP3),
and geospatial enrichment (SP4) stages into a single production-style
job with configurable paths, comprehensive logging, and clean failure
handling.

Usage
-----
    python -m spark.telecom_pipeline \
        --input  D:\\NOPIS\\data \
        --output D:\\NOPIS\\spark\\output \
        --reference D:\\NOPIS\\data\\milano-grid.geojson

All paths can also be supplied via a JSON config file::

    python -m spark.telecom_pipeline --config pipeline_config.json
"""

import argparse
import json
import logging
import sys
import time
import traceback
from datetime import datetime, timezone

# ── Pipeline stage imports ────────────────────────────────────────
from spark.spark_session import create_spark_session
from spark.ingestion import read_raw
from spark.cleaning import clean
from spark.aggregation import aggregate
from spark.enrichment import enrich
from spark.writer import write_outputs

# ── Default paths (training run) ────────────────────────────────
_DEFAULTS = {
    "input":     r"D:\NOPIS\data",
    "output":    r"D:\NOPIS\spark\output",
    "reference": r"D:\NOPIS\data\milano-grid.geojson",
}


# ═════════════════════════════════════════════════════════════════
# Logging setup
# ═════════════════════════════════════════════════════════════════

def _setup_logging():
    """Configure root logger with timestamp, level, and module name."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


# ═════════════════════════════════════════════════════════════════
# Argument parsing
# ═════════════════════════════════════════════════════════════════

def _parse_args():
    parser = argparse.ArgumentParser(
        description="NOPIS Telecom ETL Pipeline (SP7)",
    )

    parser.add_argument(
        "--input",
        default=_DEFAULTS["input"],
        help="Directory containing sms-call-internet-mi-*.csv files.",
    )

    parser.add_argument(
        "--output",
        default=_DEFAULTS["output"],
        help="Base output directory for Parquet and CSV.",
    )

    parser.add_argument(
        "--reference",
        default=_DEFAULTS["reference"],
        help="Path to milano-grid.geojson.",
    )

    parser.add_argument(
        "--config",
        default=None,
        help="Path to a JSON config file (overrides other args).",
    )

    return parser.parse_args()


def _resolve_paths(args):
    """
    Resolve final paths from CLI args, optionally overridden by a
    JSON config file.
    """
    paths = {
        "input":     args.input,
        "output":    args.output,
        "reference": args.reference,
    }

    if args.config:
        with open(args.config, "r", encoding="utf-8") as f:
            config = json.load(f)

        # Config keys override CLI defaults
        for key in ("input", "output", "reference"):
            if key in config:
                paths[key] = config[key]

    return paths


# ═════════════════════════════════════════════════════════════════
# Pipeline orchestration
# ═════════════════════════════════════════════════════════════════

def main():
    """Run the full telecom ETL pipeline."""
    _setup_logging()
    logger = logging.getLogger("telecom_pipeline")

    args = _parse_args()
    paths = _resolve_paths(args)

    start_time = time.time()
    start_dt = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    logger.info("=" * 70)
    logger.info("NOPIS TELECOM PIPELINE — START")
    logger.info("=" * 70)
    logger.info("Start time : %s", start_dt)
    logger.info("Input path : %s", paths["input"])
    logger.info("Output path: %s", paths["output"])
    logger.info("Reference  : %s", paths["reference"])
    logger.info("=" * 70)

    spark = None
    status = "FAILED"

    try:
        # ── 1. Create Spark session ──────────────────────────────
        logger.info("Stage 1/5 — Creating Spark session")
        spark = create_spark_session(
            app_name="NOPIS_Telecom_Pipeline_SP7",
        )

        # ── 2. Ingest raw data ───────────────────────────────────
        logger.info("Stage 2/5 — Ingestion (read_raw)")
        raw_df = read_raw(spark, paths["input"])
        input_rows = raw_df.count()

        # ── 3. Clean and standardize ─────────────────────────────
        logger.info("Stage 3/5 — Cleaning (clean)")
        curated_df, rejected_count, nulls_handled = clean(
            spark, raw_df
        )

        # ── 4. Aggregate ────────────────────────────────────────
        logger.info("Stage 4/5 — Aggregation (aggregate)")
        hourly_grid_summary = aggregate(spark, curated_df)

        # ── 5a. Enrich with geospatial data ─────────────────────
        logger.info("Stage 5a/5 — Enrichment (enrich)")
        enriched_df = enrich(
            spark, hourly_grid_summary, paths["reference"]
        )

        # ── 5b. Write outputs ───────────────────────────────────
        logger.info("Stage 5b/5 — Writing outputs")
        output_rows = write_outputs(enriched_df, paths["output"])

        status = "SUCCESS"

    except FileNotFoundError:
        logger.error("PIPELINE FAILED — No input files found!")
        logger.error(traceback.format_exc())
        sys.exit(1)

    except Exception:
        logger.error("PIPELINE FAILED — Unexpected error!")
        logger.error(traceback.format_exc())
        sys.exit(1)

    finally:
        end_time = time.time()
        end_dt = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        elapsed = end_time - start_time

        logger.info("=" * 70)
        logger.info("NOPIS TELECOM PIPELINE — SUMMARY")
        logger.info("=" * 70)
        logger.info("Final status   : %s", status)
        logger.info("Start time     : %s", start_dt)
        logger.info("End time       : %s", end_dt)
        logger.info("Elapsed        : %.1f seconds", elapsed)

        if status == "SUCCESS":
            logger.info("Input rows     : %d", input_rows)
            logger.info("Rejected rows  : %d", rejected_count)
            logger.info("Nulls handled  : %s", nulls_handled)
            logger.info("Output rows    : %d", output_rows)

        logger.info("=" * 70)

        if spark:
            spark.stop()
            logger.info("SparkSession stopped.")


# ═════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    main()
