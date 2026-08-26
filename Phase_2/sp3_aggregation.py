# 1. Collapse the country-code-level records to one row per timestamp + grid_id by summing sms_in, sms_out, call_in, call_out and internet_activity across country-code categories.

from pyspark.sql import SparkSession
from pyspark.sql.functions import sum as spark_sum
from pyspark.sql.functions import when
from sp2_cleaning import NetworkDataCleaner
from pyspark.sql.functions import (
    col,
    hour,
    to_date,
    sum as spark_sum
)

spark = (
    SparkSession.builder
    .appName("NOPIS_SP3_Aggregation")
    .master("local[*]")
    .getOrCreate()
)


print("SP2 NetworkDataCleaner imported successfully!")

cleaner = NetworkDataCleaner(spark)

print("NetworkDataCleaner object created successfully!")

clean_network_df = cleaner.run()

print("SP2 cleaning completed successfully!")


# SP3 Question 1:
# Collapse country-code-level records to timestamp + grid_id

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



print("\n--- Hourly Grid Summary ---")
hourly_grid_summary.show(5)

hourly_count = hourly_grid_summary.count()

print("Hourly grid summary rows:", hourly_count)

# Add time features back to the consolidated grid/hour DataFrame

from pyspark.sql.functions import hour, to_date

hourly_grid_summary = (
    hourly_grid_summary
    .withColumn("date", to_date(col("timestamp")))
    .withColumn("hour", hour(col("timestamp")))
)

# Validate the grain: one row per grid_id + timestamp

duplicate_count = (
    hourly_grid_summary
    .groupBy("grid_id", "timestamp")
    .count()
    .filter("count > 1")
    .count()
)

print("\n--- Q1 Grain Validation ---")
print("Duplicate grid + timestamp combinations:", duplicate_count)

assert duplicate_count == 0, (
    "Validation failed: hourly_grid_summary contains duplicate "
    "(grid_id, timestamp) combinations."
)

print("Grain validation PASSED!")

# 2. From the consolidated grid/hour DataFrame compute total SMS activity, total call activity, internet activity, total_activity, and daily activity per grid.

from pyspark.sql.functions import (
    col,
    sum as spark_sum
)


# Calculate hourly activity KPIs

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

hourly_grid_summary = (
    hourly_grid_summary
    .withColumn("date", col("timestamp").cast("date"))
)
# Calculate daily activity per grid

daily_traffic_summary = (
    hourly_grid_summary
    .groupBy("date", "grid_id")
    .agg(
        spark_sum("total_activity").alias("daily_activity")
    )
)


print("\n--- Daily Traffic Summary ---")

daily_traffic_summary.show(5)

# 3. Identify the top ten high-activity grids for selected windows.

from pyspark.sql.functions import col


# Select one window: 2013-11-01

selected_date = "2013-11-01"

top_10_grids = (
    daily_traffic_summary
    .filter(col("date") == selected_date)
    .orderBy(col("daily_activity").desc())
    .limit(10)
)


print("\n--- Top 10 High-Activity Grids ---")
print("Selected date:", selected_date)

top_10_grids.show()

# 4. Compute the peak activity hour.

from pyspark.sql.functions import sum as spark_sum

peak_activity_hour = (
    hourly_grid_summary
    .groupBy("hour")
    .agg(
        spark_sum("total_activity").alias("total_activity")
    )
    .orderBy(col("total_activity").desc())
    .limit(1)
)

print("\n--- Peak Activity Hour ---")

peak_activity_hour.show()
# 5. Compute internet share of total activity.

hourly_grid_summary = (
    hourly_grid_summary
    .withColumn(
        "internet_share",
        when(
            col("total_activity") > 0,
            col("internet_activity") / col("total_activity")
        ).otherwise(0.0)
    )
)

print("\n--- Internet Share of Total Activity ---")

hourly_grid_summary.select(
    "timestamp",
    "grid_id",
    "internet_activity",
    "total_activity",
    "internet_share"
).show(10)
# 6. Validate the final hourly_grid_summary against the SP3 acceptance criteria.

print("\n--- SP3 Final Validation ---")

# Check 1: Zero duplicates on grid_id + timestamp
duplicate_count = (
    hourly_grid_summary
    .groupBy("grid_id", "timestamp")
    .count()
    .filter(col("count") > 1)
    .count()
)

print("Duplicate grid + timestamp combinations:", duplicate_count)

assert duplicate_count == 0, "Grain validation FAILED!"

print("Grain validation PASSED!")


# Check 2: hourly_grid_summary must be smaller than clean_network_df
clean_count = clean_network_df.count()
hourly_count = hourly_grid_summary.count()

print("Clean network rows:", clean_count)
print("Hourly grid summary rows:", hourly_count)

assert hourly_count < clean_count, \
    "Hourly summary should have fewer rows than clean data."

print("Row count reduction validation PASSED!")


# Check 3: Maximum possible rows = D × 24 × 10000
number_of_days = clean_network_df.select("date").distinct().count()

expected_max_rows = number_of_days * 24 * 10000

print("Number of days:", number_of_days)
print("Maximum expected rows:", expected_max_rows)
print("Actual hourly summary rows:", hourly_count)

assert hourly_count <= expected_max_rows, \
    "Hourly summary exceeds the theoretical maximum."

print("Maximum row-count validation PASSED!")


# Check 4: country_code must not exist in hourly_grid_summary
assert "country_code" not in hourly_grid_summary.columns, \
    "country_code should not exist in hourly_grid_summary."

print("country_code removal validation PASSED!")

spark.stop()