"""
Spark session factory with Hadoop/winutils configuration for Windows.

Sets HADOOP_HOME to the winutils directory inside Phase_2 so that
Spark can write Parquet and other Hadoop-format outputs without a
full Hadoop installation or admin access.
"""

import os
import sys
import logging

from pyspark.sql import SparkSession

logger = logging.getLogger(__name__)

# Default winutils location relative to the project
_DEFAULT_HADOOP_HOME = r"D:\NOPIS\Phase_2\winutils"


def create_spark_session(
    app_name="NOPIS_Telecom_Pipeline",
    hadoop_home=None,
):
    """
    Create and return a configured SparkSession.

    Parameters
    ----------
    app_name : str
        Spark application name shown in the Spark UI.
    hadoop_home : str or None
        Path to the directory containing bin/winutils.exe.
        Defaults to D:\\NOPIS\\Phase_2\\winutils.

    Returns
    -------
    pyspark.sql.SparkSession
    """
    hadoop_home = hadoop_home or _DEFAULT_HADOOP_HOME

    # ── Temp directory (avoids PermissionError on system temp) ──────
    spark_tmp = r"D:\NOPIS\tmp\spark_temp"
    os.makedirs(spark_tmp, exist_ok=True)
    os.environ["TMPDIR"] = spark_tmp
    os.environ["TEMP"] = spark_tmp
    os.environ["TMP"] = spark_tmp
    os.environ["JAVA_TOOL_OPTIONS"] = f"-Djava.io.tmpdir={spark_tmp}"

    # ── Set environment variables BEFORE creating the session ────────
    os.environ["HADOOP_HOME"] = hadoop_home
    os.environ["hadoop.home.dir"] = hadoop_home
    os.environ["PATH"] = (
        os.path.join(hadoop_home, "bin")
        + os.pathsep
        + os.environ["PATH"]
    )

    # Use the same Python that is running this script
    os.environ["PYSPARK_PYTHON"] = sys.executable
    os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

    logger.info("HADOOP_HOME = %s", hadoop_home)
    logger.info("Temp dir    = %s", spark_tmp)
    logger.info("PYSPARK_PYTHON = %s", sys.executable)

    spark = (
        SparkSession.builder
        .appName(app_name)
        .master("local[*]")
        .config("spark.hadoop.home.dir", hadoop_home)
        .config("spark.local.dir", spark_tmp)
        .config("spark.sql.session.timeZone", "UTC")
        .config(
            "spark.driver.extraJavaOptions",
            f"-Djava.io.tmpdir={spark_tmp}",
        )
        .config("spark.python.worker.connect.timeout", "120")
        .config("spark.python.worker.reuse", "true")
        .config("spark.hadoop.io.native.lib.available", "false")
        .getOrCreate()
    )

    spark.sparkContext.setLogLevel("WARN")

    logger.info("SparkSession created — app: %s", app_name)

    return spark
