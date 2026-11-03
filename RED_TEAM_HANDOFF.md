# Red Team ↔ Defender Handoff

**Audience:** the Ground Station / Satellite (defender) team.
**Goal:** let the authorized Red Team attacker's signed tiles reach your Ground
Station so the full chain can be exercised end to end.

## TL;DR — no code change required

Your Ground Station already accepts a custom trusted key via `--pub-key`. To run
the source-compromise experiments you only need to **trust the Red Team's lab
public key on an isolated receiver instance**. Your operational `keys/pi.key.pub`
stays untouched.

## What was added to the repo

| File | Purpose | Secret? |
|---|---|---|
| `ground station all/keys/redteam_lab.key.pub` | Red Team lab **public** key (32 raw bytes) | No — safe to share/commit |
| `attacker/launch_attack.py` | attacker: fire one scenario or a full sweep | No |
| `attacker/attack_daemon.py` | attacker: wait for your server, attack dropped images | No |
| `attacker/attacker_config.json` | attacker: the two IPs + attack settings | No |

The attacker's **private** key lives only on the attacker machine under
`lab-keys/` (git-ignored) and is never shared.

Lab public key fingerprint (hex), for out-of-band verification:
```
51bcd78aabb8b4812b3499755b3d4624b28e18950d7ce4a148f3ada1c088f24c
```

## Defender steps

1. `git pull`.
2. Start a **dedicated test** Ground Station that trusts the Red Team identity
   (do **not** reuse your production key or port):
   ```powershell
   cd "ground station all"
   python -m ground_station.server --host 0.0.0.0 --port 9000 `
     --pub-key "keys/redteam_lab.key.pub"
   ```
   It prints `Ground station listening on ...` when ready.
3. Open inbound TCP 9000 **only** from the Red Team machine's LAN IP. Never
   expose it to the public internet.
4. Tell the Red Team your Ground Station IP. They put it in
   `attacker/attacker_config.json` as `ground_station_ip`.

## Expected results per scenario

| Scenario (attacker runs) | Your Ground Station should answer |
|---|---|
| `clean` | `ACCEPT` |
| `pre_sign_attack` | `ACCEPT` by crypto — the signature is valid; a **semantic detector** is what must flag it. This gap is the point of the exercise. |
| `post_sign_alter`, `payload_replacement` | `QUARANTINE` (block hashes fail) |
| `manifest_alter` | `QUARANTINE` / invalid signature |
| `malformed_header`, `invalid_declared_size` | `REJECT_MALFORMED` |
| `incomplete`, `unexpected_termination` | connection closed / EOF |
| `replay` | `ACCEPT` once, then `REJECT_REPLAY` |

## Optional — downlink interception (MITM) demo

To demonstrate that the signature protects the Satellite→Ground downlink, the
Red Team can run an in-path proxy (`attacker/mitm_proxy.py`). For this demo the
Satellite teammate temporarily points `SATELLITE/config.json`'s
`ground_station_ip` at the **proxy's** IP instead of the Ground Station. The
proxy forwards to the real Ground Station. Expected: unchanged frames `ACCEPT`,
but any tampered/replayed/truncated frame is `QUARANTINE` / `REJECT_REPLAY` /
`REJECT_MALFORMED` — the downlink defense holding. Revert the IP afterwards.

## Optional next milestone — close the pre-sign gap

`pre_sign_attack` is accepted because cryptography cannot see a compromised
source. To actually catch it, run your semantic detector and point the Ground
Station at it:
```powershell
python -m ground_station.server --host 0.0.0.0 --port 9000 `
  --pub-key "keys/redteam_lab.key.pub" `
  --detector-url "https://<your-detector-host>/analyze"
```
The Ground Station forwards only released tiles to that endpoint. Catching
`pre_sign_attack` there is the real win condition for the defender team.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
