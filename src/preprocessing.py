"""Input discovery and scene loading for the research pipeline."""

from pathlib import Path

from .black_pixel_agri.dataset import discover
from .black_pixel_agri.raster import Scene, read_scene


def load_scene(
    path: str | Path,
    *,
    profile: str = "auto",
    assume_scale: float | None = None,
) -> Scene:
    """Load one GeoTIFF without modifying the source file."""
    return read_scene(path, source_profile=profile, assume_scale=assume_scale)


__all__ = ["Scene", "discover", "load_scene"]
