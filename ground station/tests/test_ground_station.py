from __future__ import annotations

import json
from pathlib import Path
import struct
import unittest

import numpy as np
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ground_station.crypto_protocol import (
    EXPECTED_BANDS,
    EXPECTED_HEIGHT,
    EXPECTED_WIDTH,
    canonical_manifest_bytes,
    compute_block_hashes,
    compute_merkle_root,
    validate_header_structure,
)
from ground_station.defender import DefenderEngine


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "defender_config.json"


def signed_packet(key: Ed25519PrivateKey, tile: np.ndarray, counter: int = 1):
    leaves = compute_block_hashes(tile)
    manifest = {
        "tile_id": "test-tile",
        "source": "pi-test",
        "counter": counter,
        "ts": 1730000000.0,
        "shape": [EXPECTED_BANDS, EXPECTED_HEIGHT, EXPECTED_WIDTH],
        "dtype": "uint16",
        "root": compute_merkle_root(leaves),
        "urgency": "routine",
        "deadline_s": 300.0,
    }
    return (
        {"manifest": manifest, "sig": key.sign(canonical_manifest_bytes(manifest)).hex(), "leaves": leaves},
        tile.tobytes(order="C"),
    )


class GroundStationTests(unittest.TestCase):
    def setUp(self):
        self.key = Ed25519PrivateKey.generate()
        self.tile = np.ones((EXPECTED_BANDS, EXPECTED_HEIGHT, EXPECTED_WIDTH), dtype=np.uint16)

    def test_valid_tile_is_accepted_without_model_or_persistence(self):
        header, payload = signed_packet(self.key, self.tile)
        out = DefenderEngine(CONFIG_PATH, self.key.public_key()).evaluate_tile(
            header, payload, now_ts=1730000000.0
        )
        self.assertEqual(out.decision, "ACCEPT")
        self.assertEqual(out.failed_blocks, [])
        self.assertIsNone(out.trust_score)

    def test_payload_tampering_is_quarantined(self):
        header, payload = signed_packet(self.key, self.tile)
        changed = bytearray(payload)
        changed[0] ^= 1
        out = DefenderEngine(CONFIG_PATH, self.key.public_key()).evaluate_tile(
            header, bytes(changed), now_ts=1730000000.0
        )
        self.assertEqual(out.decision, "QUARANTINE")
        self.assertTrue(out.failed_blocks)
        self.assertGreater(np.count_nonzero(out.pixel_mask), 0)

    def test_replay_is_rejected_in_process_memory(self):
        header, payload = signed_packet(self.key, self.tile)
        engine = DefenderEngine(CONFIG_PATH, self.key.public_key())
        engine.evaluate_tile(header, payload, now_ts=1730000000.0)
        replay = engine.evaluate_tile(header, payload, now_ts=1730000000.0)
        self.assertEqual(replay.decision, "REJECT_REPLAY")

    def test_frame_shape_validation_is_available_to_server(self):
        header, payload = signed_packet(self.key, self.tile)
        raw_header = json.dumps(header, separators=(",", ":")).encode()
        frame = struct.pack(">II", len(raw_header), len(payload)) + raw_header + payload
        self.assertEqual(struct.unpack(">II", frame[:8]), (len(raw_header), len(payload)))
        self.assertEqual(validate_header_structure(header), (True, "OK"))


if __name__ == "__main__":
    unittest.main()
