# EO Ground Station, Defender, and Detector Integration

This folder contains the ground-station TCP receiver and the cryptographic
defender. The defender is not a second process: `ground_station.server` calls
`DefenderEngine` for every received tile. The service verifies the Ed25519
signature, Merkle root, freshness, replay counter, and all 256 payload blocks,
then returns one JSON decision.

The service does not contain an AI model, dashboard database, attack simulator,
or image persistence. A model is integrated as a separate HTTP detector and is
called only after the defender releases a verified tile.

To save received images for an authorized laboratory review, pass
`--output-dir C:\BlackPixelLab\images`. Accepted tiles are written under
`accepted\`; rejected or quarantined packets with a valid payload are written
under `quarantine\`. Quarantined files are forensic copies only and are never
sent to the detector as released tiles.

## 1. Start on Windows

Open PowerShell in this directory:

```powershell
cd "C:\Users\user\Desktop\Ground-Truth-Under-Attack-Securing-the-Earth-Observation-Chain\ground station all"
.\.venv\Scripts\python.exe -m ground_station.server `
  --host 127.0.0.1 `
  --port 9000 `
  --config config/defender_config.json `
  --pub-key keys/pi.key.pub `
  --state-file state\replay.json
```

Use `--host 0.0.0.0` only when a controlled client on another machine must
connect. Do not expose port 9000 to the public Internet. The server prints
`Ground station listening on ...` when it is ready. Stop it with `Ctrl+C`.

Docker starts the same server and persists replay state in a named volume:

```powershell
docker compose up --build
```

The Docker service maps `localhost:9000` to the container. Stop it with
`Ctrl+C`, or use `docker compose down`.

## 2. Run the tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The tests cover clean acceptance, payload tampering, replay rejection, and
frame/header validation.

## 3. Integrate your model

Run your model behind an HTTP endpoint that accepts the released-tile request
below. HTTPS is required by default; the ground station rejects an `http://`
detector URL unless `--allow-insecure-detector` is explicitly supplied for a
local-only test.

```json
{
  "tile_id": "tile-001",
  "source": "sat-pi-01",
  "shape": [13, 256, 256],
  "dtype": "uint16",
  "tile_base64": "<base64 of C-order uint16 bytes>",
  "defender": {
    "decision": "ACCEPT",
    "failed_blocks": [],
    "tampered_pixel_count": 0
  }
}
```

The embedded detector is preferred when the model is available locally. It
loads the teammate's serialized model inside the Ground Station process:

```powershell
.\.venv\Scripts\python.exe -m ground_station.server `
  --config config\defender_config.json `
  --pub-key keys\redteam_lab.key.pub `
  --state-file state\replay.json `
  --output-dir .\received_images `
  --detector-model .\detector_model\detector.joblib `
  --detector-include-quarantine
```

The `.joblib` object must expose `predict_tile(tile)` and return a JSON-like
mapping. A standard estimator exposing `predict(features)` is also supported.
The model runs in-process; no FastAPI detector service is required.

For the optional HTTP mode, the model endpoint should return one JSON object,
for example:

```json
{
  "label": "clean",
  "score": 0.98,
  "model_version": "my-model-1.0"
}
```

Start the station with the model URL:

```powershell
.\.venv\Scripts\python.exe -m ground_station.server `
  --host 127.0.0.1 --port 9000 `
  --config config/defender_config.json `
  --pub-key keys/pi.key.pub `
  --state-file state\replay.json `
  --detector-url https://127.0.0.1:9443/detect `
  --detector-token $env:DETECTOR_TOKEN
```

The detector response is nested under the
ground-station response's `detector` property. The detector must not be used
as a replacement for signature, freshness, or replay verification.

For forensic analysis, add `--detector-include-quarantine`. This sends a
quarantined payload with `"trusted": false` and `"analysis_only": true`.
The detector must not treat that payload as authenticated or release it as
trusted data.

## 4. How a sender connects

The sender opens one TCP connection per tile and sends this big-endian frame:

```text
4-byte header length | 4-byte payload length | UTF-8 JSON header | raw payload
```

The payload is exactly `13 * 256 * 256 * 2` bytes: a C-order `uint16` array
with shape `(13, 256, 256)`. The JSON header contains a signed manifest and
256 block hashes. The complete field and hashing contract is in
[RASPBERRY_PI_TEAM_README.md](./RASPBERRY_PI_TEAM_README.md).

The station replies with one newline-terminated JSON object. Important fields
include `decision`, `reason`, `failed_blocks`, `tampered_pixel_count`, and
`retransmit_requested`.

## 5. Safe attacker/intermediary exercise

Only run these tests against your local station or an explicitly authorized
isolated test network. Do not intercept or modify third-party, production, or
Internet traffic.

1. Start the station on `127.0.0.1:9000`.
2. Use a test sender that creates a valid signed tile using the private key
   belonging to `keys/pi.key.pub`; never copy that private key into an attacker
   tool or production environment.
3. For an in-transit/post-signing test, modify a payload byte or manifest after
   signing and forward the frame to `127.0.0.1:9000`. Expected result:
   `QUARANTINE`, `REJECT_MALFORMED`, or `REJECT_REPLAY`, with no unverified tile
   sent to the model.
4. For a replay test, send the same valid frame twice with the same counter.
   The second response should be `REJECT_REPLAY`.
5. For a pre-signing/source-compromise simulation, change the tile first, then
   recompute its hashes and sign it with the test source key. Cryptography will
   accept the packet; semantic detection and the ground-truth label must then
   be handled by the model/dashboard layer.

An intermediary should be implemented as a test-only TCP relay that forwards
bytes unchanged or applies one controlled mutation before forwarding. Keep it
on loopback, bound it to a test port, and remove it after the exercise. The
wire-level attack positions and expected outcomes are documented in
[ATTACK_TEAM_CONTRACT.md](./ATTACK_TEAM_CONTRACT.md).

## 6. Security and operational notes

- Keep `keys/pi.key.pub` and the replay state directory readable/writable only
  by the service account.
- Use mutual TLS in deployed environments with `--tls-cert`,
  `--tls-key`, and `--tls-client-ca`.
- Use a unique, strictly increasing counter for every source; do not retry a
  frame by reusing a counter after an ambiguous delivery.
- Treat `SALVAGE` as masked/partial data, not a clean model input.
- The dashboard/backend owns durable imagery, decisions, and attack labels.
