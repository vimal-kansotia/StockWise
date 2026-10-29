"""Run Ingestion and Medallion ETL Pipeline."""

import argparse
from pathlib import Path
from inventory_forecasting.config import settings
from inventory_forecasting.ingestion.m5_loader import M5Loader
from inventory_forecasting.processing.pandas_pipeline import PandasPipeline

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run ingestion to Bronze, Silver, and Gold.")
    parser.add_argument("--source", type=str, default=str(settings.synthetic_dir), help="Source CSV directory")
    parser.add_argument("--synthetic", action="store_true", default=True, help="Flag if source is synthetic")

    args = parser.parse_args()
    source_path = Path(args.source)
    print(f"Starting ingestion from {source_path}...")

    # Bronze
    loader = M5Loader(source_dir=source_path, bronze_dir=settings.bronze_dir)
    b_out = loader.load_and_ingest_bronze(is_synthetic=args.synthetic)
    print(f"Bronze ingestion complete: {list(b_out.keys())}")

    # Silver & Gold
    pipeline = PandasPipeline(
        bronze_dir=settings.bronze_dir,
        silver_dir=settings.silver_dir,
        gold_dir=settings.gold_dir,
    )
    silver_path, s_metrics = pipeline.run_bronze_to_silver()
    print(f"Silver completed: {s_metrics['total_records']} rows.")

    gold_path, g_metrics = pipeline.run_silver_to_gold()
    print(f"Gold features completed: {g_metrics['num_features']} columns.")
