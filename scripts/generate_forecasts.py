"""Generate demand forecasts using the trained champion model."""

import argparse
from inventory_forecasting.database.repository import InventoryRepository
from inventory_forecasting.database.session import SessionLocal
from inventory_forecasting.forecasting.predict import DemandPredictor

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate future demand forecasts.")
    parser.add_argument("--horizon", type=int, default=28, help="Forecast horizon in days (7 or 28)")
    parser.add_argument("--run-id", type=str, default="cli-forecast-run", help="Identifier for this forecast batch")
    args = parser.parse_args()

    print(f"Generating recursive forward forecasts for horizon={args.horizon} days...")
    predictor = DemandPredictor()
    forecasts = predictor.generate_forecasts(horizon_days=args.horizon)

    db = SessionLocal()
    try:
        repo = InventoryRepository(db)
        repo.persist_forecasts(
            run_id=args.run_id,
            model_name="champion_model",
            horizon_days=args.horizon,
            forecasts=forecasts,
        )
        print(f"Persisted {len(forecasts)} forecast rows for run_id='{args.run_id}'.")
    finally:
        db.close()
