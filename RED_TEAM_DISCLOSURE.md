# Red Team Disclosure & Rules of Engagement

**From:** Attacker team · **To:** Defender team (Ground Station / Satellite)
**Scope:** authorized MITM downlink exercise on our private lab LAN only.

This answers, point by point, what the defender team asked for before the run.

## 1. Test key — public only, with fingerprint (no private key)

We share **only** the red-team lab **public** key. The private key never leaves
the attacker machine (`lab-keys/`, git-ignored).

| | |
|---|---|
| File in repo | `ground station all/keys/redteam_lab.key.pub` |
| Raw key (32-byte Ed25519 identity, hex) | `51bcd78aabb8b4812b3499755b3d4624b28e18950d7ce4a148f3ada1c088f24c` |
| SHA-256(public key) fingerprint | `4edb958b54dfb90ec94f21448d76e4671bf0d8d88dbad2f937e9dd9d7b708dcd` |

Verify before trusting it:
```powershell
python -c "import hashlib,pathlib;b=pathlib.Path('keys/redteam_lab.key.pub').read_bytes();print(len(b),b.hex());print(hashlib.sha256(b).hexdigest())"
```
The two values must match the table above.

## 2. Proxy endpoint, test window, network confinement

| | |
|---|---|
| Attacker proxy (intercept point) | `172.18.138.216:9100` |
| Forwards to your Ground Station | `172.18.138.207:9000` |
| Satellite (sender) | `172.18.138.68` |
| Test window | **_<fill in: date + start–end time>_** |

Confinement: the proxy only accepts from, and only connects to, the private LAN
addresses above. No hostnames, no public destinations, no packet capture or ARP
spoofing — the Satellite is explicitly pointed at the proxy. Outside this window
the proxy is stopped.

## 3. Test images and expected change

Synthetic test tiles only (e.g. `pair_000005`, `pair_000014`, `pair_000015`
from the pilot dataset / `synthetic_farms.tif`). Each is a 13×256×256 uint16 tile.

Expected manipulation per proxy mode:

| mode | what we do to the image | you should see |
|---|---|---|
| `observe` | nothing (forward as-is) | `ACCEPT`, image identical to original |
| `tamper` | flip a small block of payload bytes | `QUARANTINE`, a few blocks fail |
| `substitute` | apply a BLACK PIXEL attack (default `cloud_injection`, ~20–21k pixels changed) then re-sign with the lab key | `ACCEPT` (if you trust the lab key), image visibly altered vs original |
| `replay` / `drop` | resend / truncate | `REJECT_REPLAY` / `REJECT_MALFORMED` |

You keep the original tiles, so you can diff the received tile against the
original to see exactly what changed.

## 4. Test logs we will provide

After the run we send you:

- **Attacker proxy log** `attacker/mitm_log.jsonl` — one JSON line per image:
  `time` (UTC), `index`, `from` (sender IP), `tile_id`, `mode`, `attack`,
  `edited_px`, and the Ground Station `decision`.
- **Image count** and the **per-image station decision** (summarised from the log).
- Your own `SATELLITE/logs/transmissions.jsonl` and the Ground Station logs are
  the independent cross-check.

## 5. Stop and revert procedure

To stop the exercise and return to the normal service:

1. **Attacker:** `Ctrl+C` the proxy (`mitm_proxy.py`). Nothing else listens.
2. **Satellite:** set `SATELLITE/config.json` `ground_station_ip` back to
   `172.18.138.207` and `ground_station_port` back to `9000`.
3. **Ground Station:** restart with your **normal** key:
   `python -m ground_station.server --host 0.0.0.0 --port 9000` (default
   `keys/pi.key.pub`) — drop the `--pub-key keys/redteam_lab.key.pub` override.

After these three steps the legitimate Satellite→Ground chain is fully restored;
the lab key is no longer trusted.

## 6. Separation and no real data

- The test key is a **separate file** (`redteam_lab.key.pub`), never your
  operational `pi.key.pub`. Trusting it is a one-flag, reversible override.
- Test settings live in separate files (`attacker/mitm_config.json`,
  `attacker/attacker_config.json`) — the normal service config is untouched.
- **Synthetic / test imagery only.** No real Sentinel-2 scenes or any production
  data are used in this exercise.
- No private key is ever shared or committed; `.gitignore` blocks all private
  keys, runtime images, logs, counters and state.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
