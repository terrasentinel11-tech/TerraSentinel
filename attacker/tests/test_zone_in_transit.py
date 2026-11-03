from __future__ import annotations
import struct
import numpy as np
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from red_team.protocol import SHAPE, build_signed_frame
from red_team.scenarios import prepare_scenario
from red_team.zones import describe

def test_in_transit_scenarios_are_post_sign_boundaries():
    assert describe("in_transit", "post_sign_alter", executing=False).attack_position == "after signing, before receiver"

def test_incomplete_frame_is_shorter_than_declared():
    frame = build_signed_frame(np.zeros(SHAPE, dtype=np.uint16), Ed25519PrivateKey.generate(), tile_id="x")
    wire = prepare_scenario("incomplete", frame)
    header_len, payload_len = struct.unpack(">II", wire[:8])
    assert len(wire) < 8 + header_len + payload_len
