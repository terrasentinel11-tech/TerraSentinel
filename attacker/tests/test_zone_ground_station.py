from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from red_team.protocol import SHAPE, build_signed_frame

GROUND_ROOT = Path(__file__).resolve().parents[2] / "ground station all"
sys.path.insert(0, str(GROUND_ROOT))
from ground_station.crypto_protocol import validate_header_structure, verify_manifest_signature  # noqa: E402

def test_real_ground_station_contract_accepts_lab_header_structure():
    key = Ed25519PrivateKey.generate()
    frame = build_signed_frame(np.zeros(SHAPE, dtype=np.uint16), key, tile_id="lab", timestamp=1)
    assert validate_header_structure(frame.header) == (True, "OK")
    assert verify_manifest_signature(frame.header["manifest"], frame.header["sig"], key.public_key())

def test_real_ground_station_rejects_wrong_shape_and_type_metadata():
    key = Ed25519PrivateKey.generate()
    frame = build_signed_frame(np.zeros(SHAPE, dtype=np.uint16), key, tile_id="lab", timestamp=1)
    for field, bad in (("shape", [3, 256, 256]), ("dtype", "float32")):
        header = {**frame.header, "manifest": {**frame.header["manifest"], field: bad}}
        valid, _ = validate_header_structure(header)
        assert not valid
