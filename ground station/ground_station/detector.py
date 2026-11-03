"""In-process detector adapter for teammate-provided serialized models."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np


class EmbeddedDetector:
    """Load and execute a detector artifact inside the Ground Station process.

    A teammate model should expose ``predict_tile(tile)`` and return a mapping.
    Standard scikit-learn estimators are also supported through ``predict``.
    """

    def __init__(self, model_path: str | Path) -> None:
        path = Path(model_path)
        if not path.is_file():
            raise FileNotFoundError(f"Detector model not found: {path}")
        try:
            import joblib
        except ImportError as exc:
            raise RuntimeError("Install joblib before using --detector-model") from exc
        self.model = joblib.load(path)
        self.path = path

    def analyze(self, tile: np.ndarray, *, trusted: bool, analysis_only: bool) -> dict[str, Any]:
        if tile.shape != (13, 256, 256) or tile.dtype != np.uint16:
            raise ValueError("Detector input must be a uint16 tile with shape (13, 256, 256)")

        if hasattr(self.model, "predict_tile"):
            result = self.model.predict_tile(tile)
        elif hasattr(self.model, "predict"):
            result = self.model.predict(tile.reshape(1, -1))
        else:
            raise TypeError("Detector artifact must expose predict_tile(tile) or predict(features)")

        return {
            "status": "ok",
            "model": str(self.path),
            "trusted": trusted,
            "analysis_only": analysis_only,
            "result": self._json_safe(result),
        }

    @classmethod
    def _json_safe(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): cls._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._json_safe(item) for item in value]
        if isinstance(value, np.ndarray):
            return cls._json_safe(value.tolist())
        if isinstance(value, np.generic):
            return value.item()
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)
