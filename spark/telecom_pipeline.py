"""
telecom_pipeline.py — Unified ETL pipeline for NOPIS telecom data.

Combines the landing ingestion (DE2), raw ingestion (SP1), cleaning (SP2),
aggregation (SP3), and geospatial enrichment (SP4) stages into a single
production-style job with configurable paths, comprehensive logging, and clean
failure handling.

Pipeline Stages
---------------
    1. Landing Ingestion: Validate files in landing/ and route to raw/ or rejected/
    2. Spark Session: Initialize Spark with local winutils/Hadoop config
    3. Ingestion: Read validated raw CSVs from data/raw/
    4. Cleaning: Standardize, quarantine bad rows, handle nulls
    5. Aggregation: Collapse country codes, compute KPIs at (timestamp, grid_id) grain
    6. Enrichment: Broadcast-join with milano-grid.geojson
    7. Persistence: Persist Parquet and CSV outputs

Usage
-----
    python -m spark.telecom_pipeline \
        --landing   D:\\NOPIS\\data\\landing \
        --raw       D:\\NOPIS\\data\\raw \
        --rejected  D:\\NOPIS\\data\\rejected \
        --logs      D:\\NOPIS\\logs \
        --processed D:\\NOPIS\\data\\processed \
        --analytics D:\\NOPIS\\data\\analytics \
        --reference D:\\NOPIS\\data\\milano-grid.geojson

All paths can also be supplied via a JSON config file::

    python -m spark.telecom_pipeline --config pipeline_config.json
"""

import argparse
import json
import logging
from pathlib import Path
import sys
import time
import traceback
from datetime import datetime, timezone

# ── Pipeline stage imports ────────────────────────────────────────
from spark.spark_session import create_spark_session
from spark.landing_ingestion import process_landing
from spark.ingestion import read_raw
from spark.cleaning import clean
from spark.aggregation import aggregate
from spark.enrichment import enrich
from spark.writer import write_outputs

# ── Default paths (training run) ────────────────────────────────
_DEFAULTS = {
    "landing":   r"D:\NOPIS\data\landing",
    "raw":       r"D:\NOPIS\data\raw",
    "rejected":  r"D:\NOPIS\data\rejected",
    "logs":      r"D:\NOPIS\logs",
    "processed": r"D:\NOPIS\data\processed",
    "analytics": r"D:\NOPIS\data\analytics",
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


def load_warehouse():
    """Load the successful Spark output into the SQL warehouse."""
    from warehouse.load_warehouse import load_dim_grid, load_activity_data

    load_dim_grid()
    load_activity_data()


# ═════════════════════════════════════════════════════════════════
# Argument parsing
# ═════════════════════════════════════════════════════════════════

def _parse_args():
    parser = argparse.ArgumentParser(
        description="NOPIS Telecom ETL Pipeline (SP7 / DE2)",
    )

    parser.add_argument(
        "--landing",
        default=_DEFAULTS["landing"],
        help="Directory containing landing zone CSV files (data/landing).",
    )

    parser.add_argument(
        "--raw",
        default=_DEFAULTS["raw"],
        help="Directory containing validated raw CSV files for Spark ingestion (data/raw).",
    )

    parser.add_argument(
        "--rejected",
        default=_DEFAULTS["rejected"],
        help="Directory for quarantined/rejected CSV files (data/rejected).",
    )

    parser.add_argument(
        "--logs",
        default=_DEFAULTS["logs"],
        help="Directory for ingestion audit logs (logs).",
    )

    parser.add_argument(
        "--input",
        default=None,
        help="Base data folder or raw input folder (legacy compatibility).",
    )

    parser.add_argument(
        "--processed",
        default=_DEFAULTS["processed"],
        help="Base directory for the processed data zone (data/processed).",
    )

    parser.add_argument(
        "--analytics",
        default=_DEFAULTS["analytics"],
        help="Base directory for the analytics data zone (data/analytics).",
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
        "landing":   args.landing,
        "raw":       args.raw,
        "rejected":  args.rejected,
        "logs":      args.logs,
        "processed": args.processed,
        "analytics": args.analytics,
        "reference": args.reference,
    }

    # Backward compatibility: if --input is explicitly passed
    if args.input:
        input_p = Path(args.input)
        if (input_p / "raw").exists() or (input_p / "landing").exists():
            paths["landing"] = str(input_p / "landing")
            paths["raw"] = str(input_p / "raw")
            paths["rejected"] = str(input_p / "rejected")
        else:
            paths["raw"] = str(input_p)

    if args.config:
        with open(args.config, "r", encoding="utf-8") as f:
            config = json.load(f)

        # Config keys override CLI defaults
        for key in ("landing", "raw", "rejected", "logs",
                    "processed", "analytics", "reference"):
            if key in config:
                paths[key] = config[key]

        if "input" in config and "raw" not in config:
            input_p = Path(config["input"])
            if (input_p / "raw").exists() or (input_p / "landing").exists():
                paths["landing"] = str(input_p / "landing")
                paths["raw"] = str(input_p / "raw")
                paths["rejected"] = str(input_p / "rejected")
            else:
                paths["raw"] = str(input_p)

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
    logger.info("Start time      : %s", start_dt)
    logger.info("Landing path    : %s", paths["landing"])
    logger.info("Raw path        : %s", paths["raw"])
    logger.info("Rejected path   : %s", paths["rejected"])
    logger.info("Logs path       : %s", paths["logs"])
    logger.info("Processed path  : %s", paths["processed"])
    logger.info("Analytics path  : %s", paths["analytics"])
    logger.info("Reference       : %s", paths["reference"])
    logger.info("=" * 70)

    spark = None
    status = "FAILED"
    landing_summary = {"detected": 0, "valid": 0, "rejected": 0}
    input_rows = 0
    rejected_count = 0
    nulls_handled = {}
    output_rows = 0

    try:
        # ── 1. Landing Ingestion (Landing -> Raw / Rejected) ───────
        logger.info("Stage 1/6 — Landing Ingestion (process_landing)")
        landing_summary = process_landing(
            landing_path=paths["landing"],
            raw_path=paths["raw"],
            rejected_path=paths["rejected"],
            logs_path=paths["logs"],
        )
        logger.info(
            "Landing Ingestion complete: %d detected, %d valid, %d rejected",
            landing_summary["detected"],
            landing_summary["valid"],
            landing_summary["rejected"],
        )

        # ── 2. Create Spark session ──────────────────────────────
        logger.info("Stage 2/6 — Creating Spark session")
        spark = create_spark_session(
            app_name="NOPIS_Telecom_Pipeline_SP7",
        )

        # ── 3. Ingest raw data from raw folder ───────────────────
        logger.info("Stage 3/6 — Ingestion (read_raw from %s)", paths["raw"])
        raw_df = read_raw(spark, paths["raw"])
        input_rows = raw_df.count()

        # ── 4. Clean and standardize ─────────────────────────────
        logger.info("Stage 4/6 — Cleaning (clean)")
        curated_df, rejected_count, nulls_handled = clean(
            spark, raw_df
        )

        # ── 5. Aggregate ────────────────────────────────────────
        logger.info("Stage 5/6 — Aggregation (aggregate)")
        hourly_grid_summary = aggregate(spark, curated_df)

        # ── 6a. Enrich with geospatial data ─────────────────────
        logger.info("Stage 6a/6 — Enrichment (enrich)")
        enriched_df = enrich(
            spark, hourly_grid_summary, paths["reference"]
        )

        # ── 6b. Write outputs ───────────────────────────────────
        logger.info("Stage 6b/6 — Writing outputs")
        output_rows = write_outputs(
            enriched_df,
            processed_path=paths["processed"],
            analytics_path=paths["analytics"],
        )

        # ── 6c. Load the complete output into MySQL ─────────────
        logger.info("Stage 6c/6 — Loading SQL warehouse")
        load_warehouse()

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
        logger.info("Final status    : %s", status)
        logger.info("Start time      : %s", start_dt)
        logger.info("End time        : %s", end_dt)
        logger.info("Elapsed         : %.1f seconds", elapsed)

        if status == "SUCCESS":
            logger.info("Landing detected: %d", landing_summary["detected"])
            logger.info("Landing valid   : %d", landing_summary["valid"])
            logger.info("Landing rejected: %d", landing_summary["rejected"])
            logger.info("Raw input rows  : %d", input_rows)
            logger.info("Rejected rows   : %d", rejected_count)
            logger.info("Nulls handled   : %s", nulls_handled)
            logger.info("Output rows     : %d", output_rows)
            logger.info("Processed path  : %s", paths["processed"])
            logger.info("Analytics path  : %s", paths["analytics"])

        logger.info("=" * 70)

        if spark:
            spark.stop()
            logger.info("SparkSession stopped.")


# ═════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    main()

