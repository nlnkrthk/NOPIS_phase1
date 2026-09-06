import json
import os
import pandas as pd
from sqlalchemy import create_engine, text


# ================================================================
# Configuration
# ================================================================

DATABASE_URL = os.environ.get(
    "NOPIS_DATABASE_URL",
    "mysql+pymysql://root:root@localhost:3306/nopis",
)
GEOJSON_PATH = "/mnt/d/NOPIS/data/reference/milano-grid.geojson"
PARQUET_PATH = "/mnt/d/NOPIS/data/processed/enriched_hourly_grid"


# ================================================================
# MySQL connection
# ================================================================

engine = create_engine(
    DATABASE_URL,
    connect_args={"connect_timeout": 10},
    pool_pre_ping=True,
)


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

def load_activity_data(parquet_path=PARQUET_PATH, replace=True):

    print("Reading Spark Parquet output...")

    df = pd.read_parquet(parquet_path)

    print(
        f"Parquet rows: {len(df)}"
    )

    expected_fact_rows = len(df)

    if replace:
        with engine.begin() as conn:
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            conn.execute(text("TRUNCATE TABLE fact_network_activity"))
            conn.execute(text("TRUNCATE TABLE dim_time"))
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))

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

    if not dim_time_df.empty:
        time_insert = text("""
            INSERT IGNORE INTO dim_time
                (time_key, timestamp, date, hour, day, month, year)
            VALUES
                (:time_key, :timestamp, :date, :hour, :day, :month, :year)
        """)
        with engine.begin() as conn:
            conn.execute(time_insert, dim_time_df.to_dict("records"))

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

    if not fact_df.empty:
        fact_insert = text("""
            INSERT INTO fact_network_activity
                (grid_id, time_key, sms_in, sms_out, call_in, call_out,
                 internet_activity, total_sms, total_calls, total_activity,
                 internet_share)
            VALUES
                (:grid_id, :time_key, :sms_in, :sms_out, :call_in, :call_out,
                 :internet_activity, :total_sms, :total_calls, :total_activity,
                 :internet_share)
            ON DUPLICATE KEY UPDATE
                sms_in = VALUES(sms_in),
                sms_out = VALUES(sms_out),
                call_in = VALUES(call_in),
                call_out = VALUES(call_out),
                internet_activity = VALUES(internet_activity),
                total_sms = VALUES(total_sms),
                total_calls = VALUES(total_calls),
                total_activity = VALUES(total_activity),
                internet_share = VALUES(internet_share)
        """)
        with engine.begin() as conn:
            for start in range(0, len(fact_df), 5000):
                conn.execute(
                    fact_insert,
                    fact_df.iloc[start:start + 5000].to_dict("records"),
                )

        print(
            f"fact_network_activity loaded: {len(fact_df)} new rows"
        )

        with engine.connect() as conn:
            actual_fact_rows = conn.execute(
                text("SELECT COUNT(*) FROM fact_network_activity")
            ).scalar()

        if replace and actual_fact_rows != expected_fact_rows:
            raise RuntimeError(
                "fact_network_activity row-count mismatch: "
                f"expected {expected_fact_rows}, found {actual_fact_rows}"
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