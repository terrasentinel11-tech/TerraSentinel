"""BLACK PIXEL AGRI: offline synthetic Earth-observation integrity experiments."""
from .engine import run, compatible_attacks, ATTACKS, SEVERITIES
from .raster import read_scene, Scene
__version__ = "3.0.0a1"
