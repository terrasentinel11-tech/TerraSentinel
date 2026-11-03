"""Read metrics emitted by the trained model; this script never creates metrics."""

from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model-metrics",
        type=Path,
        required=True,
        help="JSON or CSV metrics file produced by the detector model",
    )
    args = parser.parse_args()
    if not args.model_metrics.is_file():
        raise FileNotFoundError(f"Model metrics not found: {args.model_metrics}")
    if args.model_metrics.suffix.lower() == ".json":
        metrics = json.loads(args.model_metrics.read_text(encoding="utf-8"))
    else:
        metrics = args.model_metrics.read_text(encoding="utf-8")
    print(json.dumps(metrics, indent=2) if not isinstance(metrics, str) else metrics)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
