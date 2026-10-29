"""Operational pipeline runner orchestrating Ingestion, ETL, Modeling, and Inventory Engine."""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
import pandas as pd
from inventory_forecasting.config import settings
from inventory_forecasting.database.models import ModelEvaluation
from inventory_forecasting.database.repository import InventoryRepository
from inventory_forecasting.database.session import SessionLocal, init_db
from inventory_forecasting.forecasting.predict import DemandPredictor
from inventory_forecasting.forecasting.train import ForecastTrainer
from inventory_forecasting.ingestion.m5_loader import M5Loader
from inventory_forecasting.ingestion.synthetic_generator import generate_synthetic_m5_data
from inventory_forecasting.inventory.recommendations import InventoryEngine
from inventory_forecasting.processing.pandas_pipeline import PandasPipeline


def run_full_pipeline(
    use_synthetic: bool = True,
    num_stores: int = 3,
    num_products: int = 15,
) -> Dict[str, Any]:
    """Executes the complete end-to-end data science and data engineering pipeline.
    
    Stages:
    1. Database initialization
    2. Data generation / verification
    3. Bronze Ingestion
    4. Silver cleaning & Gold feature engineering (ETL)
    5. PostgreSQL daily sales persistence
    6. Model training & validation (Seasonal Naive vs Moving Avg vs LightGBM)
    7. Multi-step forward recursive forecasting (7 & 28 days)
    8. Inventory recommendation engine & alerting
    9. Persistence of forecasts and inventory recommendations
    """
    run_id = f"pipeline-{uuid.uuid4().hex[:8]}"
    start_time = datetime.now(timezone.utc)
    db = SessionLocal()
    repo = InventoryRepository(db)

    try:
        # Step 1: Ensure DB tables exist
        init_db()

        # Step 2: Source Data Preparation
        if use_synthetic:
            generate_synthetic_m5_data(
                num_stores=num_stores,
                num_products=num_products,
                output_dir=settings.synthetic_dir,
            )
            source_dir = settings.synthetic_dir
        else:
            source_dir = settings.raw_dir

        # Step 3: Bronze Lake Ingestion
        loader = M5Loader(source_dir=source_dir, bronze_dir=settings.bronze_dir)
        loader.load_and_ingest_bronze(is_synthetic=use_synthetic)

        # Step 4: Silver & Gold Medallion Processing
        pipeline = PandasPipeline(
            bronze_dir=settings.bronze_dir,
            silver_dir=settings.silver_dir,
            gold_dir=settings.gold_dir,
        )
        silver_path, s_metrics = pipeline.run_bronze_to_silver()
        gold_path, g_metrics = pipeline.run_silver_to_gold()

        # Step 5: Persist Daily Sales to DB
        silver_df = pd.read_parquet(silver_path)
        repo.persist_daily_sales(silver_df)

        # Persist Inventory Snapshots if present
        inv_file = source_dir / "inventory_snapshots.csv"
        if inv_file.exists():
            inv_df = pd.read_csv(inv_file)
            repo.persist_inventory_snapshots(inv_df)
        else:
            # Build sample snapshot from latest products
            unique_items = silver_df[["store_id", "item_id"]].drop_duplicates()
            inv_rows = []
            for _, r in unique_items.iterrows():
                inv_rows.append({
                    "store_id": r["store_id"],
                    "item_id": r["item_id"],
                    "snapshot_date": silver_df["date"].max(),
                    "stock_on_hand": 50,
                    "incoming_stock": 20,
                    "committed_stock": 0,
                    "unit_cost": 10.0,
                    "supplier_lead_time_days": 7,
                    "min_order_qty": 10,
                    "order_multiple": 5,
                })
            inv_df = pd.DataFrame(inv_rows)
            repo.persist_inventory_snapshots(inv_df)

        # Step 6: Forecasting Model Training & Champion Selection
        trainer = ForecastTrainer(gold_file=gold_path)
        train_results = trainer.train_and_evaluate()

        # Save evaluations in database
        for model_name, metrics in train_results["evaluations"].items():
            db.add(
                ModelEvaluation(
                    model_name=model_name,
                    mae=metrics["mae"],
                    rmse=metrics["rmse"],
                    wape=metrics["wape"],
                    bias=metrics["bias"],
                    horizon_days=28,
                    validation_split="validation_set",
                    feature_count=len(train_results["features"]),
                    is_champion=(model_name == train_results["champion"]),
                )
            )
        db.commit()

        # Step 7: Forecast Generation
        predictor = DemandPredictor(gold_file=gold_path)
        forecasts = predictor.generate_forecasts(horizon_days=28)
        repo.persist_forecasts(
            run_id=run_id,
            model_name=train_results["champion"],
            horizon_days=28,
            forecasts=forecasts,
        )

        # Step 8: Inventory Recommendation Engine
        forecasts_df = pd.DataFrame(forecasts)
        engine = InventoryEngine()
        recommendations = engine.generate_recommendations(
            inventory_df=inv_df,
            forecasts_df=forecasts_df,
            historical_sales_df=silver_df,
        )
        repo.persist_recommendations(recommendations)

        return {
            "status": "SUCCESS",
            "run_id": run_id,
            "duration_seconds": (datetime.now(timezone.utc) - start_time).total_seconds(),
            "silver_metrics": s_metrics,
            "gold_metrics": g_metrics,
            "champion_model": train_results["champion"],
            "test_metrics": train_results["test_metrics"],
            "forecast_count": len(forecasts),
            "recommendation_count": len(recommendations),
        }
    finally:
        db.close()
