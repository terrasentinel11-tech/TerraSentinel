"""Atomic, reproducible experiment evidence writer."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from typing import Any

import numpy as np


def experiment_id() -> str:
    return datetime.now(timezone.utc).strftime("bp-%Y%m%dT%H%M%S.%fZ")


def write_bundle(root: str | Path, record: dict[str, Any], *,
                 changed_mask: np.ndarray | None = None,
                 original: np.ndarray | None = None,
                 attacked: np.ndarray | None = None) -> Path:
    eid = str(record["experiment_id"])
    target = Path(root) / eid
    target.mkdir(parents=True, exist_ok=False)
    if changed_mask is not None:
        if changed_mask.shape != (256, 256) or changed_mask.dtype != bool:
            raise ValueError("changed mask must be (256,256) bool")
        np.save(target / "actual_change_mask.npy", changed_mask, allow_pickle=False)
    for name, value in (("original_tile.npy", original), ("attacked_tile.npy", attacked)):
        if value is not None:
            if value.shape != (13, 256, 256) or value.dtype != np.uint16:
                raise ValueError("evidence tiles must be (13,256,256) uint16")
            np.save(target / name, value, allow_pickle=False)
    enriched = dict(record)
    enriched.setdefault("recorded_at", datetime.now(timezone.utc).isoformat())
    enriched["schema_version"] = "black-pixel-red-team/1"
    fd, tmp = tempfile.mkstemp(prefix=".report-", suffix=".json", dir=target)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(enriched, handle, indent=2, sort_keys=True)
            handle.flush(); os.fsync(handle.fileno())
        os.replace(tmp, target / "report.json")
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise
    return target

