"""Command-line controller for authorized BLACK PIXEL lab experiments."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from black_pixel_agri.attacks import ATTACKS
from .adapters import WIRE_INCOMPATIBLE, run_attack
from .evidence import experiment_id, write_bundle
from .protocol import build_signed_frame
from .scenarios import SCENARIOS, prepare_scenario
from .transport import transmit
from .zones import ZONE_SCENARIOS, describe


def _git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _lab_key(path: str | None, *, executing: bool):
    if path is None:
        if executing:
            raise ValueError("--lab-private-key is required with --execute; provision its public key on the lab receiver")
        return Ed25519PrivateKey.generate()
    key_path = Path(path).resolve()
    if "satellite" in {part.lower() for part in key_path.parts}:
        raise ValueError("refusing to read a key from the Satellite source tree; use a dedicated lab key")
    raw = key_path.read_bytes()
    if len(raw) != 32:
        raise ValueError("laboratory Ed25519 private key must contain exactly 32 raw bytes")
    return Ed25519PrivateKey.from_private_bytes(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="BLACK PIXEL authorized Red Team laboratory")
    parser.add_argument("--image", required=True)
    parser.add_argument("--attack", required=True, choices=["clean", *sorted(ATTACKS)])
    parser.add_argument("--scenario", default="pre_sign_attack", choices=sorted(SCENARIOS))
    parser.add_argument("--zone", default="ground_station", choices=sorted(ZONE_SCENARIOS))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--profile", default="auto", choices=["auto", "eurosat", "sen12ms-cr"])
    parser.add_argument("--assume-scale", type=float)
    parser.add_argument("--coverage", default="auto")
    parser.add_argument("--level", default="balanced")
    parser.add_argument("--output", default="red_team_evidence")
    parser.add_argument("--execute", action="store_true", help="Send to an allowlisted lab receiver")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--allow-host", action="append", default=[])
    parser.add_argument("--lab-private-key", help="Dedicated 32-byte raw Ed25519 laboratory key")
    parser.add_argument("--delay-seconds", type=float, default=1.0)
    args = parser.parse_args(argv)
    zone = describe(args.zone, args.scenario, executing=args.execute)

    started = time.perf_counter()
    adapted = run_attack(args.image, attack=args.attack, seed=args.seed,
                         profile=args.profile, assume_scale=args.assume_scale,
                         coverage=args.coverage, level=args.level)
    # Ephemeral key: never reads the Satellite private key. For a real receiver, provision
    # this public key as the dedicated authorized lab identity.
    key = _lab_key(args.lab_private_key, executing=args.execute)
    tile = adapted.attacked if args.scenario == "pre_sign_attack" else adapted.original
    eid = experiment_id()
    frame = build_signed_frame(tile, key, tile_id=eid, counter=time.time_ns())
    # For the replacement experiment, preserve the clean signed envelope while
    # placing the selected BLACK PIXEL output on the wire. This reuses the
    # original attack engine and tests the post-sign integrity boundary.
    if args.scenario == "payload_replacement" and args.attack != "clean":
        from .protocol import LabFrame
        wire = LabFrame(frame.header, adapted.attacked.tobytes(order="C")).encode()
    else:
        wire = prepare_scenario(args.scenario, frame)
    response = None
    if args.execute:
        allowed = set(args.allow_host)
        try:
            if args.scenario == "replay":
                response = [transmit(wire, host=args.host, port=args.port, allow_hosts=allowed),
                            transmit(wire, host=args.host, port=args.port, allow_hosts=allowed)]
            else:
                close_after = (len(wire) if args.scenario == "incomplete" else
                               len(wire) // 2 if args.scenario == "unexpected_termination" else None)
                response = transmit(
                    wire, host=args.host, port=args.port, allow_hosts=allowed,
                    delay_s=args.delay_seconds if args.scenario == "delayed_transmission" else 0.0,
                    close_after=close_after,
                )
        except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            response = {"status": "client_error", "error_type": type(exc).__name__, "reason": str(exc)}
    expected = SCENARIOS[args.scenario].expected
    record = {
        "experiment_id": eid, "attack_zone": zone.zone, "target_component": zone.target,
        "attack_position": zone.attack_position, "prerequisites": list(zone.prerequisites),
        "git_commit": _git_commit(), "attack": args.attack, "seed": args.seed,
        "parameters": {"coverage": args.coverage, "level": args.level,
                       "profile": args.profile, "assume_scale": args.assume_scale},
        "scenario": args.scenario, "expected_result": expected,
        "actual_ground_station_response": response,
        "actual_result": "frame_generated_not_executed" if response is None else response,
        "execution_mode": "controlled_tcp" if args.execute else "offline_frame_generation",
        "attack_metadata": adapted.metadata,
        "runtime_ms": round((time.perf_counter() - started) * 1000, 3),
        "wire_bytes": len(wire),
        "signed_tile": "attacked" if args.scenario == "pre_sign_attack" else "original",
        "image_attack_applied_to_signed_tile": args.scenario == "pre_sign_attack" and args.attack != "clean",
        "signed_payload_sha256": hashlib.sha256(frame.payload).hexdigest(),
        "prepared_wire_sha256": hashlib.sha256(wire).hexdigest(),
        "defense_status": ("not_executed" if response is None else
                           "replay_sequence_recorded" if isinstance(response, list) else
                           response.get("decision", "undetermined")),
        "cryptographic_integrity_result": "not_executed" if response is None else response,
        "semantic_detection_result": ("not_configured_or_not_reported" if response is None else
                                      (response.get("detector", "not_configured_or_not_reported")
                                       if isinstance(response, dict) else "not_reported")),
    }
    destination = write_bundle(args.output, record, changed_mask=adapted.changed_mask,
                               original=adapted.original, attacked=adapted.attacked)
    print(json.dumps({"experiment_id": eid, "evidence": str(destination),
                      "expected": expected, "response": response}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

