"""Generate reproducible synthetic sample data."""

import argparse
from pathlib import Path
from inventory_forecasting.config import settings
from inventory_forecasting.ingestion.synthetic_generator import generate_synthetic_m5_data

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic Walmart M5 format dataset.")
    parser.add_argument("--stores", type=int, default=3, help="Number of stores")
    parser.add_argument("--products", type=int, default=15, help="Number of products")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--out", type=str, default=str(settings.synthetic_dir), help="Output directory")

    args = parser.parse_args()
    print(f"Generating synthetic data: {args.stores} stores, {args.products} products to {args.out}...")
    generate_synthetic_m5_data(
        num_stores=args.stores,
        num_products=args.products,
        seed=args.seed,
        output_dir=Path(args.out),
    )
    print("Done generating synthetic datasets.")
