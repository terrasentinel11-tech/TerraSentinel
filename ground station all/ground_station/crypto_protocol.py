"""Cryptographic and framing protocol utilities for the Ground Station.

Implements canonical manifest JSON serialization, Ed25519 signature verification,
16x16 block SHA-256 hashing, pairwise Merkle root computation, strict type-safe
header validation, and total-deadline TCP framing.
"""

from __future__ import annotations

import hashlib
import json
import math
import socket
import struct
import time
from pathlib import Path
from typing import Any

import numpy as np
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

EXPECTED_BANDS = 13
EXPECTED_HEIGHT = 256
EXPECTED_WIDTH = 256
GRID_ROWS = 16
GRID_COLS = 16
BLOCK_H = 16
BLOCK_W = 16
NUM_BLOCKS = GRID_ROWS * GRID_COLS  # 256
EXPECTED_PAYLOAD_BYTES = EXPECTED_BANDS * EXPECTED_HEIGHT * EXPECTED_WIDTH * 2  # 1,703,936 bytes

REQUIRED_MANIFEST_FIELDS = {
    "tile_id",
    "source",
    "counter",
    "ts",
    "shape",
    "dtype",
    "root",
    "urgency",
    "deadline_s",
}


def canonical_manifest_bytes(manifest: dict[str, Any]) -> bytes:
    """Serialize manifest to canonical JSON bytes (sorted keys, no whitespace)."""
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def load_public_key(pub_key_path: str | Path) -> Ed25519PublicKey:
    """Load a 32-byte raw Ed25519 public key from disk (e.g., pi.key.pub)."""
    raw = Path(pub_key_path).read_bytes()
    if len(raw) != 32:
        raise ValueError(f"Expected 32 raw bytes for Ed25519 public key, got {len(raw)}")
    return Ed25519PublicKey.from_public_bytes(raw)


def verify_manifest_signature(
    manifest: dict[str, Any], sig_hex: str, public_key: Ed25519PublicKey
) -> bool:
    """Verify Ed25519 signature over canonical JSON bytes of the manifest."""
    try:
        if not isinstance(sig_hex, str) or len(sig_hex) != 128:
            return False
        sig_bytes = bytes.fromhex(sig_hex)
        if len(sig_bytes) != 64:
            return False
        msg = canonical_manifest_bytes(manifest)
        public_key.verify(sig_bytes, msg)
        return True
    except (ValueError, TypeError, InvalidSignature):
        return False


def compute_block_hashes(tile: np.ndarray) -> list[str]:
    """Compute 256 SHA-256 hex digests for a 16x16 grid of (13, 16, 16) blocks."""
    if tile.shape != (EXPECTED_BANDS, EXPECTED_HEIGHT, EXPECTED_WIDTH) or tile.dtype != np.uint16:
        raise ValueError(f"Invalid tile shape {tile.shape} or dtype {tile.dtype}")
    leaves: list[str] = []
    for r in range(GRID_ROWS):
        r0, r1 = r * BLOCK_H, (r + 1) * BLOCK_H
        for c in range(GRID_COLS):
            c0, c1 = c * BLOCK_W, (c + 1) * BLOCK_W
            block_bytes = np.ascontiguousarray(tile[:, r0:r1, c0:c1], dtype=np.uint16).tobytes(order="C")
            leaves.append(hashlib.sha256(block_bytes).hexdigest())
    return leaves


def compute_merkle_root(leaves_hex: list[str]) -> str:
    """Compute pairwise SHA-256 Merkle root over hex leaf hashes, duplicating last node when odd."""
    if not isinstance(leaves_hex, list) or not leaves_hex:
        raise ValueError("Cannot compute Merkle root of empty or non-list leaves")
    try:
        level = [bytes.fromhex(h) for h in leaves_hex]
    except (ValueError, TypeError) as exc:
        raise ValueError("Malformed hex string in leaves") from exc
    if any(len(node) != 32 for node in level):
        raise ValueError("All leaf hashes must be 32-byte SHA-256 digests")

    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        next_level: list[bytes] = []
        for i in range(0, len(level), 2):
            combined = hashlib.sha256(level[i] + level[i + 1]).digest()
            next_level.append(combined)
        level = next_level
    return level[0].hex()


def compare_blocks_and_build_masks(
    computed_leaves: list[str], header_leaves: list[str]
) -> tuple[list[int], np.ndarray, np.ndarray]:
    """Compare recomputed block hashes against header leaves."""
    failed_indices: list[int] = []
    tamper_map = np.zeros((GRID_ROWS, GRID_COLS), dtype=np.uint8)
    for idx, (comp_h, hdr_h) in enumerate(zip(computed_leaves, header_leaves)):
        if comp_h.lower() != hdr_h.lower():
            failed_indices.append(idx)
            r, c = divmod(idx, GRID_COLS)
            tamper_map[r, c] = 1

    pixel_mask = np.repeat(np.repeat(tamper_map.astype(bool), BLOCK_H, axis=0), BLOCK_W, axis=1)
    return failed_indices, tamper_map, pixel_mask


def _is_valid_hex(s: str, expected_len: int) -> bool:
    if not isinstance(s, str) or len(s) != expected_len:
        return False
    try:
        bytes.fromhex(s)
        return True
    except ValueError:
        return False


def validate_header_structure(header: Any) -> tuple[bool, str]:
    """Strictly validate untrusted parsed JSON header without raising TypeError/KeyError."""
    if not isinstance(header, dict):
        return False, "Header must be a JSON object"
    if not {"manifest", "sig", "leaves"}.issubset(header.keys()):
        return False, "Header missing 'manifest', 'sig', or 'leaves'"

    manifest = header.get("manifest")
    sig = header.get("sig")
    leaves = header.get("leaves")

    if not isinstance(manifest, dict):
        return False, "Manifest must be a JSON object"
    if not REQUIRED_MANIFEST_FIELDS.issubset(manifest.keys()):
        return False, "Manifest missing required fields"
    if not _is_valid_hex(sig, 128):
        return False, "Signature must be a 128-character valid hex string"
    if not isinstance(leaves, list) or len(leaves) != NUM_BLOCKS:
        return False, f"Leaves must be a list of {NUM_BLOCKS} hex strings"
    if not all(_is_valid_hex(x, 64) for x in leaves):
        return False, "Each leaf must be a 64-character valid SHA-256 hex string"

    tile_id = manifest.get("tile_id")
    source = manifest.get("source")
    counter = manifest.get("counter")
    ts = manifest.get("ts")
    shape = manifest.get("shape")
    dtype = manifest.get("dtype")
    root = manifest.get("root")
    urgency = manifest.get("urgency")
    deadline_s = manifest.get("deadline_s")

    if not isinstance(tile_id, str) or not tile_id.strip() or len(tile_id) > 128:
        return False, "Invalid tile_id"
    if not isinstance(source, str) or not source.strip() or len(source) > 128:
        return False, "Invalid source"
    if not isinstance(counter, int) or isinstance(counter, bool) or counter < 0:
        return False, "Counter must be a non-negative integer"
    if (
        not isinstance(ts, (int, float))
        or isinstance(ts, bool)
        or not math.isfinite(float(ts))
    ):
        return False, "Timestamp must be a finite number"
    if not isinstance(shape, list) or shape != [EXPECTED_BANDS, EXPECTED_HEIGHT, EXPECTED_WIDTH]:
        return False, f"Unsupported shape: {shape}"
    if dtype != "uint16":
        return False, f"Unsupported dtype: {dtype}"
    if not _is_valid_hex(root, 64):
        return False, "Manifest root must be a 64-char valid hex string"
    if urgency not in ("routine", "urgent"):
        return False, f"Invalid urgency: {urgency}"
    if (
        not isinstance(deadline_s, (int, float))
        or isinstance(deadline_s, bool)
        or not math.isfinite(float(deadline_s))
        or float(deadline_s) < 0.0
    ):
        return False, "deadline_s must be a non-negative finite number"

    return True, "OK"


def recv_exact(
    sock: socket.socket,
    num_bytes: int,
    deadline_mono: float | None = None,
    per_read_timeout_s: float = 5.0,
) -> bytes:
    """Read exactly num_bytes while enforcing both a per-read timeout and a total connection deadline."""
    chunks: list[bytes] = []
    bytes_recd = 0
    while bytes_recd < num_bytes:
        if deadline_mono is not None:
            remaining_time = deadline_mono - time.monotonic()
            if remaining_time <= 0.0:
                raise TimeoutError("Total connection deadline exceeded (slow-loris protection)")
            sock.settimeout(min(per_read_timeout_s, remaining_time))
        else:
            sock.settimeout(per_read_timeout_s)

        chunk = sock.recv(min(num_bytes - bytes_recd, 65536))
        if not chunk:
            raise EOFError(f"Connection closed after {bytes_recd}/{num_bytes} bytes")
        chunks.append(chunk)
        bytes_recd += len(chunk)
    return b"".join(chunks)


def read_framed_message(
    sock: socket.socket,
    max_header_bytes: int,
    max_payload_bytes: int,
    *,
    connection_deadline_s: float = 10.0,
    per_read_timeout_s: float = 5.0,
) -> tuple[dict[str, Any], bytes]:
    """Safely read a framed tile message with strict size limits and total wall-clock deadline."""
    deadline_mono = time.monotonic() + connection_deadline_s

    prefix = recv_exact(
        sock, 8, deadline_mono=deadline_mono, per_read_timeout_s=per_read_timeout_s
    )
    header_len, payload_len = struct.unpack(">II", prefix)

    if header_len == 0 or header_len > max_header_bytes:
        raise ValueError(f"Header length {header_len} out of bounds (max {max_header_bytes})")
    if payload_len != EXPECTED_PAYLOAD_BYTES or payload_len > max_payload_bytes:
        raise ValueError(
            f"Payload length {payload_len} invalid (expected {EXPECTED_PAYLOAD_BYTES}, max {max_payload_bytes})"
        )

    header_bytes = recv_exact(
        sock, header_len, deadline_mono=deadline_mono, per_read_timeout_s=per_read_timeout_s
    )
    payload_bytes = recv_exact(
        sock, payload_len, deadline_mono=deadline_mono, per_read_timeout_s=per_read_timeout_s
    )

    try:
        header_obj = json.loads(header_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Malformed UTF-8 or JSON in header") from exc

    return header_obj, payload_bytes
