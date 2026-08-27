import json
from pathlib import Path
from pyspark.sql.functions import col, sum as spark_sum, broadcast
from pyspark.sql import SparkSession
from pyspark.sql.types import (
    StructType,
    StructField,
    IntegerType,
    StringType
)
import os
import sys

# Tell Spark to use the same Python installation running this script
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

os.environ["HADOOP_HOME"] = r"D:\NOPIS\Phase_2\winutils"
os.environ["hadoop.home.dir"] = r"D:\NOPIS\Phase_2\winutils"
os.environ["PATH"] = (
    r"D:\NOPIS\Phase_2\winutils\bin;"
    + os.environ["PATH"]
)

spark = (
    SparkSession.builder
    .appName("NOPIS_SP4_Geospatial")
    .master("local[1]")
    .config("spark.python.worker.connect.timeout", "120")
    .config("spark.python.worker.reuse", "true")
    .config("spark.hadoop.io.native.lib.available", "false")
    .getOrCreate()
)


# ============================================================
# LOAD SP3 OUTPUT FROM PARQUET
# ============================================================

sp3_output_path = r"D:\NOPIS\Phase_2\outputs\hourly_grid_summary"

hourly_grid_summary = spark.read.parquet(sp3_output_path)

print("\n--- SP3 Parquet Loaded ---")
print("Hourly grid summary rows:", hourly_grid_summary.count())
hourly_grid_summary.show(5)


# ============================================================
# 1. Load milano-grid.geojson and inspect its structure:
# the top-level type, where the grid identifier is stored,
# and the geometry type.
# ============================================================

geojson_path = Path(
    r"D:\NOPIS\data\milano-grid.geojson"
)

with open(geojson_path, "r", encoding="utf-8") as f:
    geo_data = json.load(f)


print("\n1--- GeoJSON Inspection ---")

print(
    "Top-level type:",
    geo_data.get("type")
)

print(
    "Number of features:",
    len(geo_data.get("features", []))
)


# ============================================================
# INSPECT FIRST FEATURE
# ============================================================

feature = geo_data["features"][0]

print("\n--- First Feature ---")

print(
    "Feature type:",
    feature.get("type")
)

print(
    "Top-level id:",
    feature.get("id")
)

print(
    "Properties:",
    feature.get("properties")
)

print(
    "Geometry type:",
    feature.get("geometry", {}).get("type")
)


# ============================================================
# 2. Identify the common key between the telecom activity
# dataset and the GeoJSON. In the GeoJSON it is
# properties.cellId; in the project schema it is grid_id.
# ============================================================


# ============================================================
# 3. Normalize the identifier: flatten features[] into a
# lookup of grid_id + geometry, mapping properties.cellId
# → grid_id.
# ============================================================

grid_lookup_data = []

for feature in geo_data["features"]:

    # IMPORTANT:
    # Use properties.cellId as the project grid_id.
    # Do NOT use the top-level feature["id"].
    grid_id = feature["properties"]["cellId"]

    geometry = feature["geometry"]

    grid_lookup_data.append(
        (
            grid_id,
            json.dumps(geometry)
        )
    )


print("\n2--- Grid Lookup ---")

print(
    "Grid lookup rows:",
    len(grid_lookup_data)
)

print("First 5 lookup records:")

for row in grid_lookup_data[:5]:
    print(row)


# ============================================================
# CREATE SPARK GRID LOOKUP
# ============================================================

grid_schema = StructType([
    StructField(
        "grid_id",
        IntegerType(),
        False
    ),
    StructField(
        "geometry",
        StringType(),
        False
    )
])


grid_lookup_df = spark.createDataFrame(
    grid_lookup_data,
    schema=grid_schema
)

# ============================================================
# 4. Inspect the size of the grid lookup relative to the
# activity DataFrame — 10,000 rows against many millions.
# ============================================================

print("\n--- Grid Lookup Validation ---")

print("Grid lookup created successfully.")
print("Grid lookup rows:", len(grid_lookup_data))

print("\n--- Spark Grid Lookup ---")
grid_lookup_df.printSchema()

grid_lookup_df.show(5, truncate=False)
# ============================================================
# SHOW GRID LOOKUP
# ============================================================

print("\n--- Spark Grid Lookup ---")

grid_lookup_df.printSchema()

grid_lookup_df.show(
    5,
    truncate=False
)

# ============================================================
# 5. Perform a left join between the processed network activity
# data and the Milan grid lookup on grid_id.
# ============================================================

from pyspark.sql.functions import broadcast

enriched_df = (
    hourly_grid_summary
    .join(
        broadcast(grid_lookup_df),
        on="grid_id",
        how="left"
    )
)

print("\n---5 -  SP4 Geospatial Enrichment ---")

print("Rows before join:", hourly_grid_summary.count())
print("Rows after join:", enriched_df.count())

enriched_df.show(5, truncate=False)
# ============================================================
# 6. Validate the join by checking:
#    - count of distinct activity grids before the join
#    - count after the join
#    - grids with missing geometry
#    - percentage successfully enriched
#    - unmatched grid_id values
# ============================================================

print("\n--- 6 - SP4 Join Validation ---")

# Distinct grid IDs in SP3 activity
activity_grids_df = (
    hourly_grid_summary
    .select("grid_id")
    .distinct()
)

activity_grid_count = activity_grids_df.count()

# Distinct grid IDs in the GeoJSON lookup
lookup_grids_df = (
    grid_lookup_df
    .select("grid_id")
    .distinct()
)

lookup_grid_count = lookup_grids_df.count()

# Find activity grid IDs that do NOT exist in the GeoJSON lookup
unmatched_grids_df = (
    activity_grids_df
    .join(
        lookup_grids_df,
        on="grid_id",
        how="left_anti"
    )
)

unmatched_grid_count = unmatched_grids_df.count()

# Calculate coverage
enriched_grid_count = activity_grid_count - unmatched_grid_count

if activity_grid_count > 0:
    enrichment_coverage = (
        enriched_grid_count / activity_grid_count
    ) * 100
else:
    enrichment_coverage = 0.0

print("Distinct activity grids before join:", activity_grid_count)
print("Distinct grids in lookup:", lookup_grid_count)
print("Unmatched grid IDs:", unmatched_grid_count)
print("Enrichment coverage:", enrichment_coverage, "%")

print("\n--- Unmatched Grid IDs ---")

if unmatched_grid_count == 0:
    print("No unmatched grid IDs.")
else:
    unmatched_grids_df.show(
        unmatched_grid_count,
        truncate=False
    )

# ============================================================
# 7. Validate the join geographically as well as numerically.
#
# Check the centroids of grid_id 1 and grid_id 2.
# They should be adjacent rather than identical or far apart.
# Also print the centroid of a selected grid cell.
# ============================================================
# ============================================================
# 7. Validate the join geographically as well as numerically.
#
# The centroid of a named grid cell is printed and should land
# in the expected part of Milan.
#
# The centroids of grid_id 1 and grid_id 2 should be adjacent
# rather than identical or far apart.
# ============================================================

print("\n--- 7 - Geographic Spot Check ---")


# ------------------------------------------------------------
# Calculate centroid from a Polygon geometry
# ------------------------------------------------------------
def calculate_centroid(geometry):

    coordinates = geometry["coordinates"][0]

    # Last coordinate repeats the first coordinate,
    # so exclude it from the calculation.
    points = coordinates[:-1]

    longitudes = [point[0] for point in points]
    latitudes = [point[1] for point in points]

    centroid_lon = sum(longitudes) / len(longitudes)
    centroid_lat = sum(latitudes) / len(latitudes)

    return centroid_lon, centroid_lat


# ------------------------------------------------------------
# Create a direct lookup from the ORIGINAL GeoJSON
# ------------------------------------------------------------
# IMPORTANT:
# grid_id comes from properties.cellId, not feature["id"].

geojson_grid_lookup = {
    feature["properties"]["cellId"]: feature["geometry"]
    for feature in geo_data["features"]
}


# ------------------------------------------------------------
# Grid 1
# ------------------------------------------------------------
geometry_1 = geojson_grid_lookup[1]

centroid_1 = calculate_centroid(geometry_1)

print("\nGrid 1 centroid:")
print("Longitude:", centroid_1[0])
print("Latitude:", centroid_1[1])


# ------------------------------------------------------------
# Grid 2
# ------------------------------------------------------------
geometry_2 = geojson_grid_lookup[2]

centroid_2 = calculate_centroid(geometry_2)

print("\nGrid 2 centroid:")
print("Longitude:", centroid_2[0])
print("Latitude:", centroid_2[1])


# ------------------------------------------------------------
# Check that Grid 1 and Grid 2 are not identical
# ------------------------------------------------------------
assert centroid_1 != centroid_2, (
    "Geographic validation failed: "
    "Grid 1 and Grid 2 have identical centroids."
)


# ------------------------------------------------------------
# Calculate approximate distance between centroids
# ------------------------------------------------------------
distance = (
    (centroid_2[0] - centroid_1[0]) ** 2
    +
    (centroid_2[1] - centroid_1[1]) ** 2
) ** 0.5

print("\nApproximate centroid distance:", distance)


# ------------------------------------------------------------
# Selected grid cell
# ------------------------------------------------------------
selected_grid_id = 285

selected_geometry = geojson_grid_lookup[selected_grid_id]

selected_centroid = calculate_centroid(
    selected_geometry
)

print(f"\nGrid {selected_grid_id} centroid:")
print("Longitude:", selected_centroid[0])
print("Latitude:", selected_centroid[1])


print("\nGeographic spot-check PASSED!")

# ============================================================
# 8. Compare the Spark execution plan for a standard join
# against a broadcast join, and explain why the grid lookup
# is a broadcast candidate.
# ============================================================

from pyspark.sql.functions import broadcast

print("\n--- 8 - Standard Join Execution Plan ---")

standard_join_df = (
    hourly_grid_summary
    .join(
        grid_lookup_df,
        on="grid_id",
        how="left"
    )
)

standard_join_df.explain()

print("\n--- 8 - Broadcast Join Execution Plan ---")

broadcast_join_df = (
    hourly_grid_summary
    .join(
        broadcast(grid_lookup_df),
        on="grid_id",
        how="left"
    )
)

broadcast_join_df.explain()

print("\n--- Broadcast Join Explanation ---")
print("Grid lookup contains only 10,000 rows.")
print("Activity DataFrame contains 1,679,994 rows.")
print("The grid lookup is much smaller than the activity data.")
print("Therefore, it is a good candidate for a broadcast join.")
print("Broadcasting allows Spark to send the small lookup to")
print("the workers instead of performing a large shuffle join.")

# ============================================================
# 9. Create an enriched dataset containing timestamp, grid_id,
# sms_in, sms_out, call_in, call_out, internet_activity,
# total_activity and geometry.
# ============================================================

from pyspark.sql.functions import broadcast

print("\n--- 9 - SP4 Geospatial Enrichment ---")

grid_activity_geo_df = (
    hourly_grid_summary
    .join(
        broadcast(grid_lookup_df),
        on="grid_id",
        how="left"
    )
    .select(
        "timestamp",
        "grid_id",
        "sms_in",
        "sms_out",
        "call_in",
        "call_out",
        "internet_activity",
        "total_activity",
        "geometry"
    )
)

print("Enriched DataFrame created successfully!")

print("\n--- Enriched Dataset Schema ---")
grid_activity_geo_df.printSchema()

# DO NOT use .show() here because the Spark Python worker
# is currently failing during collect/display operations.


# ============================================================
# SAVE SP4 ENRICHED DATASET
# ============================================================

sp4_output_path = r"D:\NOPIS\Phase_2\outputs\grid_activity_geo"

print("\n--- Saving SP4 Enriched Dataset ---")

grid_activity_geo_df.write \
    .mode("overwrite") \
    .parquet(sp4_output_path)

print("SP4 enriched dataset saved successfully!")
print("Saved to:", sp4_output_path)

# ============================================================
# 10. Identify the top high-activity grids for a selected
# window and retain their geometry for later visualization.
# ============================================================

print("\n--- 10 - Top High-Activity Grids ---")

selected_date = "2013-11-01"

top_10_grids_geo = (
    grid_activity_geo_df
    .filter(col("timestamp").cast("date") == selected_date)
    .groupBy("grid_id", "geometry")
    .agg(
        spark_sum("total_activity").alias("activity")
    )
    .orderBy(
        col("activity").desc()
    )
    .limit(10)
)

print("Selected date:", selected_date)
print("Top 10 high-activity grids:")

top_10_grids_geo.show(
    10,
    truncate=False
)

# ============================================================
# SAVE TOP HIGH-ACTIVITY GRIDS
# ============================================================

top_grids_output_path = (
    r"D:\NOPIS\Phase_2\outputs\top_high_activity_grids"
)

print("\n--- Saving Top High-Activity Grids ---")

top_10_grids_geo.write \
    .mode("overwrite") \
    .parquet(top_grids_output_path)

print("Top high-activity grids saved successfully!")
print("Saved to:", top_grids_output_path)


# ============================================================
# 11. Optionally derive the centroid of each grid polygon,
# for simpler map visualizations and API responses.
# ============================================================

from pyspark.sql.functions import udf
from pyspark.sql.types import (
    StructType,
    StructField,
    DoubleType
)

def calculate_centroid(geometry_json):
    try:
        geometry = json.loads(geometry_json)

        coordinates = geometry["coordinates"][0]

        # Remove the duplicated last coordinate
        # if the polygon is closed.
        if coordinates[0] == coordinates[-1]:
            coordinates = coordinates[:-1]

        longitudes = [point[0] for point in coordinates]
        latitudes = [point[1] for point in coordinates]

        centroid_longitude = sum(longitudes) / len(longitudes)
        centroid_latitude = sum(latitudes) / len(latitudes)

        return (
            centroid_longitude,
            centroid_latitude
        )

    except Exception:
        return (None, None)


centroid_schema = StructType([
    StructField(
        "centroid_longitude",
        DoubleType(),
        True
    ),
    StructField(
        "centroid_latitude",
        DoubleType(),
        True
    )
])

centroid_udf = udf(
    calculate_centroid,
    centroid_schema
)

# Add centroid to the top high-activity grids
top_10_with_centroid = (
    top_10_grids_geo
    .withColumn(
        "centroid",
        centroid_udf(col("geometry"))
    )
    .select(
        "grid_id",
        "activity",
        "geometry",
        col("centroid.centroid_longitude")
            .alias("centroid_longitude"),
        col("centroid.centroid_latitude")
            .alias("centroid_latitude")
    )
)

print("\n--- 11 - Grid Centroids ---")

top_10_with_centroid.show(
    10,
    truncate=False
)

# ============================================================
# SAVE CENTROID DATA
# ============================================================

centroid_output_path = (
    r"D:\NOPIS\Phase_2\outputs\top_high_activity_grids_centroid"
)

top_10_with_centroid.write \
    .mode("overwrite") \
    .parquet(centroid_output_path)

print(
    "\nTop high-activity grids with centroids "
    "saved successfully!"
)

# ============================================================
# 12 - SP4 Join Strategy Comparison
#
# 52. Compare the Spark execution plan for a standard join
# against a broadcast join, and explain why the grid lookup
# is a broadcast candidate.
# ============================================================

print("\n--- 12 - Standard Join Execution Plan ---")

standard_join_df = (
    hourly_grid_summary
    .join(
        grid_lookup_df,
        on="grid_id",
        how="left"
    )
)

standard_join_df.explain()

print("\n--- 12 - Broadcast Join Execution Plan ---")

broadcast_join_df = (
    hourly_grid_summary
    .join(
        broadcast(grid_lookup_df),
        on="grid_id",
        how="left"
    )
)

broadcast_join_df.explain()