# BLACK PIXEL Attack Matrix

## Image-content compatibility

All entries below refer to the actual `ATTACKS` registry. Compatibility assumes a 13-band, 256×256, `uint16` GeoTIFF with correct band semantics. A shape match alone does not prove the band order or radiometric scale.

| Attack | Bands / calibration | Satellite pixel payload | Notes |
|---|---|---:|---|
| `field_patch_replacement` | No named-band requirement | Supported | Requires a valid target and distinct donor region. |
| `copy_move_clone` | No named-band requirement | Supported | Requires a compatible donor region. |
| `fake_drought_proxy` | B04+B08; scale required | Supported when verified | Synthetic agronomic proxy, not a physical drought claim. |
| `vegetation_recovery_proxy` | B04+B08; scale required | Supported when verified | Requires stressed target candidates. |
| `fake_harvest_proxy` | B04+B08; scale required | Supported when verified | Requires vegetation and bare-soil candidates. |
| `cloud_injection` | No named-band requirement | Supported | Synthetic optical cloud proxy. |
| `cloud_shadow_combined` | No named-band requirement | Supported | Synthetic cloud plus shifted shadow. |
| `atmospheric_haze` | No named-band requirement | Supported | Synthetic percentile-based haze. |
| `scanline_stripes` | No named-band requirement | Supported | Applies sensor-like stripe gains to all bands. |
| `single_band_ndvi` | B04+B08; scale required | Supported when verified | Perturbs B08 only. |
| `band_misregistration` | B08 | Supported when verified | B08 semantic mapping must be known. |
| `calibration_gain` | B04 | Supported when verified | B04 semantic mapping must be known. |
| `georeference_shift` | CRS and affine transform | **Not observable over wire** | Pixels remain identical and the protocol omits georeferencing. Offline-only. |

RGB-only input is not accepted by the Satellite. If a future capture pipeline provides only RGB, spatial, atmospheric, and scanline transformations may be evaluated offline, but the result remains incompatible with the current wire contract. Spectral/agronomic attacks must not fabricate B04/B08 or calibration.

## Protocol scenario matrix

| Scenario | Mutation position | Expected current defense | Success criterion |
|---|---|---|---|
| `clean` | None | `ACCEPT` | Receiver accepts an unmodified valid frame. |
| `post_sign_payload_alteration` | Payload after signing | `QUARANTINE` for routine, `SALVAGE` for urgent | At least one failed block; no unmodified malicious tile released. |
| `post_sign_payload_replacement` | Whole payload after signing | Quarantine/salvage | Receiver reports block failures. |
| `replay` | Resend accepted signed frame | `REJECT_REPLAY` | Second delivery is rejected by counter. |
| `incomplete_transmission` | Truncate frame | Error/EOF rejection | No tile is accepted. A reply may be impossible after disconnect. |
| `malformed_header` | Invalid JSON/schema/header | `REJECT_MALFORMED` | No defender evaluation of a tile. |
| `invalid_payload_size` | Prefix length | `REJECT_MALFORMED` | Rejected before declared payload read. |
| `delayed_transmission` | Inter-chunk delay | Accept within deadline; timeout beyond it | Observed result matches configured total deadline. |
| `unexpected_termination` | Close connection mid-frame | EOF/error rejection | No tile accepted. |
| `pre_sign_image_manipulation` | Pixels before laboratory signing | Crypto normally `ACCEPT` | Crypto accepts; semantic detector result is recorded separately. |
| `manifest_alteration` | Signed manifest after signing | Quarantine/unverified wait | Signature invalid. |

## Interpretation rules

- A rejected attack is evidence that the defense worked, not a failed experiment.
- A valid signature on an intentionally modified laboratory image is not a signature bypass.
- Crypto acceptance says that bytes match the signed manifest; it does not establish physical truth.
- Do not infer semantic detection when no detector endpoint was configured.
- A transport experiment is `UNDETERMINED` when no complete response/evidence exists.
- Never report mock dashboard values as measured outcomes.

## Current validation gaps

Ground Station unit tests cover clean acceptance, one-byte corruption, in-memory replay, and schema-helper availability. They do not yet cover real sockets, partial reads, deadlines, oversized frames, freshness boundaries, restart persistence, TLS, concurrency, detector failures, or strike amplification.

Satellite has no automated tests for key loading, concurrent counter access, reply parsing, network failures, or log durability. Hardware throughput and Wi-Fi behavior remain unmeasured.

