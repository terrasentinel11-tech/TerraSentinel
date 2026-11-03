# BLACK PIXEL Red Team Architecture

## Scope and trust boundaries

This project is an authorized laboratory harness. It reuses `black_pixel_agri`; it does not duplicate its 13 transformations, modify the Satellite or Ground Station, intercept unrelated traffic, or acquire a production private key. Network execution is opt-in and restricted to configured laboratory endpoints. Offline artifact generation is the default.

The three independently owned systems are:

1. `attacker/black_pixel_agri`: deterministic GeoTIFF transformations, masks, and attack manifests.
2. `SATELLITE`: an outbound sender that validates a `(13, 256, 256)` `uint16` TIFF/NPY, signs a manifest with Ed25519, and sends one TCP frame per connection.
3. `ground station all`: a TCP receiver that validates framing, signature, Merkle root, freshness, replay counter, and all 256 payload block hashes. Its semantic detector is optional and external.

## Verified data flow

```text
GeoTIFF/NPY
    |
    +-- clean path --> Satellite read_image --> hash/sign --> TCP --> Ground Station
    |
    +-- RED TEAM, pre-sign laboratory path
    |      BLACK PIXEL --> attacked 13-band tile --> lab signer --> TCP --> Ground Station
    |
    +-- RED TEAM, post-sign path
           legitimate framed bytes --> controlled mutation/relay --> Ground Station
```

Pre-sign manipulation is a source-compromise simulation using a dedicated laboratory signing key. It is not a cryptographic bypass. Post-sign manipulation preserves the original signed envelope and is expected to fail integrity checks.

## Red Team package responsibilities

The independent `red_team` package is organized around these boundaries:

- `adapters`: validate and translate BLACK PIXEL results into the exact raw tile contract without inventing bands, resampling silently, or changing dtype.
- `transport`: construct, parse, mutate, and send the real length-prefixed protocol.
- `scenarios`: named, deterministic clean/pre-sign/post-sign/malformed/replay experiments.
- `experiment_runner`: enforce configuration, execute one scenario, evaluate success criteria, and finalize a report.
- `evidence`: immutable-per-run artifacts: configuration, hashes, mask, request/frame metadata, receiver response, timing, status, and errors.
- `configuration`: offline-safe defaults and explicit endpoint allowlisting.
- `core`: typed domain records, validation, IDs, clocks, and hashing.

BLACK PIXEL remains the only attack implementation. The adapter calls its public orchestration and records `Result.changed_mask` and `Result.manifest`.

## Security controls

- Offline is the default; no network call occurs without an explicit scenario and destination.
- Only literal loopback or configured laboratory IP addresses and ports are permitted.
- Hostnames, public destinations, wildcard ranges, packet capture, ARP spoofing, and transparent interception are outside scope.
- Test signing keys are supplied explicitly and are never copied from the Satellite.
- Evidence directories are created per experiment and never silently reused.
- Original source files are hash-checked and remain unchanged.
- No attack label or ground-truth mask is placed in the wire packet.
- A run records an error or `UNDETERMINED` status instead of manufacturing a result.

## Actual implementation boundaries

The Satellite currently accepts only `.tif`, `.tiff`, and `.npy`; it rejects anything not exactly `(13, 256, 256)` `uint16` (`SATELLITE/satellite.py`, `read_image`). It transmits pixel samples only, so GeoTIFF CRS, affine transform, tags, nodata, and band descriptions do not cross the wire. Consequently, `georeference_shift` is valid as an offline metadata experiment but has no observable effect in this protocol.

The Ground Station has one configured public key, not a source-to-key registry. For pre-sign testing, a matching dedicated test public key must be supplied to an isolated receiver instance. Never replace the team's operational key during a test.

## Known operational risks

- Pixel byte order is native-endian on both implementations rather than explicitly versioned. The present Windows/Raspberry Pi pairing is normally little-endian, but the contract should be changed to explicit little-endian before portability claims.
- Satellite counter persistence is a plain file write and is not locked or atomic. Do not run concurrent Satellite processes against the same `counter.txt`.
- Ground Station mTLS is optional and disabled by default.
- Ground Station TLS handshaking occurs in the accept loop before bounded worker admission.
- Replay counters persist, but last-known-good imagery and audit evidence do not.
- The web dashboard contains mock data; it is not experiment evidence.

## Source references

- Satellite input, hashing, signing, and framing: `SATELLITE/satellite.py:17-85`.
- Ground Station schema/framing: `ground station all/ground_station/crypto_protocol.py:23-31,138-198,227-262`.
- Ground Station decisions: `ground station all/ground_station/defender.py:90-319`.
- BLACK PIXEL registry and synthesis: `attacker/black_pixel_agri/attacks.py:21-35,120-214`.
- BLACK PIXEL result masks/manifests: `attacker/black_pixel_agri/engine.py:51-109`.
