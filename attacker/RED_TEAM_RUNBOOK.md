# Red Team Attacker Runbook

Authorized lab use only. All destinations are loopback or an explicitly
allow-listed lab IP. No interception/MITM — the attacker sends its own
attacked copies to the defender's Ground Station.

## One-time setup

The lab private key already exists at `../lab-keys/lab_ed25519.key` (git-ignored).
To regenerate:
```powershell
python - << 'PY'
from pathlib import Path
from cryptography.hazmat.primitives import serialization as s
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
Path('../lab-keys').mkdir(exist_ok=True)
k = Ed25519PrivateKey.generate()
Path('../lab-keys/lab_ed25519.key').write_bytes(
    k.private_bytes(s.Encoding.Raw, s.PrivateFormat.Raw, s.NoEncryption()))
Path('../lab-keys/lab_public.key').write_bytes(
    k.public_key().public_bytes(s.Encoding.Raw, s.PublicFormat.Raw))
print('keys written to ../lab-keys/')
PY
```
Then share `../lab-keys/lab_public.key` with the defender team (see
`../RED_TEAM_HANDOFF.md`). Never share `lab_ed25519.key`.

## Mode A — fire specific attacks (launch_attack.py)

```powershell
python launch_attack.py --list
python launch_attack.py --scenario post_sign_alter --attack cloud_injection
python launch_attack.py --all          # full 11-scenario sweep with PASS/FAIL/INFO
```
Target defaults to `127.0.0.1:9000`. For a remote Ground Station, run a local
one for smoke tests, or use the daemon (Mode B) which reads the IP from config.

## Mode B — persistent attacker (attack_daemon.py)

1. Edit `attacker_config.json`:
   - `attacker_ip`       — this machine's LAN IP
   - `ground_station_ip` — the defender's Ground Station IP
   - `attacks`           — list applied round-robin to incoming images
   - `scenario`          — `pre_sign_attack` (source compromise) by default
2. Run it (waits until the server is up):
   ```powershell
   python attack_daemon.py
   ```
3. Drop `13x256x256 uint16` `.tif`/`.npy` images into `attack_inbox/`.
   Each is attacked and sent; the daemon prints one line per image:
   ```
   [attack image 1] field_a.tif   attack=cloud_injection     -> ACCEPT   [INFO]
   [attack image 2] field_b.tif   attack=fake_drought_proxy  -> QUARANTINE [PASS]
   ```
   `--once` does a single pass and exits.

## Mode C — man-in-the-middle the Satellite downlink (mitm_proxy.py)

Intercepts a cooperating Satellite PC's frames on the way to the Ground
Station. **Not** transparent interception: the Satellite is explicitly pointed
at this proxy (no ARP spoofing / packet capture), on machines you own.

1. Edit `mitm_config.json`:
   - `listen_port`              — the proxy's port on this machine (e.g. 9100)
   - `real_ground_station_ip/port` — the **real** Ground Station behind the proxy
   - `mode` — `observe` | `tamper` | `replay` | `drop`
2. Run it:
   ```powershell
   python mitm_proxy.py --mode tamper
   ```
3. Tell the Satellite teammate to set `ground_station_ip` in their
   `SATELLITE/config.json` to **this proxy's IP** (and port). When they send,
   the proxy prints one line per image:
   ```
   [intercepted image 1] synthetic_farms-...  mode=tamper  -> QUARANTINE
   ```

Expected Ground Station decisions (verified locally):

| mode | decision | meaning |
|---|---|---|
| `observe` | `ACCEPT` | interception works; frame forwarded unchanged |
| `tamper` | `QUARANTINE` | payload bytes flipped -> block hashes fail |
| `replay` | `ACCEPT , REJECT_REPLAY` | resend caught by the counter |
| `drop` | `REJECT_MALFORMED` | payload truncated |
| `substitute` | `ACCEPT`* | sender's real tile is extracted, attacked, and re-signed with the lab key |

A MITM **cannot** make a *tampered* frame `ACCEPT`: it has no access to the
Satellite's private key, so it cannot re-sign the satellite sender's manifest. That is the
point — the signature protects the downlink.

`substitute` is the exception, and it shows the real risk: the proxy takes the
sender's **actual image out of the intercepted payload**, applies a BLACK PIXEL
attack to it, and re-signs with the **Red Team lab key**. The Ground Station
`ACCEPT`s it *only if it trusts that lab key* (`--pub-key keys/redteam_lab.key.pub`,
i.e. a key-trust compromise). This is the "image reaches me, I bake the attack
in, re-send, and it passes" flow — verified end to end (the sender's tile accepted
with ~21k pixels altered). Prefer band-agnostic attacks here (`cloud_injection`,
`atmospheric_haze`, `scanline_stripes`, `field_patch_replacement`): only raw
pixels cross the wire, so spectral attacks needing B04/B08 provenance will fail.

## Reading verdicts

- `PASS`  — the defender responded correctly (accept clean / reject or quarantine an attack).
- `FAIL`  — the defender accepted tampered or malformed bytes (a real integrity miss).
- `INFO`  — `pre_sign_attack` was crypto-`ACCEPT`ed: expected, because only a
  semantic detector can catch a source compromise.

If signature-dependent scenarios (`clean`, `pre_sign_attack`, `replay`) come
back `QUARANTINE`, the Ground Station does not trust your lab public key yet —
the defender must start it with `--pub-key keys/redteam_lab.key.pub`.

## Evidence

Every run writes an immutable bundle under `red_team_evidence/<experiment_id>/`
(git-ignored): config, hashes, change mask, frame metadata, receiver response,
timing, and status.
