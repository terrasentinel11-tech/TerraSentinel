"""Three-zone experiment catalogue for the authorized laboratory harness."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ZoneScenario:
    zone: str
    target: str
    attack_position: str
    prerequisites: tuple[str, ...]


ZONE_SCENARIOS = {
    "satellite": {"clean", "pre_sign_attack"},
    "in_transit": {"clean", "post_sign_alter", "payload_replacement", "manifest_alter",
                   "replay", "incomplete", "malformed_header", "invalid_declared_size",
                   "delayed_transmission", "unexpected_termination"},
    "ground_station": {"clean", "pre_sign_attack", "post_sign_alter", "payload_replacement",
                       "manifest_alter", "replay", "incomplete", "malformed_header",
                       "invalid_declared_size", "delayed_transmission", "unexpected_termination"},
    "combined": {"clean", "pre_sign_attack", "post_sign_alter", "payload_replacement",
                 "manifest_alter", "replay", "incomplete", "malformed_header",
                 "invalid_declared_size", "delayed_transmission", "unexpected_termination"},
}


def describe(zone: str, scenario: str, *, executing: bool) -> ZoneScenario:
    if zone not in ZONE_SCENARIOS or scenario not in ZONE_SCENARIOS[zone]:
        raise ValueError(f"scenario {scenario!r} is not valid for zone {zone!r}")
    if zone == "satellite":
        return ZoneScenario(zone, "satellite image/signing boundary", "before signing",
                            ("authorized image copy", "dedicated laboratory key"))
    if zone == "in_transit":
        requirements = (("explicit lab endpoint", "isolated network") if executing
                        else ("offline signed frame",))
        return ZoneScenario(zone, "TCP application frame", "after signing, before receiver", requirements)
    if zone == "ground_station":
        requirements = (("isolated receiver", "dedicated laboratory public key") if executing
                        else ("offline receiver-compatible frame",))
        return ZoneScenario(zone, "ground station receiver", "receiver input boundary", requirements)
    requirements = (("isolated end-to-end lab", "dedicated laboratory keypair") if executing
                    else ("offline chain artifacts",))
    return ZoneScenario(zone, "satellite-to-ground chain", "selected chain boundary", requirements)


def image_attack_compatibility(attack: str) -> dict[str, str]:
    if attack == "georeference_shift":
        return {"satellite": "offline metadata validation only; pixels are unchanged",
                "in_transit": "incompatible; georeferencing is absent from the TCP payload",
                "ground_station": "incompatible with current receiver contract"}
    return {"satellite": "compatible before signing when source requirements are satisfied",
            "in_transit": "compatible as payload bytes; post-sign mutation must fail integrity",
            "ground_station": "compatible; crypto and semantic outcomes are separate"}
