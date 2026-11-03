"""Independent satellite transmitter, compatible with ground_station/server.py."""
import argparse
import hashlib
import json
import socket
import struct
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parent


def read_image(path):
    if path.suffix.lower() == '.npy':
        arr = np.load(path, allow_pickle=False)
    elif path.suffix.lower() in ('.tif', '.tiff'):
        try:
            import rasterio
        except ImportError as exc:
            raise RuntimeError('Install rasterio: python -m pip install -r requirements.txt') from exc
        with rasterio.open(path) as src:
            arr = src.read()
    else:
        raise ValueError('Only .tif, .tiff and .npy supported')
    if arr.shape != (13, 256, 256) or arr.dtype != np.uint16:
        raise ValueError(f'{path.name}: expected 13x256x256 uint16; got {arr.shape}, {arr.dtype}. No implicit conversion is performed.')
    return np.ascontiguousarray(arr)


def block_hashes(arr):
    leaves = []
    for y in range(0, 256, 16):
        for x in range(0, 256, 16):
            leaves.append(hashlib.sha256(np.ascontiguousarray(arr[:,y:y+16,x:x+16]).tobytes()).hexdigest())
    return leaves


def merkle_root(leaves):
    current = [bytes.fromhex(h) for h in leaves]
    while len(current) > 1:
        if len(current) % 2: current.append(current[-1])
        current = [hashlib.sha256(current[i] + current[i+1]).digest() for i in range(0, len(current), 2)]
    return current[0].hex()


def next_counter():
    counter_file = ROOT/'counter.txt'
    previous = int(counter_file.read_text()) if counter_file.exists() else 0
    counter = max(previous + 1, time.time_ns())
    counter_file.write_text(str(counter))
    return counter


def send_file(path, config, tamper=False):
    arr = read_image(path)
    leaves = block_hashes(arr)
    counter = next_counter()
    manifest = dict(tile_id=f'{path.stem}-{counter}', source=config['satellite_id'], counter=counter, ts=time.time(), shape=[13,256,256], dtype='uint16', root=merkle_root(leaves), urgency='routine', deadline_s=180.0)
    priv = Ed25519PrivateKey.from_private_bytes((ROOT/'keys'/'satellite_private.key').read_bytes())
    canonical = json.dumps(manifest, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    header = dict(manifest=manifest, sig=priv.sign(canonical).hex(), leaves=leaves)
    if tamper:
        arr = arr.copy()
        arr[:,20:36,20:36] ^= np.uint16(255)
    payload = arr.tobytes(order='C')
    hb = json.dumps(header, separators=(',', ':')).encode()
    frame = struct.pack('>II', len(hb), len(payload)) + hb + payload
    with socket.create_connection((config['ground_station_ip'], int(config['ground_station_port'])), timeout=10) as conn:
        conn.settimeout(20)
        conn.sendall(frame)
        reply = bytearray()
        while b'\n' not in reply:
            part = conn.recv(65536)
            if not part: break
            reply.extend(part)
            if len(reply) > 1024*1024: raise ValueError('Reply too long')
    if not reply: raise ConnectionError('Ground Station closed connection without response')
    result = json.loads(reply.split(b'\n',1)[0])
    record = dict(time=datetime.now(timezone.utc).isoformat(), image=path.name, counter=counter, result=result)
    with (ROOT/'logs'/'transmissions.jsonl').open('a', encoding='utf8') as f: f.write(json.dumps(record)+'\n')
    print(f'{path.name}: {result.get("decision", "NO_DECISION")} — {result.get("reason", "")}')
    return result


def main():
    parser = argparse.ArgumentParser(description='Standalone satellite TCP image transmitter')
    parser.add_argument('--config', default=str(ROOT/'config.json'))
    parser.add_argument('--image', help='Send one .tif/.tiff/.npy file')
    parser.add_argument('--folder', help='Send all supported images inside a folder')
    parser.add_argument('--loop', action='store_true', help='Repeat folder transmission until Ctrl+C')
    parser.add_argument('--tamper', action='store_true', help='Lab test only: alter signed pixels in transit')
    args=parser.parse_args()
    config=json.loads(Path(args.config).read_text(encoding='utf8'))
    folder=Path(args.folder) if args.folder else ROOT / config['dataset_folder']
    interval=max(float(config.get('interval_seconds',5)),0)
    if args.image: files=[Path(args.image)]
    else:
        if not folder.is_dir(): parser.error(f'Dataset folder not found: {folder}')
        files=sorted(p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in ('.tif','.tiff','.npy'))
    if not files: parser.error('No .tif/.tiff/.npy images found')
    try:
        while True:
            for i,p in enumerate(files):
                try: send_file(p, config, args.tamper)
                except (OSError, ValueError, RuntimeError, ConnectionError) as exc: print(f'ERROR {p.name}: {exc}')
                if i<len(files)-1 or args.loop: time.sleep(interval)
            if not args.loop: break
    except KeyboardInterrupt: print('\nSatellite stopped.')

if __name__=='__main__': main()
