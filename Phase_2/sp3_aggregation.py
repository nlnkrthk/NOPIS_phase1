
import os

hadoop_home = r"D:\NOPIS\Phase_2\winutils\hadoop-3.3.6"

os.environ["HADOOP_HOME"] = hadoop_home
os.environ["hadoop.home.dir"] = hadoop_home
os.environ["PATH"] = (
    os.path.join(hadoop_home, "bin")
    + os.pathsep
    + os.environ["PATH"]
)

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    hour,
    to_date,
    sum as spark_sum,
    when
)

from sp2_cleaning import NetworkDataCleaner


class NetworkDataAggregator:

    def __init__(self, spark):
        self.spark = spark

    def run(self):

        # ============================================================
        # STEP 1 — GET CLEAN DATA FROM SP2
        # ============================================================

        print("\n--- Running SP2 Cleaning ---")

        cleaner = NetworkDataCleaner(self.spark)
        clean_network_df = cleaner.run()

        print("SP2 cleaning completed successfully!")

        # ============================================================
        # SP3 Q1 — COUNTRY CODE → GRID/HOUR GRAIN
        # ============================================================

        print("\n--- SP3 Q1: Country-Code Consolidation ---")

        hourly_grid_summary = (
            clean_network_df
            .groupBy("timestamp", "grid_id")
            .agg(
                spark_sum("sms_in").alias("sms_in"),
                spark_sum("sms_out").alias("sms_out"),
                spark_sum("call_in").alias("call_in"),
                spark_sum("call_out").alias("call_out"),
                spark_sum("internet_activity").alias("internet_activity")
            )
        )

        # Add date and hour
        hourly_grid_summary = (
            hourly_grid_summary
            .withColumn("date", to_date(col("timestamp")))
            .withColumn("hour", hour(col("timestamp")))
        )

        print("\n--- Hourly Grid Summary ---")

        hourly_grid_summary.show(5)

        hourly_count = hourly_grid_summary.count()

        print("Hourly grid summary rows:", hourly_count)

        # ============================================================
        # Q1 GRAIN VALIDATION
        # ============================================================

        duplicate_count = (
            hourly_grid_summary
            .groupBy("grid_id", "timestamp")
            .count()
            .filter(col("count") > 1)
            .count()
        )

        print("\n--- Q1 Grain Validation ---")
        print(
            "Duplicate grid + timestamp combinations:",
            duplicate_count
        )

        assert duplicate_count == 0, (
            "Validation failed: hourly_grid_summary contains "
            "duplicate (grid_id, timestamp) combinations."
        )

        print("Grain validation PASSED!")

        # ============================================================
        # SP3 Q2 — ACTIVITY KPIs
        # ============================================================

        print("\n--- SP3 Q2: Activity KPIs ---")

        hourly_grid_summary = (
            hourly_grid_summary

            .withColumn(
                "total_sms",
                col("sms_in") + col("sms_out")
            )

            .withColumn(
                "total_calls",
                col("call_in") + col("call_out")
            )

            .withColumn(
                "total_activity",
                col("sms_in")
                + col("sms_out")
                + col("call_in")
                + col("call_out")
                + col("internet_activity")
            )
        )

        print("\n--- Hourly Activity KPIs ---")

        hourly_grid_summary.select(
            "timestamp",
            "grid_id",
            "total_sms",
            "total_calls",
            "internet_activity",
            "total_activity"
        ).show(5)

        # ============================================================
        # DAILY ACTIVITY PER GRID
        # ============================================================

        daily_traffic_summary = (
            hourly_grid_summary
            .groupBy("date", "grid_id")
            .agg(
                spark_sum("total_activity")
                .alias("daily_activity")
            )
        )

        print("\n--- Daily Traffic Summary ---")

        daily_traffic_summary.show(5)

        # ============================================================
        # SP3 Q3 — TOP 10 HIGH-ACTIVITY GRIDS
        # ============================================================

        print("\n--- SP3 Q3: Top 10 High-Activity Grids ---")

        selected_date = "2013-11-01"

        top_10_grids = (
            daily_traffic_summary
            .filter(col("date") == selected_date)
            .orderBy(col("daily_activity").desc())
            .limit(10)
        )

        print("Selected date:", selected_date)

        top_10_grids.show()

        # ============================================================
        # SP3 Q4 — PEAK ACTIVITY HOUR
        # ============================================================

        print("\n--- SP3 Q4: Peak Activity Hour ---")

        peak_activity_hour = (
            hourly_grid_summary
            .groupBy("hour")
            .agg(
                spark_sum("total_activity")
                .alias("total_activity")
            )
            .orderBy(col("total_activity").desc())
            .limit(1)
        )

        peak_activity_hour.show()

        # ============================================================
        # SP3 Q5 — INTERNET SHARE
        # ============================================================

        print("\n--- SP3 Q5: Internet Share of Total Activity ---")

        hourly_grid_summary = (
            hourly_grid_summary
            .withColumn(
                "internet_share",
                when(
                    col("total_activity") > 0,
                    col("internet_activity")
                    / col("total_activity")
                ).otherwise(0.0)
            )
        )

        hourly_grid_summary.select(
            "timestamp",
            "grid_id",
            "internet_activity",
            "total_activity",
            "internet_share"
        ).show(10)

        # ============================================================
        # SP3 FINAL VALIDATION
        # ============================================================

        print("\n--- SP3 Final Validation ---")

        # ------------------------------------------------------------
        # Check 1 — No duplicate grid + timestamp
        # ------------------------------------------------------------

        duplicate_count = (
            hourly_grid_summary
            .groupBy("grid_id", "timestamp")
            .count()
            .filter(col("count") > 1)
            .count()
        )

        print(
            "Duplicate grid + timestamp combinations:",
            duplicate_count
        )

        assert duplicate_count == 0, (
            "Grain validation FAILED!"
        )

        print("Grain validation PASSED!")

        # ------------------------------------------------------------
        # Check 2 — Summary must have fewer rows
        # ------------------------------------------------------------

        clean_count = clean_network_df.count()
        hourly_count = hourly_grid_summary.count()

        print("Clean network rows:", clean_count)
        print("Hourly grid summary rows:", hourly_count)

        assert hourly_count < clean_count, (
            "Hourly summary should have fewer rows than clean data."
        )

        print("Row count reduction validation PASSED!")

        # ------------------------------------------------------------
        # Check 3 — Maximum theoretical row count
        # D × 24 × 10000
        # ------------------------------------------------------------

        number_of_days = (
            clean_network_df
            .select("date")
            .distinct()
            .count()
        )

        expected_max_rows = (
            number_of_days * 24 * 10000
        )

        print("Number of days:", number_of_days)
        print("Maximum expected rows:", expected_max_rows)
        print("Actual hourly summary rows:", hourly_count)

        assert hourly_count <= expected_max_rows, (
            "Hourly summary exceeds the theoretical maximum."
        )

        print("Maximum row-count validation PASSED!")

        # ------------------------------------------------------------
        # Check 4 — country_code must be removed
        # ------------------------------------------------------------

        assert "country_code" not in hourly_grid_summary.columns, (
            "country_code should not exist in "
            "hourly_grid_summary."
        )

        print("country_code removal validation PASSED!")

        # ============================================================
        # RETURN RESULTS
        # ============================================================

        return {
            "hourly_grid_summary": hourly_grid_summary,
            "daily_traffic_summary": daily_traffic_summary,
            "top_10_grids": top_10_grids,
            "peak_activity_hour": peak_activity_hour
        }


# ================================================================
# RUN DIRECTLY
# ================================================================
if __name__ == "__main__":

    spark = (
        SparkSession.builder
        .appName("NOPIS_SP3_Aggregation")
        .master("local[*]")
        .getOrCreate()
    )

    print("SP3 NetworkDataAggregator started!")

    aggregator = NetworkDataAggregator(spark)

    results = aggregator.run()

    print("\nSP3 aggregation completed successfully!")

    # ============================================================
    # SAVE SP3 OUTPUT FOR SP4
    # ============================================================

    hourly_grid_summary = results["hourly_grid_summary"]

    output_path = r"D:\NOPIS\Phase_2\outputs\hourly_grid_summary"

    print("\n--- Saving SP3 Output ---")

    hourly_grid_summary.write \
        .mode("overwrite") \
        .parquet(output_path)

    print("SP3 output saved successfully!")
    print("Saved to:", output_path)

    spark.stop()