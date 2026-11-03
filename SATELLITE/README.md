# Satellite PC1 — standalone transmitter for Ground Station PC2

Prerequisites: Python 3.10+, both PCs on the same Wi-Fi/LAN or a configured private VPN.

## PC1 Satellite (PowerShell)
1. `cd "path\to\SATELLITE_PC1"`
2. `python -m pip install -r requirements.txt`
3. `python setup_keys.py` (run only once; never overwrite working keys)
4. Edit `config.json` to set the real IPv4 address of PC2.
5. Put genuine 13-band 256x256 uint16 GeoTIFF files in `images/`.
6. `python satellite.py` (all images once), or `python satellite.py --loop` (repeat every interval), or `python satellite.py --image "C:\path\tile.tif"` (one image).

## PC2 Ground Station
Copy ONLY `keys/satellite_public.key` from PC1 to `<project_root>/keys/pi.key.pub` on PC2. Never copy the private key to PC2. Ground Station also requires `config/defender_config.json` (create/preserve according to its existing project instructions).
From the parent folder containing `ground_station/`, start:
`python -m ground_station.server --host 0.0.0.0 --port 9000`
Windows Defender Firewall: allow inbound TCP port 9000 only from your private LAN. Never port-forward this demo receiver to the public internet without TLS/VPN and access controls.

## Troubleshooting / notes
- `ipconfig` on PC2 shows its IPv4 address.
- On PC1: `Test-NetConnection 192.168.1.20 -Port 9000` (replace example IP).
- `.tif` is read without spectral-band fabrication. Unsupported shapes/dtypes are rejected explicitly, not silently converted.
- Only pixel data and the cryptographic manifest are transmitted, not the entire GeoTIFF or its georeferencing metadata.
- `--tamper` alters the payload after it has been signed to test defender handling in a controlled lab.
- Sender initiates outgoing TCP; PC1 does not need to host a listening server.
- Logs are appended to `logs/transmissions.jsonl`; repeated transmissions use new counters.
