# Experiment protocol

1. Use a local copy of a GeoTIFF and record its source and SHA-256 digest.
2. Select an attack in `configs/experiment.yaml`; do not modify the source.
3. Run the standard attack and retain the generated manifest, attacked copy, and preview.
4. Run evaluation only on generated artifacts and keep metrics in `results/`.
5. Treat all outputs as synthetic research data. Do not claim physical realism or detector evasion from appearance alone.
6. Run network attack scenarios only against the loopback laboratory ground station or a network for which explicit authorization exists.

The cryptographic trust mechanism runs before the detector. Invalid signatures,
replays, stale timestamps, or failed block hashes must never be treated as
authenticated model input.
