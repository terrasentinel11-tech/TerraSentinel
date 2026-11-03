# Three-Zone Coverage and Initial Results

This matrix records demonstrated repository coverage, not claimed operational vulnerabilities. Satellite Team's `SATELLITE/`, Ground Team's `ground station all/`, and the original `black_pixel_agri/` engine are treated as read-only systems under test.

| Zone | Implemented now | Missing / blocked | Validation environment |
|---|---|---|---|
| Satellite | Real `read_image` tests for exact shape/dtype and object-array rejection; offline pre-sign BLACK PIXEL generation; signed-frame/hash contract | Real Pi counter corruption/concurrency, filesystem/power behavior, signing-key failure, network/reply/log durability, resource measurements | Shape/type/security tests run locally; Pi items require the Raspberry Pi |
| In transit | One-byte post-sign alteration, selected BLACK PIXEL payload replacement, zero replacement baseline, signed-manifest alteration, replay, malformed JSON, bad declared size, truncation, pre-send delay, mid-frame termination; endpoint allowlist | Explicit two-ended relay, inter-chunk slow delivery, packet loss, real Wi-Fi interruption/timing | Frame construction runs locally; receiver decisions need isolated loopback; Wi-Fi claims need the isolated network |
| Ground Station | Real schema/signature compatibility tests, invalid shape/type metadata rejection, clean/tamper/replay unit coverage, receiver-compatible malformed frames, optional detector response recording | Full socket matrix, persisted replay restart, freshness edges, urgent salvage matrix, concurrency/resource/TLS tests, runnable semantic detector | Contract tests run locally; semantic results require a real configured detector |
| Combined | `--zone combined` evidence classification and common signed-frame workflow | Automated multi-stage campaign orchestration and physical end-to-end topology | Offline artifacts now; Pi + isolated receiver/network for physical chain |

## Image attack compatibility

The 12 pixel attacks—`field_patch_replacement`, `copy_move_clone`, `fake_drought_proxy`, `vegetation_recovery_proxy`, `fake_harvest_proxy`, `cloud_injection`, `cloud_shadow_combined`, `atmospheric_haze`, `scanline_stripes`, `single_band_ndvi`, `band_misregistration`, and `calibration_gain`—are compatible with the exact 13×256×256 `uint16` payload when their band/calibration prerequisites are satisfied. They can be applied before laboratory signing for Satellite/Ground Station semantic experiments or inserted after signing as a replacement payload for integrity experiments.

`georeference_shift` is the thirteenth attack. It is valid only as an offline metadata/Satellite-ingress experiment because CRS and affine metadata are not included in the TCP protocol. It cannot be observed by the current Ground Station.

## Result interpretation

- Cryptographic integrity and semantic detection are separate report fields.
- Offline generation records `frame_generated_not_executed`; it is not an acceptance or detection result.
- The repository has an optional detector HTTP client but no runnable semantic BLACK PIXEL detector service. No semantic detection result is claimed.
- Pre-sign manipulation with a dedicated laboratory key is a source-boundary simulation, not a signature bypass.
- Post-sign replacement preserves the originally signed manifest and is expected to fail payload integrity checks.

## Initial local evidence — 2026-11-02

- Independent attacker/zone suites: **53 passed, 1 skipped**. The skip is an existing optional test; three dependency warnings do not change the pass result.
- Ground Team Ground Station regression suite: **4 passed**.
- Satellite offline pre-sign evidence: `bp-20261102T192808.000308Z`.
- In-transit offline BLACK PIXEL replacement evidence: `bp-20261102T192809.314947Z`.
- Ground Station offline pre-sign evidence: `bp-20261102T192810.639078Z`.
- Combined clean offline evidence: `bp-20261102T192811.795103Z`.

All four evidence runs have `actual_result: frame_generated_not_executed`, `cryptographic_integrity_result: not_executed`, and no claimed semantic result. Raspberry Pi, isolated Wi-Fi, TLS, live receiver, and semantic-detector results remain **not tested** until those systems are explicitly configured.
