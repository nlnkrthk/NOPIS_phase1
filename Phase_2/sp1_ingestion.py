# 1. Create a SparkSession.

from pyspark.sql import SparkSession
from pyspark.sql.functions import input_file_name
from pyspark.sql.types import (
    StructType,
    StructField,
    TimestampType,
    IntegerType,
    DoubleType
)

spark = (
    SparkSession.builder
    .appName("NOPIS_SP1_Ingestion")
    .master("local[*]")
    .getOrCreate()
)

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


# 2. Read the daily files from a folder using the pattern sms-call-internet-mi-*.csv. Use the -mi- in the glob — see the trap below.

from pathlib import Path

data_folder = Path(r"D:\NOPIS\data")

files = [
    str(file)
    for file in data_folder.glob("sms-call-internet-mi-*.csv")
]

print("Files found:", len(files))

for file in files:
    print(file)

raw_network_df = (
    spark.read
    .option("header", True)
    .schema(raw_schema)
    .csv(files)
)

raw_network_df.printSchema()
raw_network_df.show(5, truncate=False)


# 3. Compare inferSchema against a trainer-provided manual StructType, and explain the cost of each.

inferred_df = (
    spark.read
    .option("header", True)
    .option("inferSchema", True)
    .csv(files)
)

print("\n--- Manual Schema ---")
raw_network_df.printSchema()

print("\n--- Inferred Schema ---")
inferred_df.printSchema()

# 4. Count rows, source files, unique grids, country-code categories and distinct hourly intervals.

from pyspark.sql.functions import (
    count,
    countDistinct,
    min,
    max
)

row_count = raw_network_df.count()

unique_grids = raw_network_df.select("CellID").distinct().count()

country_code_categories = raw_network_df.select("countrycode").distinct().count()

distinct_hourly_intervals = raw_network_df.select("datetime").distinct().count()

print("\n--- SP1 Question 4 Results ---")
print("Row count:", row_count)
print("Unique grids:", unique_grids)
print("Country-code categories:", country_code_categories)
print("Distinct hourly intervals:", distinct_hourly_intervals)

# 5. Add an input_file_name column for traceability.

raw_network_df = raw_network_df.withColumn(
    "input_file_name",
    input_file_name()
)

raw_network_df.select(
    "datetime",
    "CellID",
    "countrycode",
    "input_file_name"
).show(5, truncate=False)

# 5. Add an input_file_name column for traceability.

source_file_count = (
    raw_network_df
    .select("input_file_name")
    .distinct()
    .count()
)

print("Source file count:", source_file_count)

# 6. Inspect the partition count and explain why file layout affects Spark execution.

partition_count = raw_network_df.rdd.getNumPartitions()

print("Partition count:", partition_count)

# SP1 Acceptance Validation

from pyspark.sql.functions import min, max, col

print("Minimum CellID:", raw_network_df.select(min("CellID")).first()[0])
print("Maximum CellID:", raw_network_df.select(max("CellID")).first()[0])

missing_source_files = raw_network_df.filter(
    col("input_file_name").isNull()
).count()

print("Rows with missing input_file_name:", missing_source_files)

spark.stop()