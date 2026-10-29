"""Application configuration and environment settings."""

from pathlib import Path
from typing import List, Optional
import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Base Project Root directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # General
    app_name: str = "Smart Inventory and Demand Forecasting System"
    env: str = "development"
    log_level: str = "INFO"
    api_key: str = "dev-secret-api-key-2026"
    jwt_secret_key: str = "super-secret-jwt-key-2026-inventory"
    cors_origins: str = "*"
    host: str = "0.0.0.0"
    port: int = 8000

    # PostgreSQL Database
    postgres_user: str = "inventory_user"
    postgres_password: str = "inventory_secure_pass"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "inventory_db"

    # SQLite Fallback / Development file (for standalone lightweight testing without Docker)
    use_sqlite_fallback: bool = False
    sqlite_db_path: str = str(BASE_DIR / "data" / "inventory.db")

    # Spark
    spark_master_url: str = "spark://spark-master:7077"
    spark_local_master: str = "local[*]"
    spark_driver_memory: str = "1g"
    spark_executor_memory: str = "1g"
    spark_executor_cores: int = 1

    # Forecasting & Inventory Defaults
    default_lead_time_days: int = 7
    default_service_level: float = 0.95
    forecast_horizon_short: int = 7
    forecast_horizon_long: int = 28
    random_seed: int = 42

    # Directory Paths
    base_dir: Path = BASE_DIR
    data_dir: Path = BASE_DIR / "data"
    raw_dir: Path = BASE_DIR / "data" / "raw"
    bronze_dir: Path = BASE_DIR / "data" / "bronze"
    silver_dir: Path = BASE_DIR / "data" / "silver"
    gold_dir: Path = BASE_DIR / "data" / "gold"
    synthetic_dir: Path = BASE_DIR / "data" / "synthetic"
    artifacts_dir: Path = BASE_DIR / "artifacts"
    models_dir: Path = BASE_DIR / "artifacts" / "models"
    metrics_dir: Path = BASE_DIR / "artifacts" / "metrics"

    @property
    def database_url(self) -> str:
        """Construct PostgreSQL connection URL, or fallback to SQLite if configured or PG unavailable."""
        if self.use_sqlite_fallback:
            return f"sqlite:///{self.sqlite_db_path}"
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


def load_yaml_config(path: Optional[Path] = None) -> dict:
    config_path = path or (BASE_DIR / "config" / "settings.yaml")
    if config_path.exists():
        with open(config_path, "r") as f:
            return yaml.safe_load(f) or {}
    return {}


settings = Settings()
yaml_config = load_yaml_config()
