"""Train and evaluate forecasting models."""

from inventory_forecasting.config import settings
from inventory_forecasting.forecasting.train import ForecastTrainer

if __name__ == "__main__":
    print("Initiating out-of-sample model training and evaluation...")
    trainer = ForecastTrainer()
    results = trainer.train_and_evaluate()
    print("--- Model Evaluation Results ---")
    for m_name, metrics in results["evaluations"].items():
        print(f"[{m_name}] MAE: {metrics['mae']} | RMSE: {metrics['rmse']} | WAPE: {metrics['wape']} | Bias: {metrics['bias']}")
    print(f"Selected Champion Model: {results['champion']}")
    print(f"Champion Test Set WAPE: {results['test_metrics']['wape']}")
