"""Verified Satellite/Ground Station wire contract and laboratory frames."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import struct
import time
from typing import Any

import numpy as np

SHAPE = (13, 256, 256)
DTYPE = np.dtype("uint16")  # Actual implementations use native endian.
PAYLOAD_BYTES = int(np.prod(SHAPE) * DTYPE.itemsize)


def validate_tile(tile: np.ndarray) -> np.ndarray:
    if not isinstance(tile, np.ndarray):
        raise TypeError("tile must be a NumPy array")
    if tile.shape != SHAPE or tile.dtype != DTYPE:
        raise ValueError(f"expected {SHAPE} uint16; got {tile.shape} {tile.dtype}")
    return np.ascontiguousarray(tile)


def block_hashes(tile: np.ndarray) -> list[str]:
    tile = validate_tile(tile)
    return [
        hashlib.sha256(np.ascontiguousarray(tile[:, y:y+16, x:x+16]).tobytes()).hexdigest()
        for y in range(0, 256, 16) for x in range(0, 256, 16)
    ]


def merkle_root(leaves: list[str]) -> str:
    if len(leaves) != 256:
        raise ValueError("exactly 256 leaves required")
    level = [bytes.fromhex(value) for value in leaves]
    if any(len(value) != 32 for value in level):
        raise ValueError("leaves must be SHA-256 digests")
    while len(level) > 1:
        level = [hashlib.sha256(level[i] + level[i + 1]).digest()
                 for i in range(0, len(level), 2)]
    return level[0].hex()


def canonical_manifest(manifest: dict[str, Any]) -> bytes:
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


@dataclass(frozen=True)
class LabFrame:
    header: dict[str, Any]
    payload: bytes

    def encode(self, *, declared_payload_size: int | None = None) -> bytes:
        header_bytes = json.dumps(self.header, separators=(",", ":")).encode()
        size = len(self.payload) if declared_payload_size is None else declared_payload_size
        return struct.pack(">II", len(header_bytes), size) + header_bytes + self.payload


def build_signed_frame(tile: np.ndarray, private_key: Any, *, tile_id: str,
                       source: str = "RED-TEAM-LAB", counter: int = 1,
                       timestamp: float | None = None, urgency: str = "routine") -> LabFrame:
    """Build a frame using an explicitly supplied authorized laboratory key."""
    tile = validate_tile(tile)
    leaves = block_hashes(tile)
    manifest = {
        "tile_id": tile_id, "source": source, "counter": int(counter),
        "ts": time.time() if timestamp is None else float(timestamp),
        "shape": list(SHAPE), "dtype": "uint16", "root": merkle_root(leaves),
        "urgency": urgency, "deadline_s": 180.0,
    }
    signature = private_key.sign(canonical_manifest(manifest)).hex()
    return LabFrame({"manifest": manifest, "sig": signature, "leaves": leaves},
                    tile.tobytes(order="C"))

