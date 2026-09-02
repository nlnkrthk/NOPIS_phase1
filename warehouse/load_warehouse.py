import json
import pandas as pd
from sqlalchemy import create_engine, text


# ================================================================
# Configuration
# ================================================================

DATABASE_URL = "mysql+pymysql://root:root@localhost/nopis"

GEOJSON_PATH = r"D:\NOPIS\data\reference\milano-grid.geojson"

PARQUET_PATH = r"D:\NOPIS\data\processed\enriched_hourly_grid"


# ================================================================
# MySQL connection
# ================================================================

engine = create_engine(DATABASE_URL)


# ================================================================
# 109. Load dim_grid from the static Milan reference once.
# ================================================================

def load_dim_grid():

    print("Loading dim_grid...")

    # Check whether dim_grid already contains data
    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM dim_grid")
        ).scalar()

    if count > 0:
        print(
            f"dim_grid already contains {count} rows. "
            "Skipping reload."
        )
        return

    with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
        geo_data = json.load(f)

    records = []

    for feature in geo_data["features"]:

        grid_id = feature["properties"]["cellId"]

        geometry = feature["geometry"]

        centroid_lon = None
        centroid_lat = None

        if (
            geometry["type"] == "Polygon"
            and geometry["coordinates"]
        ):

            coords = geometry["coordinates"][0]

            centroid_lon = sum(
                point[0] for point in coords
            ) / len(coords)

            centroid_lat = sum(
                point[1] for point in coords
            ) / len(coords)

        records.append({
            "grid_id": grid_id,
            "centroid_lon": centroid_lon,
            "centroid_lat": centroid_lat,
            "geometry": json.dumps(geometry)
        })

    dim_grid_df = pd.DataFrame(records)

    dim_grid_df.to_sql(
        "dim_grid",
        engine,
        if_exists="append",
        index=False,
        chunksize=1000
    )

    print(
        f"dim_grid loaded: {len(dim_grid_df)} rows"
    )


# ================================================================
# 109. Load dim_time and fact_network_activity
# from Spark output.
# ================================================================

def load_activity_data():

    print("Reading Spark Parquet output...")

    df = pd.read_parquet(PARQUET_PATH)

    print(
        f"Parquet rows: {len(df)}"
    )

    # ------------------------------------------------------------
    # Create timestamp
    # ------------------------------------------------------------

    df["timestamp"] = pd.to_datetime(
        df["timestamp"]
    )

    # ------------------------------------------------------------
    # Create time_key
    # ------------------------------------------------------------

    df["time_key"] = (
        df["timestamp"]
        .dt.strftime("%Y%m%d%H")
    )

    # ============================================================
    # 109. Load dim_time
    # ============================================================

    dim_time_df = pd.DataFrame({

        "time_key": df["time_key"],

        "timestamp": df["timestamp"],

        "date": df["timestamp"].dt.date,

        "hour": df["timestamp"].dt.hour,

        "day": df["timestamp"].dt.day,

        "month": df["timestamp"].dt.month,

        "year": df["timestamp"].dt.year

    })

    dim_time_df = dim_time_df.drop_duplicates(
        subset=["time_key"]
    )

    print(
        f"Loading dim_time: "
        f"{len(dim_time_df)} rows"
    )

    # Only insert time keys that don't already exist
    with engine.connect() as conn:

        existing = pd.read_sql(
            text("SELECT time_key FROM dim_time"),
            conn
        )

    if not existing.empty:

        dim_time_df = dim_time_df[
            ~dim_time_df["time_key"].isin(
                existing["time_key"]
            )
        ]

    if not dim_time_df.empty:

        dim_time_df.to_sql(
            "dim_time",
            engine,
            if_exists="append",
            index=False,
            chunksize=1000
        )

    print("dim_time loaded.")

    # ============================================================
    # 106. Load fact_network_activity
    # ============================================================

    fact_columns = [

        "grid_id",
        "time_key",

        "sms_in",
        "sms_out",

        "call_in",
        "call_out",

        "internet_activity",

        "total_sms",
        "total_calls",

        "total_activity",
        "internet_share"
    ]

    fact_df = df[fact_columns].copy()

    print(
        f"Loading fact_network_activity: "
        f"{len(fact_df)} rows"
    )

    # Only insert records that don't already exist
    with engine.connect() as conn:

        existing = pd.read_sql(
            text("SELECT grid_id, time_key FROM fact_network_activity"),
            conn
        )

    if not existing.empty:

        # Create a composite key for comparison
        existing['composite_key'] = (
            existing['grid_id'].astype(str) + '-' + existing['time_key']
        )

        fact_df['composite_key'] = (
            fact_df['grid_id'].astype(str) + '-' + fact_df['time_key']
        )

        fact_df = fact_df[
            ~fact_df['composite_key'].isin(existing['composite_key'])
        ]

        fact_df = fact_df.drop(columns=['composite_key'])

    if not fact_df.empty:

        fact_df.to_sql(
            "fact_network_activity",
            engine,
            if_exists="append",
            index=False,
            chunksize=5000
        )

        print(
            f"fact_network_activity loaded: {len(fact_df)} new rows"
        )

    else:

        print("fact_network_activity: No new rows to insert.")


# ================================================================
# Main
# ================================================================

if __name__ == "__main__":

    print("=" * 60)
    print("NOPIS — MySQL Warehouse Load")
    print("=" * 60)

    load_dim_grid()

    load_activity_data()

    print("=" * 60)
    print("Warehouse loading completed successfully.")
    print("=" * 60)