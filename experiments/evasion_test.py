"""Run a bounded attack-family compatibility check on an input copy."""

from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.black_pixel_agri.attacks import ATTACKS
from src.black_pixel_agri.engine import compatible_attacks
from src.preprocessing import load_scene


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    scene = load_scene(args.input)
    print(json.dumps(compatible_attacks(scene), indent=2))
    print(f"Known attack definitions: {len(ATTACKS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
