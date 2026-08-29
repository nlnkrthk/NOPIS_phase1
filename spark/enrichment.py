"""
Enrichment module — joins telecom data with Milano grid GeoJSON.

Derived from SP4 (sp4_geospatial.py).
"""

import json
import logging

from pyspark.sql.functions import col, broadcast
from pyspark.sql.types import (
    StructType,
    StructField,
    IntegerType,
    StringType,
)

logger = logging.getLogger(__name__)


def _load_grid_lookup(spark, reference_path):
    """
    Load milano-grid.geojson and build a Spark DataFrame of
    (grid_id, geometry) for broadcast joining.

    The data is written to a temp JSON file and read back via
    Spark's JVM-native JSON reader. This avoids createDataFrame()
    from Python data, which triggers PythonRDD workers that can
    time out on restricted Windows environments.

    Parameters
    ----------
    spark : pyspark.sql.SparkSession
    reference_path : str
        Path to ``milano-grid.geojson``.

    Returns
    -------
    pyspark.sql.DataFrame
        Two columns: grid_id (int), geometry (string/JSON).
    """
    import os
    import tempfile

    logger.info("Loading GeoJSON reference: %s", reference_path)

    with open(reference_path, "r", encoding="utf-8") as f:
        geo_data = json.load(f)

    features = geo_data.get("features", [])
    logger.info("GeoJSON features: %d", len(features))

    # ── Write lookup to a temp JSON file (JVM-native read) ────────
    # Each line is a JSON object: {"grid_id": ..., "geometry": "..."}
    tmp_dir = r"D:\NOPIS\tmp\spark_temp"
    os.makedirs(tmp_dir, exist_ok=True)
    tmp_path = os.path.join(tmp_dir, "grid_lookup.json")

    with open(tmp_path, "w", encoding="utf-8") as f:
        for feature in features:
            record = {
                "grid_id": feature["properties"]["cellId"],
                "geometry": json.dumps(feature["geometry"]),
            }
            f.write(json.dumps(record) + "\n")

    logger.info("Grid lookup written to temp file: %s", tmp_path)

    # ── Read back via Spark's JVM reader (no PythonRDD) ──────────
    grid_schema = StructType([
        StructField("grid_id", IntegerType(), False),
        StructField("geometry", StringType(), False),
    ])

    grid_lookup_df = (
        spark.read
        .schema(grid_schema)
        .json(tmp_path)
    )

    row_count = grid_lookup_df.count()
    logger.info("Grid lookup DataFrame loaded: %d rows", row_count)

    return grid_lookup_df


def enrich(spark, hourly_grid_summary, reference_path):
    """
    Enrich the hourly grid summary with geometry from the GeoJSON.

    Uses a broadcast join (the grid lookup is ~10 000 rows vs millions
    of activity rows).

    Parameters
    ----------
    spark : pyspark.sql.SparkSession
    hourly_grid_summary : pyspark.sql.DataFrame
        Output of ``aggregation.aggregate()``.
    reference_path : str
        Path to ``milano-grid.geojson``.

    Returns
    -------
    pyspark.sql.DataFrame
        Enriched DataFrame with columns: timestamp, grid_id, sms_in,
        sms_out, call_in, call_out, internet_activity, total_activity,
        geometry, date, hour, total_sms, total_calls, internet_share.
    """
    rows_before = hourly_grid_summary.count()
    logger.info("Enrichment — rows before join: %d", rows_before)

    grid_lookup_df = _load_grid_lookup(spark, reference_path)

    # ── Broadcast join ────────────────────────────────────────────
    enriched_df = (
        hourly_grid_summary
        .join(
            broadcast(grid_lookup_df),
            on="grid_id",
            how="left",
        )
    )

    rows_after = enriched_df.count()
    logger.info("Enrichment — rows after join: %d", rows_after)

    # ── Validate: no row inflation ────────────────────────────────
    if rows_after != rows_before:
        logger.warning(
            "Row count changed after join! Before: %d, After: %d",
            rows_before,
            rows_after,
        )

    # ── Coverage stats ────────────────────────────────────────────
    missing_geometry = (
        enriched_df
        .filter(col("geometry").isNull())
        .select("grid_id")
        .distinct()
        .count()
    )

    total_grids = (
        enriched_df.select("grid_id").distinct().count()
    )

    enriched_grids = total_grids - missing_geometry

    if total_grids > 0:
        coverage_pct = (enriched_grids / total_grids) * 100
    else:
        coverage_pct = 0.0

    logger.info(
        "Enrichment coverage: %d/%d grids (%.1f%%)",
        enriched_grids,
        total_grids,
        coverage_pct,
    )

    if missing_geometry > 0:
        logger.warning(
            "%d grid(s) have no geometry after join.",
            missing_geometry,
        )

    return enriched_df
