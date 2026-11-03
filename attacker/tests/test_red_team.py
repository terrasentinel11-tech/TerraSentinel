from __future__ import annotations

import json
import struct

import numpy as np
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from red_team.adapters import run_attack
from red_team.evidence import write_bundle
from red_team.protocol import PAYLOAD_BYTES, SHAPE, block_hashes, build_signed_frame, merkle_root
from red_team.scenarios import prepare_scenario
from red_team.transport import validate_lab_endpoint


def test_protocol_matches_verified_contract():
    tile = np.arange(np.prod(SHAPE), dtype=np.uint16).reshape(SHAPE)
    frame = build_signed_frame(tile, Ed25519PrivateKey.generate(), tile_id="lab-1", counter=7,
                               timestamp=100.0)
    encoded = frame.encode()
    header_len, payload_len = struct.unpack(">II", encoded[:8])
    header = json.loads(encoded[8:8 + header_len])
    assert payload_len == PAYLOAD_BYTES == 1_703_936
    assert header["manifest"]["shape"] == [13, 256, 256]
    assert header["manifest"]["root"] == merkle_root(block_hashes(tile))
    assert len(header["leaves"]) == 256


@pytest.mark.parametrize("scenario", [
    "clean", "post_sign_alter", "payload_replacement", "incomplete",
    "malformed_header", "invalid_declared_size", "manifest_alter", "replay", "pre_sign_attack",
    "delayed_transmission", "unexpected_termination",
])
def test_scenario_is_deterministically_prepared(scenario):
    tile = np.zeros(SHAPE, dtype=np.uint16)
    frame = build_signed_frame(tile, Ed25519PrivateKey.generate(), tile_id="lab", timestamp=1)
    first = prepare_scenario(scenario, frame)
    second = prepare_scenario(scenario, frame)
    assert first == second


def test_post_sign_alter_preserves_signed_header():
    tile = np.zeros(SHAPE, dtype=np.uint16)
    frame = build_signed_frame(tile, Ed25519PrivateKey.generate(), tile_id="lab")
    clean, changed = frame.encode(), prepare_scenario("post_sign_alter", frame)
    clean_hlen = struct.unpack(">I", clean[:4])[0]
    changed_hlen = struct.unpack(">I", changed[:4])[0]
    assert clean[8:8 + clean_hlen] == changed[8:8 + changed_hlen]
    assert clean != changed


def test_manifest_alter_preserves_signature_and_payload():
    tile = np.zeros(SHAPE, dtype=np.uint16)
    frame = build_signed_frame(tile, Ed25519PrivateKey.generate(), tile_id="lab")
    changed = prepare_scenario("manifest_alter", frame)
    hlen = struct.unpack(">I", changed[:4])[0]
    header = json.loads(changed[8:8 + hlen])
    assert header["sig"] == frame.header["sig"]
    assert header["manifest"] != frame.header["manifest"]
    assert changed[8 + hlen:] == frame.payload


def test_adapter_reuses_attack_engine_and_preserves_source(tmp_path):
    from black_pixel_agri.demo import create
    source = create(tmp_path / "scene.tif")
    before = source.read_bytes()
    result = run_attack(source, attack="cloud_injection", seed=19)
    assert source.read_bytes() == before
    assert result.original.shape == result.attacked.shape == SHAPE
    assert result.original.dtype == result.attacked.dtype == np.uint16
    assert result.changed_mask.any()
    assert result.metadata["seed"] == 19


def test_clean_adapter_is_identity_with_empty_mask(tmp_path):
    from black_pixel_agri.demo import create
    source = create(tmp_path / "scene.tif")
    result = run_attack(source, attack="clean", seed=19)
    assert np.array_equal(result.original, result.attacked)
    assert not result.changed_mask.any()
    assert result.metadata["executed_attack"] == "clean"
    assert result.metadata["original_array_sha256"] == result.metadata["attacked_array_sha256"]


def test_georeference_is_explicitly_wire_incompatible(tmp_path):
    from black_pixel_agri.demo import create
    source = create(tmp_path / "scene.tif")
    with pytest.raises(ValueError, match="absent from the wire protocol"):
        run_attack(source, attack="georeference_shift")


def test_evidence_bundle_is_machine_readable(tmp_path):
    mask = np.zeros((256, 256), dtype=bool); mask[1, 2] = True
    folder = write_bundle(tmp_path, {"experiment_id": "test-1", "actual": None}, changed_mask=mask)
    record = json.loads((folder / "report.json").read_text())
    assert record["schema_version"] == "black-pixel-red-team/1"
    assert np.load(folder / "actual_change_mask.npy", allow_pickle=False)[1, 2]


def test_transport_requires_explicit_allowlist():
    with pytest.raises(ValueError, match="allowlist"):
        validate_lab_endpoint("127.0.0.1", 9000, set())
    validate_lab_endpoint("127.0.0.1", 9000, {"127.0.0.1"})

