"""Adapters between BLACK PIXEL GeoTIFF results and the verified wire tile."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib

import numpy as np

from black_pixel_agri.engine import Result, run
from black_pixel_agri.raster import read_scene
from .protocol import SHAPE, validate_tile


WIRE_INCOMPATIBLE = {"georeference_shift"}


@dataclass(frozen=True)
class AdaptedAttack:
    original: np.ndarray
    attacked: np.ndarray
    changed_mask: np.ndarray
    selected_mask: np.ndarray
    metadata: dict


def array_sha256(array: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def run_attack(path: str | Path, *, attack: str, seed: int = 42,
               coverage: str = "auto", level: str = "balanced",
               profile: str = "auto", assume_scale: float | None = None) -> AdaptedAttack:
    """Reuse the existing engine, enforcing the real 13x256x256 wire contract."""
    if attack == "clean":
        scene = read_scene(path, source_profile=profile, assume_scale=assume_scale)
        original = validate_tile(scene.pixels)
        empty_mask = np.zeros(SHAPE[1:], dtype=bool)
        digest = array_sha256(original)
        return AdaptedAttack(
            original.copy(), original.copy(), empty_mask.copy(), empty_mask.copy(),
            {
                "requested_attack": "clean", "executed_attack": "clean", "seed": int(seed),
                "wire_compatible": True, "original_array_sha256": digest,
                "attacked_array_sha256": digest, "edited_pixel_count": 0,
            },
        )
    if attack in WIRE_INCOMPATIBLE:
        raise ValueError("georeference_shift changes GeoTIFF metadata, which is absent from the wire protocol")
    result: Result = run(path, attack=attack, seed=seed, coverage=coverage, level=level,
                         profile=profile, assume_scale=assume_scale)
    original = validate_tile(result.scene.pixels)
    attacked = validate_tile(result.output)
    metadata = dict(result.manifest)
    metadata.update({
        "wire_compatible": True,
        "original_array_sha256": array_sha256(original),
        "attacked_array_sha256": array_sha256(attacked),
    })
    return AdaptedAttack(original.copy(), attacked.copy(), result.changed_mask.copy(),
                         result.selected_mask.copy(), metadata)

