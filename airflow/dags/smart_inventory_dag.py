"""Apache Airflow DAG for Scheduled Smart Inventory and Demand Forecasting Pipeline."""

from datetime import datetime, timedelta
import os
import sys

# Ensure local source files can be imported by Airflow scheduler & workers
PROJECT_ROOT = os.getenv("PROJECT_ROOT", "/opt/airflow/dags/repo")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))

from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "data_science_team",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}


def task_check_source_availability():
    """Verifies that either raw M5 files or synthetic data generator inputs exist."""
    print("Checking source data availability...")
    raw_dir = os.path.join(PROJECT_ROOT, "data", "raw")
    synthetic_dir = os.path.join(PROJECT_ROOT, "data", "synthetic")
    
    has_raw = os.path.exists(os.path.join(raw_dir, "sales_train_validation.csv"))
    has_synthetic = os.path.exists(os.path.join(synthetic_dir, "sales_train_validation.csv"))
    
    if not (has_raw or has_synthetic):
        print("No source CSV found. Triggering synthetic generator...")
        from inventory_forecasting.ingestion.synthetic_generator import generate_synthetic_m5_data
        generate_synthetic_m5_data(output_dir=os.path.join(PROJECT_ROOT, "data", "synthetic"))
    print("Source data verified.")


def task_ingest_bronze():
    """Ingests source datasets into Bronze Parquet lake."""
    from inventory_forecasting.ingestion.m5_loader import M5Loader
    synthetic_dir = os.path.join(PROJECT_ROOT, "data", "synthetic")
    bronze_dir = os.path.join(PROJECT_ROOT, "data", "bronze")
    
    loader = M5Loader(source_dir=synthetic_dir, bronze_dir=bronze_dir)
    loader.load_and_ingest_bronze(is_synthetic=True)
    print("Bronze ingestion complete.")


def task_silver_transformation():
    """Cleans, normalizes, and joins sales, calendar, and price tables."""
    from inventory_forecasting.processing.pandas_pipeline import PandasPipeline
    pipeline = PandasPipeline(
        bronze_dir=os.path.join(PROJECT_ROOT, "data", "bronze"),
        silver_dir=os.path.join(PROJECT_ROOT, "data", "silver"),
        gold_dir=os.path.join(PROJECT_ROOT, "data", "gold"),
    )
    silver_path, metrics = pipeline.run_bronze_to_silver()
    print(f"Silver transformation complete. Records: {metrics['total_records']}")


def task_gold_features():
    """Generates lag, rolling, and temporal ML features."""
    from inventory_forecasting.processing.pandas_pipeline import PandasPipeline
    pipeline = PandasPipeline(
        bronze_dir=os.path.join(PROJECT_ROOT, "data", "bronze"),
        silver_dir=os.path.join(PROJECT_ROOT, "data", "silver"),
        gold_dir=os.path.join(PROJECT_ROOT, "data", "gold"),
    )
    gold_path, metrics = pipeline.run_silver_to_gold()
    print(f"Gold feature engineering complete. Features: {metrics['num_features']}")


def task_train_evaluate_models():
    """Trains LightGBM and Baselines out-of-sample and selects champion."""
    from inventory_forecasting.forecasting.train import ForecastTrainer
    trainer = ForecastTrainer(
        gold_file=os.path.join(PROJECT_ROOT, "data", "gold", "gold_demand_features.parquet")
    )
    results = trainer.train_and_evaluate()
    print(f"Model training complete. Champion: {results['champion']}")


def task_generate_forecasts():
    """Generates 7 and 28 day forward demand forecasts."""
    from inventory_forecasting.forecasting.predict import DemandPredictor
    from inventory_forecasting.database.repository import InventoryRepository
    from inventory_forecasting.database.session import SessionLocal
    
    predictor = DemandPredictor(
        gold_file=os.path.join(PROJECT_ROOT, "data", "gold", "gold_demand_features.parquet")
    )
    forecasts = predictor.generate_forecasts(horizon_days=28)
    
    db = SessionLocal()
    try:
        repo = InventoryRepository(db)
        repo.persist_forecasts(
            run_id=f"airflow-{datetime.now().strftime('%Y%m%d%H%M')}",
            model_name="champion_model",
            horizon_days=28,
            forecasts=forecasts,
        )
    finally:
        db.close()
    print(f"Forecasts persisted. Total: {len(forecasts)}")


def task_inventory_recommendations():
    """Calculates DDLT, safety stock, reorder point, and generates alerts."""
    import pandas as pd
    from inventory_forecasting.database.session import SessionLocal
    from inventory_forecasting.database.repository import InventoryRepository
    from inventory_forecasting.inventory.recommendations import InventoryEngine
    
    db = SessionLocal()
    try:
        repo = InventoryRepository(db)
        inv_snapshots = repo.get_latest_inventory(limit=500)
        if not inv_snapshots:
            print("No inventory snapshots found in database.")
            return

        inv_df = pd.DataFrame([{
            "store_id": i.store_id,
            "item_id": i.item_id,
            "stock_on_hand": i.stock_on_hand,
            "incoming_stock": i.incoming_stock,
            "committed_stock": i.committed_stock,
            "supplier_lead_time_days": i.supplier_lead_time_days,
            "min_order_qty": i.min_order_qty,
            "order_multiple": i.order_multiple,
        } for i in inv_snapshots])

        # Fetch forecasts
        all_forecasts = []
        for i in inv_snapshots:
            fc_list = repo.get_forecasts(i.item_id, i.store_id)
            for f in fc_list:
                all_forecasts.append({
                    "store_id": f.store_id,
                    "item_id": f.item_id,
                    "forecast_date": f.forecast_date,
                    "predicted_demand": f.predicted_demand,
                })
        forecasts_df = pd.DataFrame(all_forecasts)

        engine = InventoryEngine()
        recommendations = engine.generate_recommendations(inventory_df=inv_df, forecasts_df=forecasts_df)
        repo.persist_recommendations(recommendations)
        print(f"Calculated and persisted {len(recommendations)} inventory recommendations.")
    finally:
        db.close()


with DAG(
    dag_id="smart_inventory_daily_pipeline",
    default_args=default_args,
    description="Daily ETL, Demand Forecasting, and Inventory Replenishment DAG",
    schedule_interval="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["inventory", "forecasting", "m5"],
) as dag:

    t1 = PythonOperator(
        task_id="check_source_availability",
        python_callable=task_check_source_availability,
    )

    t2 = PythonOperator(
        task_id="ingest_bronze",
        python_callable=task_ingest_bronze,
    )

    t3 = PythonOperator(
        task_id="transform_silver",
        python_callable=task_silver_transformation,
    )

    t4 = PythonOperator(
        task_id="engineer_gold_features",
        python_callable=task_gold_features,
    )

    t5 = PythonOperator(
        task_id="train_evaluate_models",
        python_callable=task_train_evaluate_models,
    )

    t6 = PythonOperator(
        task_id="generate_forecasts",
        python_callable=task_generate_forecasts,
    )

    t7 = PythonOperator(
        task_id="calculate_inventory_recommendations",
        python_callable=task_inventory_recommendations,
    )

    t1 >> t2 >> t3 >> t4 >> t5 >> t6 >> t7
