"""
ml/features.py — ML2 Feature Engineering and Feature Store Pipeline.

Computes the standard ML2 feature set from the analytics warehouse:
- avg_activity
- activity_growth
- active_hours
- peak_ratio
- variability
- internet_share
- feature_timestamp
"""

from datetime import datetime
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

DATABASE_URL = "mysql+pymysql://root:root@localhost/nopis"

def init_features_table(engine):
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS grid_features (
                grid_id INT PRIMARY KEY,
                feature_timestamp DATETIME NOT NULL,
                avg_activity DOUBLE NOT NULL,
                activity_growth DOUBLE NOT NULL,
                active_hours INT NOT NULL,
                peak_ratio DOUBLE NOT NULL,
                variability DOUBLE NOT NULL,
                internet_share DOUBLE NOT NULL,
                data_quality_status VARCHAR(50) NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (grid_id) REFERENCES dim_grid(grid_id)
            )
        """))

def compute_and_store_features():
    engine = create_engine(DATABASE_URL)
    init_features_table(engine)

    with engine.connect() as conn:
        max_ts = conn.execute(text("SELECT MAX(timestamp) FROM dim_time")).scalar()
        if max_ts is None:
            print("No data in dim_time.")
            return

        # Read trailing 24 hours of grid activity up to max_ts
        query = text("""
            SELECT 
                f.grid_id,
                t.timestamp,
                f.total_activity,
                f.internet_activity
            FROM fact_network_activity f
            JOIN dim_time t ON f.time_key = t.time_key
            WHERE t.timestamp <= :max_ts
            ORDER BY f.grid_id, t.timestamp ASC
        """)
        df = pd.read_sql(query, conn, params={"max_ts": max_ts})

    if df.empty:
        print("No fact data found.")
        return

    # Compute ML2 features per grid
    records = []
    for grid_id, group in df.groupby("grid_id"):
        # Take trailing 24 observations
        g = group.tail(24)
        acts = g["total_activity"].values
        internets = g["internet_activity"].values

        n = len(acts)
        if n == 0:
            continue

        mean_act = float(np.mean(acts))
        std_act = float(np.std(acts)) if n > 1 else 0.0
        max_act = float(np.max(acts))
        
        # 12h growth comparison
        half = n // 2
        first_half = np.mean(acts[:half]) if half > 0 else mean_act
        second_half = np.mean(acts[half:]) if half > 0 else mean_act
        growth = float((second_half - first_half) / (first_half + 1e-5))

        active_hrs = int(np.sum(acts > 0))
        peak_rat = float(max_act / (mean_act + 1e-5))
        var = float(std_act / (mean_act + 1e-5))
        
        tot_act_sum = np.sum(acts)
        net_share = float(np.sum(internets) / (tot_act_sum + 1e-5)) if tot_act_sum > 0 else 0.0

        dq_status = "VALID" if n >= 20 else "PARTIAL"

        records.append({
            "grid_id": int(grid_id),
            "feature_timestamp": max_ts,
            "avg_activity": mean_act,
            "activity_growth": growth,
            "active_hours": active_hrs,
            "peak_ratio": peak_rat,
            "variability": var,
            "internet_share": net_share,
            "data_quality_status": dq_status
        })

    feat_df = pd.DataFrame(records)
    print(f"Generated features for {len(feat_df)} grids.")

    # Save to grid_features table in MySQL
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE grid_features"))
    feat_df.to_sql("grid_features", engine, if_exists="append", index=False)
    print("Stored features into MySQL table grid_features.")

if __name__ == "__main__":
    compute_and_store_features()
