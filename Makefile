.PHONY: help setup test run-pipeline run-api docker-up docker-down spark-validate lint clean

help:
	@echo "Smart Inventory and Demand Forecasting System Commands:"
	@echo "  make setup          - Install dependencies and bootstrap environment"
	@echo "  make test           - Run automated unit and API test suite"
	@echo "  make run-pipeline   - Run complete end-to-end ingestion, ETL, forecasting & inventory engine"
	@echo "  make run-api        - Start FastAPI backend server locally"
	@echo "  make docker-up      - Start all Docker services (Postgres, Spark Master/Workers, API, Airflow)"
	@echo "  make docker-down    - Stop and teardown Docker containers"
	@echo "  make spark-validate - Verify Spark master and worker connectivity"
	@echo "  make lint           - Run ruff linter check"
	@echo "  make clean          - Remove temporary files and caches"

setup:
	bash scripts/setup.sh

test:
	.venv/bin/pytest tests/ -v

run-pipeline:
	.venv/bin/python -c "from inventory_forecasting.pipelines.run_pipeline import run_full_pipeline; run_full_pipeline(use_synthetic=True)"

run-api:
	.venv/bin/uvicorn inventory_forecasting.api.main:app --host 0.0.0.0 --port 8000 --reload

docker-up:
	docker compose up -d

docker-down:
	docker compose down

spark-validate:
	.venv/bin/python scripts/validate_cluster.py

lint:
	.venv/bin/ruff check src/ tests/

clean:
	rm -rf __pycache__ .pytest_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +
