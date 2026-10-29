#!/usr/bin/env bash
set -e

echo "=== 1. Setting up Python environment ==="
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "=== 2. Creating Directories ==="
mkdir -p data/raw data/bronze data/silver data/gold data/synthetic artifacts/models artifacts/metrics

echo "=== 3. Initializing Database ==="
python scripts/initialize_database.py

echo "=== 4. Generating Synthetic Data ==="
python scripts/generate_sample_data.py --stores 3 --products 15

echo "=== 5. Ingestion & ETL Pipeline ==="
python scripts/run_ingestion.py

echo "=== 6. Model Training & Evaluation ==="
python scripts/train_model.py

echo "=== 7. Generating Forecasts ==="
python scripts/generate_forecasts.py --horizon 28

echo "=== Setup & Verification Complete ==="
