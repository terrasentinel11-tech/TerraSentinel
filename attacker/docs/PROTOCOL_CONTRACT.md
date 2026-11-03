# Verified Satellite–Ground Station Protocol Contract

This document describes the current code, not a proposed CCSDS or RF protocol.

## Connection model

- Satellite is the TCP client; Ground Station is the TCP server.
- One image frame is sent per TCP connection.
- The receiver returns one compact JSON object followed by `\n`.
- Default configured port is 9000.
- TCP does not provide cryptographic confidentiality or peer authentication. Mutual TLS is optional on the receiver and unsupported by the current Satellite client.

## Frame

```text
offset  size          meaning
0       4             unsigned big-endian header length
4       4             unsigned big-endian payload length
8       header_len    UTF-8 JSON header
...     payload_len   raw pixel bytes
```

Receiver limits from `defender_config.json`:

- Header: 1–65,536 bytes.
- Payload: exactly 1,703,936 bytes and no more than 2,097,152 bytes.
- Per-read timeout: 5 seconds.
- Total framed-message deadline: 10 seconds.

## Pixel payload

```text
shape:  [13, 256, 256]
dtype:  uint16
order:  C (bands, rows, columns)
bytes:  13 * 256 * 256 * 2 = 1,703,936
```

The code currently uses native-endian `np.uint16`. This is an interoperability ambiguity. Until the implementations explicitly use `<u2`, experiments must record host endianness and refuse mismatched hosts.

GeoTIFF metadata is not transmitted. CRS, affine transform, tags, descriptions, masks, attack labels, and ground truth remain out of band.

## Header schema

```json
{
  "manifest": {
    "tile_id": "non-empty string, max 128 characters",
    "source": "non-empty string, max 128 characters",
    "counter": 1,
    "ts": 1730000000.0,
    "shape": [13, 256, 256],
    "dtype": "uint16",
    "root": "64 lowercase/uppercase hex characters",
    "urgency": "routine",
    "deadline_s": 180.0
  },
  "sig": "128 hex characters",
  "leaves": ["256 SHA-256 hex digests"]
}
```

`urgency` is `routine` or `urgent`; `deadline_s` is finite and non-negative. Unknown extra keys are currently tolerated and are included in the signature if placed inside `manifest`.

## Hashing and signing

1. Divide the tile into a 16×16 grid of spatial blocks.
2. Each block contains all 13 bands and is `(13,16,16)`.
3. SHA-256 the contiguous block bytes, row-major across the grid, producing 256 leaves.
4. Compute a pairwise SHA-256 Merkle tree. Duplicate an odd final node, although the current 256-leaf tree is even at each level.
5. Put the root in the manifest.
6. Canonicalize the manifest with sorted JSON keys, no whitespace, and no NaN.
7. Sign canonical manifest bytes with Ed25519.

The leaves are not individually signed, but their Merkle root is. The receiver first verifies signature plus advertised-leaf root, then recomputes leaves from the received payload.

## Freshness and replay

- Counter must be a non-negative integer and strictly greater than the last accepted counter for the signed `source`.
- Default maximum age is 300 seconds.
- Default maximum future clock skew is 60 seconds.
- Counter and strike state may persist in `state/replay.json`.
- Satellite generates `max(previous + 1, time.time_ns())` in `counter.txt`.

Clock synchronization is therefore required. The plain Satellite counter file is not safe for concurrent transmitter processes.

## Receiver decisions

- `ACCEPT`: signature, Merkle root, freshness, counter, and all payload blocks passed.
- `QUARANTINE`: routine corrupted payload or invalid signature when contact is available.
- `UNVERIFIED_WAIT`: invalid signature without contact availability.
- `SALVAGE`: urgent payload with failed blocks; failed 16×16 areas are zeroed.
- `REJECT_REPLAY`: counter or timestamp freshness failure.
- `REJECT_MALFORMED`: framing or structure failure before a valid evaluation.

## Laboratory signing

Pre-sign experiments require a newly generated test Ed25519 keypair and an isolated Ground Station process configured with that test public key. The Red Team harness must accept the private key only by explicit path, must not log key bytes, and must never search for or copy `SATELLITE/keys/satellite_private.key`.

Post-sign experiments operate on an already formed authorized test frame and preserve its original signature/header unless the scenario explicitly tests header mutation.

## Versioning blockers

The current manifest contains no protocol version, declared band identities, acquisition metadata, or explicit byte order. Add these through coordinated Blue Team changes before production claims; the Red Team harness must not silently extend the wire schema.

