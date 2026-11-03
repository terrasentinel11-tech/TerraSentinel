"""Friendly launcher for authorized BLACK PIXEL red-team experiments.

Wraps red_team.cli so you can fire one attack (or a full sweep) with a single
command, against the local lab Ground Station on loopback. All the fixed
plumbing (lab key path, host allowlist, evidence output) is handled here.

Examples
--------
    python launch_attack.py --scenario post_sign_alter --attack cloud_injection
    python launch_attack.py --all
    python launch_attack.py --list
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent            # attacker/
REPO = ROOT.parent                                 # project root
LAB_KEY = REPO / "lab-keys" / "lab_ed25519.key"
DEFAULT_IMAGE = ROOT / "examples" / "synthetic_farms.tif"
EVIDENCE = ROOT / "red_team_evidence"

# Scenario -> what the matrix says the defense SHOULD do.
EXPECTED = {
    "clean": "ACCEPT",
    "pre_sign_attack": "CRYPTO_ACCEPT_SEMANTIC_RESULT_EXTERNAL",
    "post_sign_alter": "QUARANTINE",
    "payload_replacement": "QUARANTINE",
    "manifest_alter": "REJECT_INVALID_SIGNATURE",
    "malformed_header": "REJECT_MALFORMED",
    "invalid_declared_size": "REJECT_MALFORMED",
    "incomplete": "REJECT_MALFORMED_OR_EOF",
    "unexpected_termination": "REJECT_MALFORMED_OR_EOF",
    "replay": "ACCEPT_THEN_REJECT_REPLAY",
    "delayed_transmission": "ACCEPT_OR_TIMEOUT_BY_DELAY",
}


def verdict(scenario: str, expected: str, actual: str) -> str:
    """Decide whether the defender's response counts as a PASS for this attack.

    This is the heart of the launcher: it encodes what "the defense worked"
    actually MEANS for each attack. The mapping is deliberately NOT a plain
    string-equals, because the defender has legitimate alternative responses:

      - `manifest_alter` is expected to be REJECT_INVALID_SIGNATURE, but the
        defender may answer QUARANTINE (quarantine + request retransmission).
        Both mean "the forged signature was caught" -> that is a PASS.
      - any attack scenario where the defender returns ACCEPT on tampered wire
        bytes is a real FAIL (integrity bypass).
      - `pre_sign_attack` returning ACCEPT is correct (crypto can't see a
        compromised source) -> PASS, but flag that only a detector can catch it.

    Return one of: "PASS", "FAIL", "INFO".
    """
    a = (actual or "").upper()
    protective = any(k in a for k in ("QUARANTINE", "REJECT", "SALVAGE", "UNVERIFIED",
                                      "CLOSED", "ERROR", "EOF", "TIMEOUT"))
    if scenario == "clean":
        return "PASS" if a.startswith("ACCEPT") and "REPLAY" not in a else "FAIL"
    if scenario == "replay":
        # must accept once, then reject the resend as a replay
        return "PASS" if a.startswith("ACCEPT") and "REPLAY" in a else "FAIL"
    if scenario == "delayed_transmission":
        return "PASS" if "ACCEPT" in a or "TIMEOUT" in a else "FAIL"
    if scenario == "pre_sign_attack":
        # crypto SHOULD accept a source-compromised tile; only a semantic
        # detector can catch it -> flag as INFO, not a defense failure
        return "INFO" if "ACCEPT" in a else ("PASS" if protective else "FAIL")
    # every remaining scenario is an integrity/transport attack: any protective
    # response is a PASS; accepting tampered or malformed bytes is a real FAIL
    return "PASS" if protective else "FAIL"


def launch(scenario: str, attack: str, image: Path, *, execute: bool = True) -> dict:
    """Run one scenario via red_team.cli and return the parsed JSON record."""
    if not LAB_KEY.exists():
        sys.exit(f"Missing lab key: {LAB_KEY}. Generate a 32-byte Ed25519 key there first.")
    cmd = [
        sys.executable, "-m", "red_team.cli",
        "--image", str(image),
        "--attack", attack,
        "--scenario", scenario,
        "--output", str(EVIDENCE),
    ]
    if execute:
        cmd += ["--execute", "--host", "127.0.0.1", "--port", "9000",
                "--allow-host", "127.0.0.1", "--lab-private-key", str(LAB_KEY)]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"error": "could not parse red_team.cli output",
                "stdout": proc.stdout[-500:], "stderr": proc.stderr[-500:]}


def _decision(record: dict) -> str:
    """Flatten the Ground Station response into a short decision string."""
    r = record.get("response")
    if isinstance(r, list):
        return " , ".join((x.get("decision") or x.get("status", "?")) if isinstance(x, dict) else str(x) for x in r)
    if isinstance(r, dict):
        return r.get("decision") or r.get("status", "?")
    return str(r)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Launch authorized BLACK PIXEL attacks at the lab Ground Station")
    p.add_argument("--scenario", default="post_sign_alter", choices=sorted(EXPECTED))
    p.add_argument("--attack", default="cloud_injection")
    p.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    p.add_argument("--all", action="store_true", help="Run the full scenario sweep")
    p.add_argument("--list", action="store_true", help="List scenarios and exit")
    p.add_argument("--offline", action="store_true", help="Generate frames without sending")
    args = p.parse_args(argv)

    if args.list:
        for s, e in EXPECTED.items():
            print(f"  {s:<24} expect {e}")
        return 0

    scenarios = list(EXPECTED) if args.all else [args.scenario]
    print(f"{'SCENARIO':<24} {'EXPECTED':<40} {'ACTUAL':<26} VERDICT")
    print("-" * 104)
    for scn in scenarios:
        atk = "clean" if scn in ("clean", "replay", "delayed_transmission",
                                 "malformed_header", "invalid_declared_size",
                                 "manifest_alter", "incomplete",
                                 "unexpected_termination") else args.attack
        rec = launch(scn, atk, args.image, execute=not args.offline)
        actual = _decision(rec)
        try:
            v = verdict(scn, EXPECTED[scn], actual)
        except NotImplementedError as exc:
            v = f"(verdict not implemented: {exc})"
        print(f"{scn:<24} {EXPECTED[scn]:<40} {actual[:25]:<26} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
