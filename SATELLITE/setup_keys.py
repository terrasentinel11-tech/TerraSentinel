from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
root=Path(__file__).resolve().parent/'keys'
root.mkdir(exist_ok=True)
priv=root/'satellite_private.key'
pub=root/'satellite_public.key'
if priv.exists() or pub.exists():
    raise SystemExit('Keys exist. Not overwriting: ensure the public key matches the private key.')
k=Ed25519PrivateKey.generate()
priv.write_bytes(k.private_bytes(serialization.Encoding.Raw,serialization.PrivateFormat.Raw,serialization.NoEncryption()))
pub.write_bytes(k.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw))
print('Key pair created. Copy ONLY keys/satellite_public.key to Ground Station as keys/pi.key.pub. Do not share private key.')
