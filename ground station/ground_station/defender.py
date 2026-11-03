"""Defender decision engine for cryptographic ground-station verification."""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from ground_station.crypto_protocol import (
    EXPECTED_BANDS,
    EXPECTED_HEIGHT,
    EXPECTED_WIDTH,
    GRID_COLS,
    GRID_ROWS,
    compare_blocks_and_build_masks,
    compute_block_hashes,
    compute_merkle_root,
    verify_manifest_signature,
)


@dataclass
class EvaluationOutcome:
    """Structured result returned by DefenderEngine for a single tile."""

    tile_id: str
    source: str
    claimed_source: str
    counter: int
    rule_key: str
    decision: str
    action: str
    reason: str
    sig_valid: bool
    counter_valid: bool
    failed_blocks: list[int]
    tamper_map: np.ndarray  # (16, 16) uint8
    pixel_mask: np.ndarray  # (256, 256) bool
    trust_score: float | None
    channel_flags: dict[str, bool]
    heatmap: np.ndarray  # (256, 256) float32
    released_tile: np.ndarray  # (13, 256, 256) uint16 or empty (0,) uint16
    stale_fallback_used: bool
    retransmit_requested: bool
    parallel_verification_pending: bool
    strikes_for_source: int
    revocation_recommended: bool


class DefenderEngine:
    """Stateful verifier and decision engine enforcing verification order and response table."""

    def __init__(
        self,
        config_path: str | Path,
        public_key: Ed25519PublicKey,
        state_path: str | Path | None = None,
    ) -> None:
        self.config_path = Path(config_path)
        self.config: dict[str, Any] = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.public_key = public_key
        self.state_path = Path(state_path) if state_path else None

        self.max_strikes: int = int(self.config.get("max_strikes_before_revocation", 3))
        self.default_next_contact_s: float = float(self.config.get("default_next_contact_s", 120.0))
        self.max_age_s: float | None = (
            None if self.config.get("max_age_s") is None else float(self.config["max_age_s"])
        )
        self.max_future_skew_s: float = float(self.config.get("max_future_skew_s", 60.0))
        self.advance_counter_on_block_failure: bool = bool(
            self.config.get("advance_counter_on_block_failure", False)
        )
        self.table: dict[str, dict[str, Any]] = self.config["response_table"]

        self.last_counter: dict[str, int] = {}
        self.bad_strikes: dict[str, int] = {}
        self.last_known_good: dict[str, np.ndarray] = {}
        self._load_state()

    def evaluate_tile(
        self,
        header: dict[str, Any],
        payload_bytes: bytes,
        next_contact_s: float | None = None,
        now_ts: float | None = None,
    ) -> EvaluationOutcome:
        """Run strict 4-step verification order and map to the config-driven response table."""
        manifest = header["manifest"]
        sig_hex = header["sig"]
        leaves_hex = header["leaves"]

        tile_id = str(manifest["tile_id"])
        claimed_source = str(manifest["source"])
        counter = int(manifest["counter"])
        ts_manifest = float(manifest["ts"])
        urgency = str(manifest["urgency"])
        deadline_s = float(manifest["deadline_s"])

        effective_next_contact = (
            self.default_next_contact_s if next_contact_s is None else float(next_contact_s)
        )
        contact_available = effective_next_contact <= deadline_s

        empty_tamper = np.zeros((GRID_ROWS, GRID_COLS), dtype=np.uint8)
        empty_mask = np.zeros((EXPECTED_HEIGHT, EXPECTED_WIDTH), dtype=bool)
        empty_heatmap = np.zeros((EXPECTED_HEIGHT, EXPECTED_WIDTH), dtype=np.float32)
        empty_tile = np.empty((0,), dtype=np.uint16)

        sig_ok = verify_manifest_signature(manifest, sig_hex, self.public_key)
        try:
            merkle_ok = compute_merkle_root(leaves_hex).lower() == str(manifest["root"]).lower()
        except ValueError:
            merkle_ok = False

        if not (sig_ok and merkle_ok):
            if contact_available:
                rule_key = "sig_invalid_contact"
                lkg = self.last_known_good.get(claimed_source)
                released = lkg.copy() if lkg is not None else empty_tile
                stale_used = lkg is not None
                reason = (
                    f"Signature/Merkle invalid (unattributed claim '{claimed_source}'); "
                    "contact available -> quarantine & serve stale LKG"
                )
            else:
                rule_key = "sig_invalid_no_contact"
                released = empty_tile
                stale_used = False
                reason = (
                    f"Signature/Merkle invalid (unattributed claim '{claimed_source}'); "
                    "no contact -> quarantine & wait as unverified"
                )

            rule = self.table[rule_key]
            return EvaluationOutcome(
                tile_id=tile_id,
                source="unattributed",
                claimed_source=claimed_source,
                counter=counter,
                rule_key=rule_key,
                decision=str(rule["decision"]),
                action=str(rule["action"]),
                reason=reason,
                sig_valid=False,
                counter_valid=False,
                failed_blocks=[],
                tamper_map=empty_tamper,
                pixel_mask=empty_mask,
                trust_score=None,
                channel_flags={},
                heatmap=empty_heatmap,
                released_tile=released,
                stale_fallback_used=stale_used,
                retransmit_requested=bool(rule.get("retransmit", False)),
                parallel_verification_pending=False,
                strikes_for_source=self.bad_strikes.get(claimed_source, 0),
                revocation_recommended=False,
            )

        source = claimed_source

        prev_counter = self.last_counter.get(source, -1)
        if counter <= prev_counter:
            strikes = self._record_confirmed_strike(source)
            revoke = strikes >= self.max_strikes
            rule_key = "stale_counter"
            rule = self.table[rule_key]
            return EvaluationOutcome(
                tile_id=tile_id,
                source=source,
                claimed_source=source,
                counter=counter,
                rule_key=rule_key,
                decision=str(rule["decision"]),
                action=str(rule["action"]),
                reason=f"Stale counter {counter} <= last accepted {prev_counter}",
                sig_valid=True,
                counter_valid=False,
                failed_blocks=[],
                tamper_map=empty_tamper,
                pixel_mask=empty_mask,
                trust_score=None,
                channel_flags={},
                heatmap=empty_heatmap,
                released_tile=empty_tile,
                stale_fallback_used=False,
                retransmit_requested=bool(rule.get("retransmit", False)),
                parallel_verification_pending=False,
                strikes_for_source=strikes,
                revocation_recommended=strikes >= self.max_strikes,
            )

        if self.max_age_s is not None and now_ts is not None:
            age_s = float(now_ts) - ts_manifest
            if age_s > self.max_age_s or age_s < -self.max_future_skew_s:
                strikes = self._record_confirmed_strike(source)
                revoke = strikes >= self.max_strikes
                rule_key = "stale_counter"
                rule = self.table[rule_key]
                return EvaluationOutcome(
                    tile_id=tile_id,
                    source=source,
                    claimed_source=source,
                    counter=counter,
                    rule_key=rule_key,
                    decision=str(rule["decision"]),
                    action=str(rule["action"]),
                    reason=(
                        f"Timestamp out of freshness window (age={age_s:.1f}s, "
                        f"allowed=[{-self.max_future_skew_s:.1f}s, {self.max_age_s:.1f}s])"
                    ),
                    sig_valid=True,
                    counter_valid=False,
                    failed_blocks=[],
                    tamper_map=empty_tamper,
                    pixel_mask=empty_mask,
                    trust_score=None,
                    channel_flags={},
                    heatmap=empty_heatmap,
                    released_tile=empty_tile,
                    stale_fallback_used=False,
                    retransmit_requested=bool(rule.get("retransmit", False)),
                    parallel_verification_pending=False,
                    strikes_for_source=strikes,
                    revocation_recommended=strikes >= self.max_strikes,
                )

        tile = np.frombuffer(payload_bytes, dtype=np.uint16).reshape(
            (EXPECTED_BANDS, EXPECTED_HEIGHT, EXPECTED_WIDTH)
        ).copy()
        computed_leaves = compute_block_hashes(tile)
        failed_blocks, tamper_map, pixel_mask = compare_blocks_and_build_masks(
            computed_leaves, leaves_hex
        )

        if failed_blocks:
            if self.advance_counter_on_block_failure:
                self.last_counter[source] = counter
                self._save_state()
            strikes = self._record_confirmed_strike(source)
            revoke = strikes >= self.max_strikes
            if urgency == "routine":
                rule_key = "blocks_fail_routine"
                released = empty_tile
                reason = f"{len(failed_blocks)}/256 blocks failed hash check (routine) -> quarantine"
            else:
                rule_key = "blocks_fail_urgent"
                salvaged = tile.copy()
                salvaged[:, pixel_mask] = 0
                released = salvaged
                reason = f"{len(failed_blocks)}/256 blocks failed hash check (urgent) -> salvage verified blocks"

            rule = self.table[rule_key]
            return EvaluationOutcome(
                tile_id=tile_id,
                source=source,
                claimed_source=source,
                counter=counter,
                rule_key=rule_key,
                decision=str(rule["decision"]),
                action=str(rule["action"]),
                reason=reason,
                sig_valid=True,
                counter_valid=True,
                failed_blocks=failed_blocks,
                tamper_map=tamper_map,
                pixel_mask=pixel_mask,
                trust_score=None,
                channel_flags={},
                heatmap=empty_heatmap,
                released_tile=released,
                stale_fallback_used=False,
                retransmit_requested=bool(rule.get("retransmit", True)),
                parallel_verification_pending=False,
                strikes_for_source=strikes,
                revocation_recommended=revoke,
            )

        self.last_counter[source] = counter
        self._save_state()

        rule_key = "accept_clean"
        rule = self.table[rule_key]
        self.last_known_good[source] = tile.copy()
        strikes = self.bad_strikes.get(source, 0)
        return EvaluationOutcome(
            tile_id=tile_id,
            source=source,
            claimed_source=source,
            counter=counter,
            rule_key=rule_key,
            decision=str(rule["decision"]),
            action=str(rule["action"]),
            reason="Signature, Merkle root, freshness, counter, and all payload blocks verified",
            sig_valid=True,
            counter_valid=True,
            failed_blocks=[],
            tamper_map=tamper_map,
            pixel_mask=pixel_mask,
            trust_score=None,
            channel_flags={},
            heatmap=empty_heatmap,
            released_tile=tile,
            stale_fallback_used=False,
            retransmit_requested=bool(rule.get("retransmit", False)),
            parallel_verification_pending=False,
            strikes_for_source=strikes,
            revocation_recommended=strikes >= self.max_strikes,
        )

    def _record_confirmed_strike(self, source: str) -> int:
        self.bad_strikes[source] = self.bad_strikes.get(source, 0) + 1
        self._save_state()
        return self.bad_strikes[source]

    def _record_clean_acceptance(self, source: str) -> int:
        strikes = self.bad_strikes.get(source, 0)
        self.bad_strikes[source] = strikes
        return strikes

    def _load_state(self) -> None:
        if self.state_path is None or not self.state_path.exists():
            return
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        counters = data.get("last_counter", {})
        strikes = data.get("bad_strikes", {})
        if not isinstance(counters, dict) or not isinstance(strikes, dict):
            raise ValueError("Invalid replay state")
        self.last_counter = {str(k): int(v) for k, v in counters.items()}
        self.bad_strikes = {str(k): int(v) for k, v in strikes.items()}

    def _save_state(self) -> None:
        if self.state_path is None:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"last_counter": self.last_counter, "bad_strikes": self.bad_strikes}
        fd, temp_name = tempfile.mkstemp(prefix=".replay-", dir=self.state_path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.state_path)
        except Exception:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise
