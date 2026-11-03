"""Deterministic transformations of valid lab frames for protocol experiments."""
from __future__ import annotations

from dataclasses import dataclass
import json
import struct
from typing import Callable

from .protocol import LabFrame, PAYLOAD_BYTES


@dataclass(frozen=True)
class Scenario:
    name: str
    expected: str
    prepare: Callable[[LabFrame], bytes]


def _clean(frame: LabFrame) -> bytes:
    return frame.encode()


def _post_sign_alter(frame: LabFrame) -> bytes:
    payload = bytearray(frame.payload)
    payload[0] ^= 1
    return LabFrame(frame.header, bytes(payload)).encode()


def _replacement(frame: LabFrame) -> bytes:
    return LabFrame(frame.header, bytes(PAYLOAD_BYTES)).encode()


def _incomplete(frame: LabFrame) -> bytes:
    encoded = frame.encode()
    return encoded[:-4096]


def _malformed_header(frame: LabFrame) -> bytes:
    bad = b"{not-json"
    return struct.pack(">II", len(bad), len(frame.payload)) + bad + frame.payload


def _invalid_size(frame: LabFrame) -> bytes:
    return frame.encode(declared_payload_size=PAYLOAD_BYTES + 2)


def _manifest_alter(frame: LabFrame) -> bytes:
    header = json.loads(json.dumps(frame.header))
    header["manifest"]["tile_id"] = f'{header["manifest"]["tile_id"]}-altered'
    return LabFrame(header, frame.payload).encode()


SCENARIOS = {
    "clean": Scenario("clean", "ACCEPT", _clean),
    "post_sign_alter": Scenario("post_sign_alter", "QUARANTINE", _post_sign_alter),
    "payload_replacement": Scenario("payload_replacement", "QUARANTINE", _replacement),
    "incomplete": Scenario("incomplete", "REJECT_MALFORMED_OR_EOF", _incomplete),
    "malformed_header": Scenario("malformed_header", "REJECT_MALFORMED", _malformed_header),
    "invalid_declared_size": Scenario("invalid_declared_size", "REJECT_MALFORMED", _invalid_size),
    "manifest_alter": Scenario("manifest_alter", "REJECT_INVALID_SIGNATURE", _manifest_alter),
    # Replay is executed by transmitting the exact clean bytes twice.
    "replay": Scenario("replay", "ACCEPT_THEN_REJECT_REPLAY", _clean),
    "delayed_transmission": Scenario("delayed_transmission", "ACCEPT_OR_TIMEOUT_BY_DELAY", _clean),
    "unexpected_termination": Scenario("unexpected_termination", "REJECT_MALFORMED_OR_EOF", _clean),
    # Pre-sign means the attacked tile is supplied to build_signed_frame; it is not a bypass.
    "pre_sign_attack": Scenario("pre_sign_attack", "CRYPTO_ACCEPT_SEMANTIC_RESULT_EXTERNAL", _clean),
}


def prepare_scenario(name: str, frame: LabFrame) -> bytes:
    try:
        scenario = SCENARIOS[name]
    except KeyError as exc:
        raise ValueError(f"unknown scenario {name!r}; choose from {', '.join(SCENARIOS)}") from exc
    return scenario.prepare(frame)

