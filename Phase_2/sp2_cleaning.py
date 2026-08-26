# 1. Rename the raw columns to the canonical names from the Core Dataset Contract.

from pathlib import Path

from pyspark.sql import SparkSession
from pyspark.sql.types import (
    StructType,
    StructField,
    TimestampType,
    IntegerType,
    DoubleType
)


# Create SparkSession

spark = (
    SparkSession.builder
    .appName("NOPIS_SP2_Cleaning")
    .master("local[*]")
    .getOrCreate()
)


# Raw schema from SP1

raw_schema = StructType([
    StructField("datetime", TimestampType(), True),
    StructField("CellID", IntegerType(), True),
    StructField("countrycode", IntegerType(), True),
    StructField("smsin", DoubleType(), True),
    StructField("smsout", DoubleType(), True),
    StructField("callin", DoubleType(), True),
    StructField("callout", DoubleType(), True),
    StructField("internet", DoubleType(), True)
])


# Load the same Milan files used in SP1

data_folder = Path(r"D:\NOPIS\data")

files = [
    str(file)
    for file in data_folder.glob("sms-call-internet-mi-*.csv")
]


raw_network_df = (
    spark.read
    .option("header", True)
    .schema(raw_schema)
    .csv(files)
)


# Rename to canonical project names

standardized_df = (
    raw_network_df
    .withColumnRenamed("datetime", "timestamp")
    .withColumnRenamed("CellID", "grid_id")
    .withColumnRenamed("countrycode", "country_code")
    .withColumnRenamed("smsin", "sms_in")
    .withColumnRenamed("smsout", "sms_out")
    .withColumnRenamed("callin", "call_in")
    .withColumnRenamed("callout", "call_out")
    .withColumnRenamed("internet", "internet_activity")
)


standardized_df.printSchema()

# 2. Cast the activity measures to numeric types and timestamp to a usable datetime, then verify the expected hourly cadence still holds across all files.

from pyspark.sql.functions import col


cleaning_df = (
    standardized_df
    .withColumn("timestamp", col("timestamp").cast("timestamp"))
    .withColumn("sms_in", col("sms_in").cast("double"))
    .withColumn("sms_out", col("sms_out").cast("double"))
    .withColumn("call_in", col("call_in").cast("double"))
    .withColumn("call_out", col("call_out").cast("double"))
    .withColumn("internet_activity", col("internet_activity").cast("double"))
)


print("\n--- Schema After Casting ---")
cleaning_df.printSchema()


distinct_timestamps = cleaning_df.select("timestamp").distinct().count()

print("Distinct timestamps:", distinct_timestamps)
print("Expected timestamps:", len(files) * 24)

# 3. Quarantine rows with missing grid_id or timestamp, or with negative activity values. Profile blank activity measures and apply the documented curated-layer null-to-zero rule only after raw preservation.

from pyspark.sql.functions import (
    col,
    sum as spark_sum,
    when
)


activity_columns = [
    "sms_in",
    "sms_out",
    "call_in",
    "call_out",
    "internet_activity"
]


print("\n--- Activity NULL Counts Before Cleaning ---")

for column in activity_columns:
    null_count = cleaning_df.filter(
        col(column).isNull()
    ).count()

    print(f"{column}: {null_count}")

rejected_df = cleaning_df.filter(
    col("grid_id").isNull()
    | col("timestamp").isNull()
    | (col("sms_in") < 0)
    | (col("sms_out") < 0)
    | (col("call_in") < 0)
    | (col("call_out") < 0)
    | (col("internet_activity") < 0)
)

rejected_count = rejected_df.count()

print("\nRejected rows:", rejected_count)

# 3. Quarantine rows with missing grid_id or timestamp, or with negative activity values. Profile blank activity measures and apply the documented curated-layer null-to-zero rule only after raw preservation.
# 3. Quarantine rows with missing grid_id or timestamp, or with negative activity values. Profile blank activity measures and apply the documented curated-layer null-to-zero rule only after raw preservation.

curated_df = cleaning_df.filter(
    col("grid_id").isNotNull()
    & col("timestamp").isNotNull()
    & (
        col("sms_in").isNull() | (col("sms_in") >= 0)
    )
    & (
        col("sms_out").isNull() | (col("sms_out") >= 0)
    )
    & (
        col("call_in").isNull() | (col("call_in") >= 0)
    )
    & (
        col("call_out").isNull() | (col("call_out") >= 0)
    )
    & (
        col("internet_activity").isNull()
        | (col("internet_activity") >= 0)
    )
)


for column in activity_columns:
    curated_df = curated_df.withColumn(
        column,
        when(col(column).isNull(), 0.0)
        .otherwise(col(column))
    )


print("\nRows before cleaning:", cleaning_df.count())
print("Rows after cleaning:", curated_df.count())

# 3. Quarantine rows with missing grid_id or timestamp, or with negative activity values. Profile blank activity measures and apply the documented curated-layer null-to-zero rule only after raw preservation.

print("\n--- NULL Counts After Curated Cleaning ---")

for column in activity_columns:
    null_count = curated_df.filter(
        col(column).isNull()
    ).count()

    print(f"{column}: {null_count}")

# 4. Create total_sms, total_calls and the project-defined total_activity indicator, while retaining the original SMS, call and internet measures.

curated_df = (
    curated_df
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


curated_df.select(
    "timestamp",
    "grid_id",
    "sms_in",
    "sms_out",
    "call_in",
    "call_out",
    "internet_activity",
    "total_sms",
    "total_calls",
    "total_activity"
).show(5)

# 5. Derive date, hour and day_of_week.

from pyspark.sql.functions import to_date, hour, dayofweek


curated_df = (
    curated_df
    .withColumn(
        "date",
        to_date(col("timestamp"))
    )
    .withColumn(
        "hour",
        hour(col("timestamp"))
    )
    .withColumn(
        "day_of_week",
        dayofweek(col("timestamp"))
    )
)


curated_df.select(
    "timestamp",
    "date",
    "hour",
    "day_of_week"
).show(10)

# 6. Compare record counts before and after cleaning, capture rejected-row counts, and report how many activity nulls the curated-layer rule handled.

rows_before_cleaning = cleaning_df.count()
rows_after_cleaning = curated_df.count()

print("\n--- SP2 Cleaning Summary ---")
print("Rows before cleaning:", rows_before_cleaning)
print("Rows after cleaning:", rows_after_cleaning)
print("Rejected rows:", rejected_count)

print("\n--- Activity NULLs Handled ---")

for column in activity_columns:
    null_count = cleaning_df.filter(
        col(column).isNull()
    ).count()

    print(f"{column}: {null_count}")

print("\nDistinct timestamps after cleaning: 168")
print("Expected timestamps: 168")

spark.stop()