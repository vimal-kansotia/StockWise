"""Model Registry for saving, loading, and tracking champion models and metadata."""

import json
from pathlib import Path
from typing import Any, Dict, Optional
import joblib
from inventory_forecasting.config import settings


class ModelRegistry:
    def __init__(self, models_dir: Optional[Path] = None, metrics_dir: Optional[Path] = None):
        self.models_dir = models_dir or settings.models_dir
        self.metrics_dir = metrics_dir or settings.metrics_dir
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.metrics_dir.mkdir(parents=True, exist_ok=True)

    def save_model(
        self,
        model_name: str,
        model_artifact: Any,
        metadata: Dict[str, Any],
        is_champion: bool = False,
    ) -> Path:
        """Saves model artifact and associated metadata JSON."""
        model_file = self.models_dir / f"{model_name}.joblib"
        metadata_file = self.models_dir / f"{model_name}_metadata.json"

        joblib.dump(model_artifact, model_file)
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

        if is_champion:
            champion_file = self.models_dir / "champion_model.joblib"
            champion_meta = self.models_dir / "champion_metadata.json"
            joblib.dump(model_artifact, champion_file)
            with open(champion_meta, "w") as f:
                json.dump({**metadata, "champion": True}, f, indent=2)

        return model_file

    def load_model(self, model_name: str = "champion_model") -> Any:
        """Loads a model artifact by name or champion."""
        model_file = self.models_dir / f"{model_name}.joblib"
        if not model_file.exists():
            raise FileNotFoundError(f"Model file not found: {model_file}")
        return joblib.load(model_file)

    def load_metadata(self, model_name: str = "champion_model") -> Dict[str, Any]:
        """Loads model metadata."""
        meta_file = self.models_dir / f"{model_name}_metadata.json"
        if not meta_file.exists():
            return {}
        with open(meta_file, "r") as f:
            return json.load(f)
