"""Persistent authorized attacker for the BLACK PIXEL lab.

Waits for the defender team's Ground Station to come online, then attacks every
image placed in the watch folder (acting as a compromised source) and reports,
per image, the attack used and the Ground Station's decision.

It does NOT intercept the team's legitimate traffic; interception/MITM is out of
scope. It sends its own attacked copies to the configured Ground Station IP.

Run:
    python attack_daemon.py                 # uses attacker_config.json
    python attack_daemon.py --once          # one pass over the folder, then exit
Stop with Ctrl+C.
"""
from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

from launch_attack import verdict, _decision, EXPECTED

ROOT = Path(__file__).resolve().parent
IMAGE_SUFFIXES = (".tif", ".tiff", ".npy")


def choose_attack(index: int, image_name: str, attacks: list[str]) -> str:
    """Pick which attack to apply to the index-th image.

    This is the attacker's policy knob. The default is round-robin over the
    configured `attacks` list, so a batch exercises several transformations.
    Swap in your own strategy (always one attack, random, by-filename, ...).
    """
    return attacks[index % len(attacks)]


def wait_for_server(host: str, port: int, poll_s: float) -> None:
    print(f"[daemon] waiting for Ground Station at {host}:{port} ...", flush=True)
    while True:
        with socket.socket() as s:
            s.settimeout(2)
            if s.connect_ex((host, port)) == 0:
                print(f"[daemon] Ground Station is UP at {host}:{port}", flush=True)
                return
        time.sleep(poll_s)


def send_attack(image: Path, attack: str, cfg: dict) -> dict:
    """Attack one image and transmit it to the Ground Station via red_team.cli."""
    cmd = [
        sys.executable, "-m", "red_team.cli",
        "--image", str(image),
        "--attack", attack,
        "--scenario", cfg["scenario"],
        "--execute",
        "--host", cfg["ground_station_ip"],
        "--port", str(cfg["ground_station_port"]),
        "--allow-host", cfg["ground_station_ip"],
        "--allow-host", "127.0.0.1",
        "--lab-private-key", cfg["lab_private_key"],
        "--output", "red_team_evidence",
    ]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"error": "red_team.cli failed", "stderr": proc.stderr[-300:]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Persistent BLACK PIXEL lab attacker")
    ap.add_argument("--config", default=str(ROOT / "attacker_config.json"))
    ap.add_argument("--once", action="store_true", help="One pass over the folder, then exit")
    args = ap.parse_args(argv)

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    folder = (ROOT / cfg["watch_folder"]).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    attacks = cfg["attacks"]
    scenario = cfg["scenario"]

    print(f"[daemon] attacker_ip={cfg['attacker_ip']}  target={cfg['ground_station_ip']}:{cfg['ground_station_port']}")
    print(f"[daemon] scenario={scenario}  attacks={attacks}")
    print(f"[daemon] drop 13x256x256 uint16 .tif/.npy images into: {folder}")

    if cfg.get("wait_for_server", True):
        wait_for_server(cfg["ground_station_ip"], int(cfg["ground_station_port"]),
                        float(cfg.get("poll_interval_s", 3.0)))

    processed: set[str] = set()
    count = 0
    try:
        while True:
            new = sorted(p for p in folder.rglob("*")
                         if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
                         and str(p) not in processed)
            for p in new:
                attack = choose_attack(count, p.name, attacks)
                rec = send_attack(p, attack, cfg)
                decision = _decision(rec)
                v = verdict(scenario, EXPECTED.get(scenario, "?"), decision)
                count += 1
                print(f"[attack image {count}] {p.name:<28} attack={attack:<20} "
                      f"-> {decision:<24} [{v}]", flush=True)
                processed.add(str(p))
            if args.once:
                break
            time.sleep(float(cfg.get("poll_interval_s", 3.0)))
    except KeyboardInterrupt:
        print(f"\n[daemon] stopped. Attacked {count} image(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
