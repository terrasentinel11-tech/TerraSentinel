
# INTEGRATION CONTRACT: ATTACK RELAY <-> GROUND STATION (TRACK 3)

## 1. Transport & Wire Framing (Fixed)

- **Destination:** Ground Station TCP `<GS_IP>:9000` (one TCP connection per tile).
- **Framing:** `[4B big-endian uint32: header_len][4B big-endian uint32: payload_len][header_bytes][payload_bytes]`
  - `header_len` <= 65,536 bytes; `payload_len` == 1,703,936 bytes (`13 * 256 * 256 * 2`).
- **Header JSON (`UTF-8`):** `{"manifest": {...}, "sig": "<128-hex-char Ed25519 sig>", "leaves": ["<64-hex-char sha256>", ... (256 items)]}`
- **Manifest Fields:** `tile_id` (str), `source` (str), `counter` (strictly increasing int), `ts` (float unix time), `shape` (`[13, 256, 256]`), `dtype` (`"uint16"`), `root` (64-hex-char Merkle root), `urgency` (`"routine"` or `"urgent"`), `deadline_s` (float).
- **Canonical Manifest Bytes for Signing:** `json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")`.
- **Block Ordering:** 16x16 grid of `(13, 16, 16)` blocks in row-major order (`r = 0..15`, `c = 0..15`), each hashed as `sha256(tile[:, r*16:(r+1)*16, c*16:(c+1)*16].tobytes(order="C")).hexdigest()`.
- **Merkle Tree:** Pairwise `sha256(bytes.fromhex(left) + bytes.fromhex(right))`, duplicating the last node if a level has an odd count.
- **Ground Station Reply:** One newline-terminated JSON line per connection (`{"status":"ok","tile_id":...,"decision":...}`).

## 2. Two Attack Positions to Evaluate

- **Position A (In-Transit / Post-Signing Attack):**
  - The tile is signed on the satellite emulator first, and the relay modifies payload bytes, header fields, or packet ordering in transit without the private key.
  - Expected Ground Station layer triggered: Ed25519 signature check, Merkle root check, anti-replay counter check, or 16x16 SHA-256 block hash verification (`QUARANTINE`, `SALVAGE`, or `REJECT_REPLAY`).
- **Position B (Compromised Source / Pre-Signing Attack):**
  - The tile pixels are manipulated *before* the block hashes, Merkle root, and Ed25519 signature are computed.
  - Cryptographic checks pass completely; semantic analysis is outside this repository and belongs to the dashboard/backend team.

## 3. Ground-Truth Labels & Masks Delivery (Post-Run Join by `tile_id`)

After a test run, provide a `labels/attack_labels.csv` file and a folder of `.npy` boolean pixel masks (`shape=(256, 256), dtype=bool`) joinable to Ground Station logs by `tile_id`:


| Column            | Type    | Description                                                                                             |
| :------------------ | :-------- | :-------------------------------------------------------------------------------------------------------- |
| `tile_id`         | `str`   | Exact match to `manifest["tile_id"]` sent over TCP                                                      |
| `attack_family`   | `str`   | `"clean"` or attack name (e.g., `"ndvi_forgery"`, `"cloud_injection"`, `"sealed_family_1"`)             |
| `attacker_tier`   | `str`   | `"clean"`, `"T0"` (naive), `"T1"` (spectral-aware), `"T2"` (cross-sensor-consistent), `"T3"` (adaptive) |
| `attack_position` | `str`   | `"none"`, `"post_sign"` (Position A), or `"pre_sign"` (Position B)                                      |
| `severity`        | `float` | Perturbation magnitude / area fraction (`0.0` for clean)                                                |
| `seed`            | `int`   | Fixed random seed used to generate the attack                                                           |
| `gt_mask_file`    | `str`   | Relative path to `(256, 256)` boolean `.npy` ground-truth modified-pixel mask                           |

## 4. Sealed Attack Families Rule

- During development, share a calibration subset of `T0–T2` families with the evaluation team. Do not place those attack tools or labels in the ground-station repository.
- Keep held-out / `T3` adaptive attack families **sealed** until final evaluation. Deliver labels and masks separately to the evaluation team; never send them to the defender or include them in the wire packet.
