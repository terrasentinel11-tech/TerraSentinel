# Experiment Guide

## Safety prerequisites

1. Work on the `red-team-integration` branch.
2. Run only on owned laboratory machines and images.
3. Begin offline. Do not configure a network target until offline tests pass.
4. Use loopback or an explicitly allowlisted private laboratory address and port.
5. Generate a dedicated Ed25519 test keypair for pre-sign experiments. Do not use or copy the Satellite private key.
6. Start an isolated Ground Station instance with a separate replay-state file and the matching test public key.
7. Keep the production/team receiver stopped or on a different port during destructive protocol tests.

## Establish a baseline

From `attacker/`:

```powershell
python -m pip install -e ".[test]"
python -m pytest -q
```

From the Ground Station directory:

```powershell
python -m pytest -q
```

Record the exact Git commit, Python version, dependency versions, OS, CPU architecture, and byte order. A test-suite pass is not a hardware/Wi-Fi result.

## Validate an input scene

The integration input must be exactly 13×256×256 `uint16`. Confirm the real band order and radiometric scale from dataset provenance. Do not infer Sentinel-2 band semantics from a file having 13 bands.

Use BLACK PIXEL's scan command for inspection:

```powershell
python -m black_pixel_agri.cli scan --input "C:\lab\images" --limit 10
```

For scale-dependent attacks, supply `--assume-scale` only when the value is documented. The flag records an assumption; it does not independently verify calibration.

## Offline image experiment

Run the existing engine first:

```powershell
python -m black_pixel_agri.cli run `
  --input "C:\lab\images\tile.tif" `
  --output "C:\lab\offline-result" `
  --attack cloud_injection `
  --coverage regional `
  --level balanced `
  --seed 42 `
  --profile sen12ms-cr
```

Verify that the source SHA-256 is unchanged and inspect the attacked TIFF, preview, manifest, and actual-change mask. This demonstrates image generation only; it is not a Ground Station result.

## Controlled receiver setup

Run the receiver on loopback for development, using a dedicated key and state file:

```powershell
python -m ground_station.server `
  --host 127.0.0.1 `
  --port 19000 `
  --pub-key "C:\lab\keys\red-team-test.pub" `
  --state-file "C:\lab\state\red-team-replay.json"
```

Do not expose the receiver on all interfaces merely for convenience. If two physical machines are required, use a private allowlisted address, restrict the firewall source, and record the topology.

## Red Team controller

Offline frame generation is the default. It uses an ephemeral laboratory key and writes an evidence bundle without contacting a receiver:

```powershell
python -m red_team.cli `
  --image "C:\lab\images\tile.tif" `
  --attack cloud_injection `
  --zone satellite `
  --scenario pre_sign_attack `
  --profile sen12ms-cr `
  --coverage regional `
  --level balanced `
  --seed 42 `
  --output "C:\lab\evidence"
```

For an authorized live loopback test, explicitly opt in, provide the dedicated raw 32-byte test key, and repeat the destination in the allowlist:

```powershell
python -m red_team.cli `
  --image "C:\lab\images\tile.tif" `
  --attack cloud_injection `
  --zone in_transit `
  --scenario post_sign_alter `
  --execute `
  --host 127.0.0.1 `
  --port 19000 `
  --allow-host 127.0.0.1 `
  --lab-private-key "C:\lab\keys\red-team-test.key" `
  --output "C:\lab\evidence"
```

Implemented scenario names are `clean`, `post_sign_alter`, `payload_replacement`, `manifest_alter`, `replay`, `incomplete`, `malformed_header`, `invalid_declared_size`, `delayed_transmission`, `unexpected_termination`, and `pre_sign_attack`. Use `--zone satellite`, `--zone in_transit`, `--zone ground_station`, or `--zone combined`; invalid zone/scenario combinations are rejected before execution.

## Scenario execution order

Execute in this order so that failures are attributable:

1. Clean signed frame.
2. One post-sign payload byte/block mutation.
3. Whole payload replacement while preserving the signed envelope.
4. Exact replay of a previously accepted frame.
5. Malformed header and invalid declared length.
6. Truncation and unexpected termination.
7. Delayed/chunked transmission around the 10-second deadline.
8. Pre-sign BLACK PIXEL manipulation with the laboratory signer.

Use a new receiver replay-state file for an independent campaign, not to hide an unexpected replay result. Within one campaign, preserve state.

## Expected-result discipline

Define the expected result before execution. Examples:

- Post-sign pixel corruption: at least one failed block and `QUARANTINE` for routine urgency.
- Replay: first delivery `ACCEPT`, second `REJECT_REPLAY`.
- Pre-sign manipulation: cryptographic `ACCEPT`; semantic-detector outcome recorded separately or `not_configured`.
- Truncation: no accepted tile. Absence of a response is expected if the client deliberately closes its write/read channel.

Never convert an exception, missing response, or mock dashboard value into an `ACCEPT`/`DETECTED` claim.

## Hardware demonstration checklist

- Confirm PC/Raspberry Pi clocks are synchronized.
- Confirm both hosts use the recorded byte order.
- Confirm the public key fingerprint before starting.
- Confirm the Ground Station IP/port is inside the approved allowlist.
- Confirm no port forwarding or public exposure exists.
- Run a clean frame before every attack group.
- Preserve Satellite JSONL logs, Ground Station output, and Red Team evidence.
- Record packet loss and Wi-Fi interruptions as environmental errors, not security detections.
- Stop the isolated receiver and archive its replay state after the demonstration.

