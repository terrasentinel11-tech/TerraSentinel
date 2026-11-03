import numpy as np
import pytest

from ground_station.detector import EmbeddedDetector


def test_missing_detector_model_is_reported(tmp_path):
    with pytest.raises(FileNotFoundError):
        EmbeddedDetector(tmp_path / "missing.joblib")


def test_detector_json_safe_converts_numpy_values():
    converted = EmbeddedDetector._json_safe({"value": np.int64(3), "array": np.array([1, 2])})
    assert converted == {"value": 3, "array": [1, 2]}
