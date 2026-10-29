"""Distributed PySpark ETL and Feature Engineering Pipeline.

Submits distributed transformations to Apache Spark Master/Workers:
- Reads Bronze Parquet
- Melts wide sales format into tall distributed DataFrame using PySpark SQL stack
- Joins calendar and prices across cluster partitions
- Computes windowed lags and rolling averages using Spark Window specs
- Writes final partitioned Gold dataset
"""

import sys
from pathlib import Path
from typing import Optional
from inventory_forecasting.config import settings


def get_spark_session(master_url: Optional[str] = None):
    """Initializes SparkSession configured for standalone cluster or local mode."""
    from pyspark.sql import SparkSession

    master = master_url or settings.spark_master_url
    builder = (
        SparkSession.builder.appName("SmartInventoryDistributedETL")
        .master(master)
        .config("spark.driver.memory", settings.spark_driver_memory)
        .config("spark.executor.memory", settings.spark_executor_memory)
        .config("spark.executor.cores", str(settings.spark_executor_cores))
        .config("spark.sql.adaptive.enabled", "true")
    )
    return builder.getOrCreate()


def run_spark_pipeline(
    bronze_dir: str,
    silver_dir: str,
    gold_dir: str,
    master_url: Optional[str] = None,
):
    """Executes distributed Bronze -> Silver -> Gold Spark pipeline."""
    from pyspark.sql import functions as F
    from pyspark.sql.window import Window

    spark = get_spark_session(master_url=master_url)
    print(f"Spark Session established. Application ID: {spark.sparkContext.applicationId}")
    print(f"Spark Master: {spark.sparkContext.master}")

    # 1. Read Bronze tables
    bronze_path = Path(bronze_dir)
    sales_df = spark.read.parquet(str(bronze_path / "bronze_sales.parquet"))
    cal_df = spark.read.parquet(str(bronze_path / "bronze_calendar.parquet"))
    price_df = spark.read.parquet(str(bronze_path / "bronze_sell_prices.parquet"))

    # 2. Reshape wide sales into tall distributed DataFrame
    d_cols = [c for c in sales_df.columns if c.startswith("d_")]
    meta_cols = [c for c in ["id", "item_id", "dept_id", "cat_id", "store_id", "state_id"] if c in sales_df.columns]

    # Construct PySpark stack expression
    stack_expr = f"stack({len(d_cols)}, " + ", ".join([f"'{c}', {c}" for c in d_cols]) + ") as (d, units_sold)"
    unpivoted_sales = sales_df.selectExpr(*meta_cols, stack_expr)
    unpivoted_sales = unpivoted_sales.withColumn("units_sold", F.coalesce(F.col("units_sold").cast("int"), F.lit(0)))

    # 3. Join with Calendar
    cal_sub = cal_df.select(
        "d",
        F.to_date("date").alias("date"),
        "wm_yr_wk",
        "wday",
        "month",
        "year",
        (F.coalesce(F.col("event_name_1"), F.lit("")) != "").cast("int").alias("has_event")
    )
    silver_joined = unpivoted_sales.join(cal_sub, on="d", how="inner")

    # 4. Join with Prices
    price_sub = price_df.select("store_id", "item_id", "wm_yr_wk", "sell_price").dropDuplicates()
    silver_joined = silver_joined.join(price_sub, on=["store_id", "item_id", "wm_yr_wk"], how="left")
    silver_joined = silver_joined.withColumn("sell_price", F.coalesce(F.col("sell_price"), F.lit(5.0)))

    # Write Silver
    silver_out = str(Path(silver_dir) / "spark_silver_sales")
    silver_joined.write.mode("overwrite").parquet(silver_out)
    print(f"Silver dataset written successfully to {silver_out}")

    # 5. Distributed Window Feature Engineering for Gold
    window_spec = Window.partitionBy("store_id", "item_id").orderBy("date")
    # Rolling 7 days: between -7 and -1 (preventing target leakage)
    window_7_spec = Window.partitionBy("store_id", "item_id").orderBy("date").rowsBetween(-7, -1)
    # Rolling 28 days: between -28 and -1
    window_28_spec = Window.partitionBy("store_id", "item_id").orderBy("date").rowsBetween(-28, -1)

    gold_df = (
        silver_joined
        .withColumn("day_of_week", F.dayofweek("date"))
        .withColumn("day_of_month", F.dayofmonth("date"))
        .withColumn("is_weekend", F.when(F.col("day_of_week").isin([1, 7]), 1).otherwise(0))
        .withColumn("lag_1", F.lag("units_sold", 1).over(window_spec))
        .withColumn("lag_7", F.lag("units_sold", 7).over(window_spec))
        .withColumn("lag_14", F.lag("units_sold", 14).over(window_spec))
        .withColumn("lag_28", F.lag("units_sold", 28).over(window_spec))
        .withColumn("rolling_mean_7", F.avg("units_sold").over(window_7_spec))
        .withColumn("rolling_std_7", F.stddev("units_sold").over(window_7_spec))
        .withColumn("rolling_mean_28", F.avg("units_sold").over(window_28_spec))
        .withColumn("rolling_std_28", F.stddev("units_sold").over(window_28_spec))
    )

    gold_out = str(Path(gold_dir) / "spark_gold_demand_features")
    gold_df.write.mode("overwrite").parquet(gold_out)
    print(f"Gold dataset written successfully to {gold_out}")
    spark.stop()


if __name__ == "__main__":
    b_dir = sys.argv[1] if len(sys.argv) > 1 else str(settings.bronze_dir)
    s_dir = sys.argv[2] if len(sys.argv) > 2 else str(settings.silver_dir)
    g_dir = sys.argv[3] if len(sys.argv) > 3 else str(settings.gold_dir)
    m_url = sys.argv[4] if len(sys.argv) > 4 else settings.spark_local_master
    run_spark_pipeline(b_dir, s_dir, g_dir, master_url=m_url)
