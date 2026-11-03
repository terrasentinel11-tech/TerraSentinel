from __future__ import annotations
import importlib.util
from pathlib import Path
import numpy as np
import pytest

SATELLITE_FILE = Path(__file__).resolve().parents[2] / "SATELLITE" / "satellite.py"
spec = importlib.util.spec_from_file_location("original_satellite", SATELLITE_FILE)
satellite = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(satellite)

def test_real_satellite_accepts_only_exact_wire_tile(tmp_path):
    valid = np.zeros((13, 256, 256), dtype=np.uint16)
    path = tmp_path / "valid.npy"; np.save(path, valid, allow_pickle=False)
    assert np.array_equal(satellite.read_image(path), valid)

@pytest.mark.parametrize("shape,dtype", [((3, 256, 256), np.uint16), ((13, 128, 128), np.uint16),
                                          ((13, 256, 256), np.float32)])
def test_real_satellite_rejects_invalid_shape_or_type(tmp_path, shape, dtype):
    path = tmp_path / "invalid.npy"; np.save(path, np.zeros(shape, dtype=dtype), allow_pickle=False)
    with pytest.raises(ValueError, match="expected 13x256x256 uint16"):
        satellite.read_image(path)

def test_real_satellite_disables_pickle_loading(tmp_path):
    path = tmp_path / "objects.npy"; np.save(path, np.array([{"unsafe": True}], dtype=object))
    with pytest.raises(ValueError, match="Object arrays cannot be loaded"):
        satellite.read_image(path)
