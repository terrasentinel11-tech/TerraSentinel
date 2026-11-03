"""Stateless TCP ground-station receiver with Defender and optional Detector."""

from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
import json
import socket
import ssl
import threading
import time
from urllib import request
from pathlib import Path
import re
from typing import Any

import numpy as np
import rasterio

from ground_station.crypto_protocol import (
    load_public_key,
    read_framed_message,
    validate_header_structure,
)
from ground_station.defender import DefenderEngine
from ground_station.detector import EmbeddedDetector


class GroundStationServer:
    """Concurrent TCP receiver that returns defender results to the dashboard."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        config_path: str | Path,
        pub_key_path: str | Path,
        next_contact_s: float | None = None,
        detector_url: str | None = None,
        detector_model_path: str | Path | None = None,
        detector_timeout_s: float = 3.0,
        detector_token: str | None = None,
        detector_include_quarantine: bool = False,
        allow_insecure_detector: bool = False,
        state_path: str | Path | None = None,
        output_dir: str | Path | None = None,
        tls_context: ssl.SSLContext | None = None,
        now_ts_fn: Any = time.time,
    ) -> None:
        self.host = host
        self.port = port
        self.config = json.loads(Path(config_path).read_text(encoding="utf-8"))
        self.max_header_bytes = int(self.config.get("max_header_bytes", 65536))
        self.max_payload_bytes = int(self.config.get("max_payload_bytes", 2097152))
        self.socket_timeout_s = float(self.config.get("socket_timeout_s", 5.0))
        self.connection_deadline_s = float(self.config.get("connection_deadline_s", 10.0))
        self.max_concurrent_connections = int(self.config.get("max_concurrent_connections", 8))
        self.next_contact_s = next_contact_s
        self.detector_url = detector_url
        self.detector = EmbeddedDetector(detector_model_path) if detector_model_path else None
        self.detector_timeout_s = detector_timeout_s
        self.detector_token = detector_token
        self.detector_include_quarantine = detector_include_quarantine
        if detector_url and detector_url.startswith("http://") and not allow_insecure_detector:
            raise ValueError("Detector URL must use HTTPS unless insecure mode is explicitly enabled")
        self.tls_context = tls_context
        self.output_dir = Path(output_dir) if output_dir else None
        self._output_lock = threading.Lock()
        if self.output_dir is not None:
            (self.output_dir / "accepted").mkdir(parents=True, exist_ok=True)
            (self.output_dir / "quarantine").mkdir(parents=True, exist_ok=True)
        self.now_ts_fn = now_ts_fn
        self.engine = DefenderEngine(config_path, load_public_key(pub_key_path), state_path)
        self._state_lock = threading.Lock()
        self._conn_semaphore = threading.BoundedSemaphore(self.max_concurrent_connections)

    def handle_connection(self, conn: socket.socket) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            header, payload = read_framed_message(
                conn,
                max_header_bytes=self.max_header_bytes,
                max_payload_bytes=self.max_payload_bytes,
                connection_deadline_s=self.connection_deadline_s,
                per_read_timeout_s=self.socket_timeout_s,
            )
            valid, error = validate_header_structure(header)
            if not valid:
                return self._send_error(conn, error, started)
            with self._state_lock:
                outcome = self.engine.evaluate_tile(
                    header, payload, next_contact_s=self.next_contact_s, now_ts=self.now_ts_fn()
                )
            saved_image = self._save_received_image(outcome, payload)
            latency_ms = round((time.perf_counter() - started) * 1000.0, 3)
            reply = {
                "status": "ok",
                "verification_layer": "ground_station_defender",
                "tile_id": outcome.tile_id,
                "source": outcome.source,
                "decision": outcome.decision,
                "action": outcome.action,
                "reason": outcome.reason,
                "sig_valid": outcome.sig_valid,
                "counter_valid": outcome.counter_valid,
                "failed_blocks": outcome.failed_blocks,
                "tampered_pixel_count": int(np.count_nonzero(outcome.pixel_mask)),
                "retransmit_requested": outcome.retransmit_requested,
                "stale_fallback_used": outcome.stale_fallback_used,
                "revocation_recommended": outcome.revocation_recommended,
                "latency_ms": latency_ms,
                "released_tile_shape": list(outcome.released_tile.shape),
                "released_tile_dtype": str(outcome.released_tile.dtype),
            }
            if saved_image is not None:
                reply["saved_image"] = saved_image
            if (self.detector or self.detector_url) and (
                outcome.released_tile.size
                or self.detector_include_quarantine
                or self.detector is not None
            ):
                reply["detector"] = self._run_detector(
                    outcome,
                    reply,
                    payload if not outcome.released_tile.size else None,
                )
            elif self.detector or self.detector_url:
                reply["detector"] = {
                    "status": "skipped",
                    "reason": "No verified tile was released to the detector",
                }
            self._record_response(reply)
            conn.sendall((json.dumps(reply, separators=(",", ":")) + "\n").encode("utf-8"))
            print(f"{outcome.tile_id} | {outcome.decision} | {outcome.reason}", flush=True)
            return reply
        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
            TimeoutError,
            UnicodeError,
            json.JSONDecodeError,
        ) as exc:
            return self._send_error(conn, str(exc), started)

    def _record_response(self, reply: dict[str, Any]) -> None:
        if self.output_dir is None:
            return
        log_path = self.output_dir / "responses.jsonl"
        line = json.dumps(reply, separators=(",", ":"), ensure_ascii=True)
        with self._output_lock:
            with log_path.open("a", encoding="utf-8") as log:
                log.write(line + "\n")

    def _save_received_image(self, outcome: Any, payload: bytes) -> str | None:
        if self.output_dir is None:
            return None

        safe_tile_id = re.sub(r"[^A-Za-z0-9._-]+", "_", outcome.tile_id)[:128] or "tile"
        if outcome.decision == "ACCEPT" and outcome.released_tile.size:
            directory = self.output_dir / "accepted"
            tile = outcome.released_tile
        else:
            directory = self.output_dir / "quarantine"
            tile = np.frombuffer(payload, dtype=np.uint16).reshape((13, 256, 256))

        path = directory / f"{safe_tile_id}.tif"
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            height=256,
            width=256,
            count=13,
            dtype="uint16",
        ) as dst:
            dst.write(np.ascontiguousarray(tile, dtype=np.uint16))
        return str(path)

    def _run_detector(
        self,
        outcome: Any,
        defender_reply: dict[str, Any],
        quarantined_payload: bytes | None = None,
    ) -> dict[str, Any]:
        """Run the detector on a released tile or explicitly labelled forensic tile."""
        trusted = outcome.released_tile.size > 0
        tile_bytes = (
            outcome.released_tile.tobytes(order="C")
            if trusted
            else quarantined_payload
        )
        if tile_bytes is None:
            return {"status": "skipped", "reason": "No tile available for detector analysis"}
        tile = np.frombuffer(tile_bytes, dtype=np.uint16).reshape((13, 256, 256))
        if self.detector is not None:
            try:
                return self.detector.analyze(
                    tile, trusted=trusted, analysis_only=not trusted
                )
            except (OSError, ValueError, TypeError, RuntimeError) as exc:
                return {"status": "error", "reason": f"Embedded detector failed: {exc}"}
        if self.detector_url is None:
            return {"status": "error", "reason": "No detector configured"}
        body = {
            "tile_id": outcome.tile_id,
            "source": outcome.source,
            "shape": [13, 256, 256],
            "dtype": "uint16",
            "tile_base64": base64.b64encode(tile_bytes).decode("ascii"),
            "trusted": trusted,
            "analysis_only": not trusted,
            "defender": {
                "decision": defender_reply["decision"],
                "failed_blocks": defender_reply["failed_blocks"],
                "tampered_pixel_count": defender_reply["tampered_pixel_count"],
            },
        }
        req = request.Request(
            self.detector_url,
            data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                **(
                    {"Authorization": f"Bearer {self.detector_token}"}
                    if self.detector_token
                    else {}
                ),
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.detector_timeout_s) as response:
                result = json.loads(response.read(262144).decode("utf-8"))
            if not isinstance(result, dict):
                return {"status": "error", "reason": "Detector response must be a JSON object"}
            return {"status": "ok", "result": result}
        except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            return {"status": "error", "reason": f"Detector unavailable: {exc}"}

    def _send_error(self, conn: socket.socket, reason: str, started: float) -> dict[str, Any]:
        reply = {
            "status": "error",
            "decision": "REJECT_MALFORMED",
            "reason": reason,
            "retransmit_requested": False,
            "latency_ms": round((time.perf_counter() - started) * 1000.0, 3),
        }
        try:
            conn.sendall((json.dumps(reply, separators=(",", ":")) + "\n").encode("utf-8"))
        except OSError:
            pass
        self._record_response(reply)
        return reply

    def _worker_task(self, conn: socket.socket) -> None:
        try:
            with conn:
                self.handle_connection(conn)
        finally:
            self._conn_semaphore.release()

    def serve_forever(self, max_tiles: int | None = None) -> None:
        accepted = 0
        with ThreadPoolExecutor(max_workers=self.max_concurrent_connections) as pool:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
                server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server.bind((self.host, self.port))
                server.listen(32)
                print(f"Ground station listening on {self.host}:{self.port}", flush=True)
                while max_tiles is None or accepted < max_tiles:
                    conn, _ = server.accept()
                    if self.tls_context is not None:
                        conn = self.tls_context.wrap_socket(conn, server_side=True)
                    if not self._conn_semaphore.acquire(timeout=0.5):
                        with conn:
                            self._send_error(conn, "Server busy", time.perf_counter())
                        continue
                    pool.submit(self._worker_task, conn)
                    accepted += 1


def main() -> None:
    parser = argparse.ArgumentParser(description="EO Ground Station TCP Defender")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--config", default="config/defender_config.json")
    parser.add_argument("--pub-key", default="keys/pi.key.pub")
    parser.add_argument("--next-contact-s", type=float, default=None)
    parser.add_argument(
        "--detector-url",
        default=None,
        help="Optional teammate detector HTTP endpoint",
    )
    parser.add_argument(
        "--detector-model",
        default=None,
        help="Optional serialized detector loaded and executed in this process",
    )
    parser.add_argument("--detector-timeout-s", type=float, default=3.0)
    parser.add_argument("--max-tiles", type=int, default=None)
    parser.add_argument("--detector-token", default=None)
    parser.add_argument(
        "--detector-include-quarantine",
        action="store_true",
        help="Send quarantined payloads to an HTTP detector as analysis-only input",
    )
    parser.add_argument("--allow-insecure-detector", action="store_true")
    parser.add_argument("--state-file", default="state/replay.json")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional directory for accepted/ and quarantine/ GeoTIFF copies",
    )
    parser.add_argument("--tls-cert", default=None)
    parser.add_argument("--tls-key", default=None)
    parser.add_argument("--tls-client-ca", default=None)
    args = parser.parse_args()
    tls_context = None
    tls_values = (args.tls_cert, args.tls_key, args.tls_client_ca)
    if any(tls_values):
        if not args.tls_cert or not args.tls_key or not args.tls_client_ca:
            parser.error("--tls-cert, --tls-key, and --tls-client-ca are required together")
        tls_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        tls_context.load_cert_chain(args.tls_cert, args.tls_key)
        tls_context.load_verify_locations(args.tls_client_ca)
        tls_context.verify_mode = ssl.CERT_REQUIRED
    GroundStationServer(
        host=args.host,
        port=args.port,
        config_path=args.config,
        pub_key_path=args.pub_key,
        next_contact_s=args.next_contact_s,
        detector_url=args.detector_url,
        detector_model_path=args.detector_model,
        detector_timeout_s=args.detector_timeout_s,
        detector_token=args.detector_token,
        detector_include_quarantine=args.detector_include_quarantine,
        allow_insecure_detector=args.allow_insecure_detector,
        state_path=args.state_file,
        output_dir=args.output_dir,
        tls_context=tls_context,
    ).serve_forever(max_tiles=args.max_tiles)


if __name__ == "__main__":
    main()
