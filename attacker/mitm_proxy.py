"""Authorized lab MITM proxy for the BLACK PIXEL Earth-Observation chain.

Sits between a (cooperating) Satellite PC and the real Ground Station: the
Satellite is pointed at this proxy's IP, the proxy intercepts each length-
prefixed frame, optionally mutates it, forwards it to the real Ground Station,
and relays the reply back. It reports, per intercepted image, the mutation and
the Ground Station's decision.

Authorized lab use only, on machines you own. This is NOT transparent
interception: the sender is explicitly configured to connect here (no ARP
spoofing / packet capture). A tampered frame cannot be re-signed without the
Satellite's private key, so `tamper`/`replay`/`drop` are expected to be caught
by the Ground Station — which is exactly the downlink-integrity property being
demonstrated.

Wire format (from SATELLITE/satellite.py):
    struct.pack('>II', header_len, payload_len) + header_json + payload

Run:
    python mitm_proxy.py                 # uses mitm_config.json
    python mitm_proxy.py --mode observe  # override the mode
Stop with Ctrl+C.
"""
from __future__ import annotations

import argparse
import json
import socket
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODES = ("observe", "tamper", "replay", "drop", "substitute")
LOG_FILE = ROOT / "mitm_log.jsonl"


def log_record(record: dict) -> None:
    """Append one intercepted-frame record to the audit log (never fatal)."""
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except OSError:
        pass


def recv_exact(sock: socket.socket, n: int) -> bytes:
    """Read exactly n bytes or raise if the peer closes early."""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(min(65536, n - len(buf)))
        if not chunk:
            raise ConnectionError(f"peer closed after {len(buf)}/{n} bytes")
        buf.extend(chunk)
    return bytes(buf)


def read_frame(sock: socket.socket) -> tuple[bytes, bytes, dict]:
    """Read one full length-prefixed frame. Returns (header_bytes, payload, manifest)."""
    prefix = recv_exact(sock, 8)
    header_len, payload_len = struct.unpack(">II", prefix)
    header = recv_exact(sock, header_len)
    payload = recv_exact(sock, payload_len)
    try:
        manifest = json.loads(header).get("manifest", {})
    except (json.JSONDecodeError, AttributeError):
        manifest = {}
    return header, payload, manifest


def mutate(mode: str, header: bytes, payload: bytes, cfg: dict) -> tuple[bytes, bytes, bool]:
    """Apply the selected mutation. Returns (header, payload, truncate_flag)."""
    if mode == "tamper":
        off = int(cfg.get("tamper_offset", 1024)) % max(len(payload), 1)
        length = min(int(cfg.get("tamper_length", 64)), len(payload) - off)
        b = bytearray(payload)
        for i in range(off, off + max(length, 1)):
            b[i] ^= 0xFF
        return header, bytes(b), False
    if mode == "drop":
        # forward only half the payload, then the proxy closes -> EOF at GS
        return header, payload[: len(payload) // 2], True
    # observe and replay forward the frame unchanged
    return header, payload, False


def encode_frame(header: bytes, payload: bytes) -> bytes:
    return struct.pack(">II", len(header), len(payload)) + header + payload


def build_substitute_frame(payload: bytes, manifest: dict, cfg: dict) -> tuple[bytes, str, object]:
    """Replace the intercepted image with an attacked, freshly lab-signed copy.

    Takes the sender's real tile out of the intercepted payload, applies a
    BLACK PIXEL attack to it, and re-signs with the Red Team lab key. The
    Ground Station ACCEPTs it only if it trusts that lab key (a key-trust
    compromise); otherwise the invalid signature is quarantined.
    """
    import tempfile
    import time
    import numpy as np
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from red_team.adapters import run_attack
    from red_team.protocol import build_signed_frame

    arr = np.frombuffer(payload, dtype=np.uint16)
    if arr.size != 13 * 256 * 256:
        raise ValueError(f"intercepted payload is {arr.size} uint16, not a 13x256x256 tile")
    arr = arr.reshape(13, 256, 256).copy()

    key_path = Path(cfg["lab_private_key"])
    if not key_path.is_absolute():
        key_path = (ROOT / key_path).resolve()
    key = Ed25519PrivateKey.from_private_bytes(key_path.read_bytes())

    attack = cfg.get("substitute_attack", "cloud_injection")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "intercepted.tif"
        # the attack engine reads rasters, not .npy; write a plain 13-band GeoTIFF.
        # only raw pixels crossed the wire, so prefer band-agnostic attacks here.
        import rasterio
        with rasterio.open(tmp, "w", driver="GTiff", height=256, width=256,
                           count=13, dtype="uint16") as dst:
            dst.write(arr)
        adapted = run_attack(str(tmp), attack=attack)

    frame = build_signed_frame(
        adapted.attacked, key,
        tile_id=f"{manifest.get('tile_id', 'mitm')}-sub",
        source="RED-TEAM-LAB", counter=time.time_ns())
    return frame.encode(), attack, adapted.metadata.get("edited_pixel_count")


def forward_to_gs(frame: bytes, cfg: dict, *, truncate: bool = False) -> dict:
    """Send a frame to the real Ground Station and return its JSON reply."""
    host = cfg["real_ground_station_ip"]
    port = int(cfg["real_ground_station_port"])
    with socket.create_connection((host, port), timeout=float(cfg.get("connect_timeout_s", 10.0))) as gs:
        gs.settimeout(float(cfg.get("socket_timeout_s", 20.0)))
        if truncate:
            gs.sendall(frame)
            gs.shutdown(socket.SHUT_WR)  # signal EOF mid-stream
        else:
            gs.sendall(frame)
        reply = bytearray()
        try:
            while b"\n" not in reply:
                part = gs.recv(65536)
                if not part:
                    break
                reply.extend(part)
                if len(reply) > 1024 * 1024:
                    break
        except (OSError, TimeoutError):
            pass
    if not reply:
        return {"decision": "NO_REPLY", "reason": "Ground Station closed without a response"}
    try:
        return json.loads(reply.split(b"\n", 1)[0])
    except json.JSONDecodeError:
        return {"decision": "UNPARSEABLE", "reason": reply[:120].decode("utf-8", "replace")}


def handle(conn: socket.socket, cfg: dict, mode: str, index: int, peer: str) -> str:
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).isoformat()
    header, payload, manifest = read_frame(conn)
    tile = manifest.get("tile_id", "?")
    record = {"time": ts, "index": index, "from": peer, "tile_id": tile, "mode": mode}

    if mode == "substitute":
        frame, attack, edited = build_substitute_frame(payload, manifest, cfg)
        reply = forward_to_gs(frame, cfg)
        decision = reply.get("decision", reply.get("status", "?"))
        try:
            conn.sendall((json.dumps(reply) + "\n").encode())
        except OSError:
            pass
        record.update({"attack": attack, "edited_px": edited, "decision": decision})
        log_record(record)
        return (f"[intercepted image {index}] {tile:<28} mode=substitute "
                f"attack={attack} edited_px={edited} -> {decision}")

    out_header, out_payload, truncate = mutate(mode, header, payload, cfg)
    frame = encode_frame(out_header, out_payload)

    reply = forward_to_gs(frame, cfg, truncate=truncate)
    decision = reply.get("decision", reply.get("status", "?"))

    if mode == "replay":
        # resend the very same accepted frame; the counter must reject the second
        replay_reply = forward_to_gs(frame, cfg)
        decision = f"{decision} , {replay_reply.get('decision', '?')}"

    # relay the (first) Ground Station reply back to the Satellite
    try:
        conn.sendall((json.dumps(reply) + "\n").encode())
    except OSError:
        pass
    record.update({"decision": decision})
    log_record(record)
    return f"[intercepted image {index}] {tile:<28} mode={mode:<8} -> {decision}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Authorized lab MITM proxy (Satellite -> Ground Station)")
    ap.add_argument("--config", default=str(ROOT / "mitm_config.json"))
    ap.add_argument("--mode", choices=MODES, help="override config mode")
    ap.add_argument("--once", action="store_true", help="handle one frame then exit")
    args = ap.parse_args(argv)

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    mode = args.mode or cfg.get("mode", "observe")
    if mode not in MODES:
        sys.exit(f"unknown mode {mode!r}; choose one of {MODES}")

    bind = (cfg.get("bind_ip", "0.0.0.0"), int(cfg["listen_port"]))
    gs = f"{cfg['real_ground_station_ip']}:{cfg['real_ground_station_port']}"
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # On Windows, SO_REUSEADDR lets a second process co-bind the same port and
    # silently steal connections. Use exclusive binding so a duplicate proxy
    # fails loudly instead of splitting the sender's traffic across instances.
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        srv.bind(bind)
    except OSError as exc:
        srv.close()
        sys.exit(f"[mitm] cannot bind {bind[0]}:{bind[1]} ({exc}). "
                 f"Another proxy is probably already running on this port — "
                 f"stop it first (one proxy at a time).")
    srv.listen(8)
    print(f"[mitm] listening on {bind[0]}:{bind[1]}  ->  real Ground Station {gs}")
    print(f"[mitm] mode={mode}  (point the Satellite's ground_station_ip at THIS proxy)")

    index = 0
    try:
        while True:
            conn, addr = srv.accept()
            index += 1
            with conn:
                conn.settimeout(float(cfg.get("socket_timeout_s", 20.0)))
                try:
                    print(handle(conn, cfg, mode, index, addr[0]), flush=True)
                except (OSError, ConnectionError, struct.error, ValueError) as exc:
                    print(f"[intercepted image {index}] from {addr[0]} -> proxy error: {exc}", flush=True)
            if args.once:
                break
    except KeyboardInterrupt:
        print(f"\n[mitm] stopped. Intercepted {index} frame(s).")
    finally:
        srv.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
