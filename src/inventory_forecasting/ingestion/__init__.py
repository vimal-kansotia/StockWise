"""Ingestion package initialization."""

from inventory_forecasting.ingestion.m5_loader import M5Loader
from inventory_forecasting.ingestion.synthetic_generator import generate_synthetic_m5_data
from inventory_forecasting.ingestion.validation import DataValidationError

__all__ = ["M5Loader", "generate_synthetic_m5_data", "DataValidationError"]
