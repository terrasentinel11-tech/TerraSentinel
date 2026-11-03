"""Small, reproducible orchestration layer for attack experiments."""

import json
from pathlib import Path
from typing import Any

from .black_pixel_agri.engine import run
from .black_pixel_agri.raster import export_tiff
from .black_pixel_agri.visuals import preview


def run_attack(
    input_path: str | Path,
    output_dir: str | Path,
    *,
    attack: str = "cloud_injection",
    coverage: str = "auto",
    level: str = "balanced",
    seed: int = 42,
    profile: str = "auto",
    assume_scale: float | None = None,
) -> dict[str, Any]:
    """Create one attack copy, preview, and manifest in ``output_dir``."""
    result = run(
        input_path,
        attack=attack,
        coverage=coverage,
        level=level,
        seed=seed,
        profile=profile,
        assume_scale=assume_scale,
    )
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    attacked_path = destination / "attacked.tif"
    preview_path = destination / "preview.png"
    manifest_path = destination / "manifest.json"
    export_tiff(result.scene, attacked_path, result.output, transform=result.geo_transform)
    preview(result, preview_path)
    manifest_path.write_text(json.dumps(result.manifest, indent=2), encoding="utf-8")
    return {
        "attack": result.attack,
        "coverage": result.coverage,
        "level": result.level,
        "attacked_path": str(attacked_path),
        "preview_path": str(preview_path),
        "manifest_path": str(manifest_path),
        "changed_pixels": result.manifest["edited_pixel_count"],
        "changed_fraction": result.manifest["edited_fraction"],
    }


__all__ = ["run_attack"]
