"""Reproduce the documented standard, authorized offline attack."""

from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pipeline import run_attack


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Input GeoTIFF copy")
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "standard_attack")
    parser.add_argument("--attack", default="cloud_injection")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    result = run_attack(args.input, args.output, attack=args.attack, seed=args.seed)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
