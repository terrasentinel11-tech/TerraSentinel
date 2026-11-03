# Securing the Earth Observation Chain

This repository is a research prototype for testing the integrity of an Earth
observation data chain. It creates controlled, synthetic modifications of
authorized satellite-image copies, verifies tile provenance and integrity at a
ground station, and invokes a detector only after the trust mechanism releases
the data. The prototype is not an operational satellite system and does not
intercept real-world traffic.

## What the prototype does

- Preprocesses and validates multispectral GeoTIFF inputs.
- Generates reproducible spatial, spectral, atmospheric, sensor, and metadata
  attack proxies on copies of the input.
- Verifies Ed25519 signatures, Merkle roots, freshness, replay counters, and
  16x16 payload blocks.
- Provides an embedded detector adapter and produces manifests, previews, and
  metrics for experiments.
- Keeps the existing Web Attacker and Web Defender dashboards available in their
  original directories.

## Track addressed

It addresses the **secure Earth-observation data-chain / red-team and
defensive integrity** track: detecting manipulation between the satellite,
transport, ground station, and downstream detector while preserving a
reproducible evidence trail.

## Dataset

The intended multispectral source is **SEN12MS-CR**, using extracted Sentinel-2
13-band GeoTIFF scenes. The toolkit also supports a documented EuroSAT 13-band
profile and synthetic demo rasters. Confirm the dataset's radiometric scale
before using scale-dependent attacks; `--assume-scale` is an experimental
assumption, not proof of calibration. No dataset is bundled in this repository.

## Layout

```text
README.md
ground station all/requirements.txt
src/
  preprocessing.py
  pipeline.py
experiments/
  standard_attack.py
  evasion_test.py
  evaluate.py
configs/experiment.yaml
results/                    # model outputs and generated previews
results/figures/
ground station all/
  requirements.txt
  ground_station/
  tests/
docs/architecture.md
docs/experiment_protocol.md
attacker/                 # existing authorized red-team implementation
ground station all/
SATELLITE/
Web Attacker/
Web Defender/
```

## Install dependencies

From the repository root on Windows:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r "ground station all\requirements.txt"
```

Run the tests with:

```powershell
Push-Location "ground station all"
..\.venv\Scripts\python.exe -m pytest -q
Pop-Location
```

## Execute the pipeline

Use an authorized local GeoTIFF copy:

```powershell
.\.venv\Scripts\python.exe experiments\standard_attack.py `
  --input "D:\DATA\scene.tif" `
  --output results\standard_attack
```

The command writes `attacked.tif`, `preview.png`, and `manifest.json`.

## Reproduce the standard attack

The default standard attack is a deterministic `cloud_injection` proxy with
seed `42`. Select another supported attack explicitly when required:

```powershell
.\.venv\Scripts\python.exe experiments\standard_attack.py `
  --input "D:\DATA\scene.tif" `
  --attack cloud_injection `
  --seed 42
```

To inspect compatible attack candidates without generating an output:

```powershell
.\.venv\Scripts\python.exe experiments\evasion_test.py `
  --input "D:\DATA\scene.tif"
```

All attacker operations are for authorized, offline research copies. The
existing `attacker/README.md` and red-team runbooks contain the detailed
scenario rules and expected defensive outcomes.

## Reproduce the evaluation

Evaluate the generated manifest:

```powershell
.\.venv\Scripts\python.exe experiments\evaluate.py `
  --model-metrics "D:\MODEL_OUTPUT\metrics.json"
```

Metrics must be emitted by the trained detector/model. The evaluation helper
only reads and displays that model output; it does not calculate or create a
replacement metrics file.

For transport and ground-station scenarios, follow the protocol in
`ground station all/README.md` and
`docs/experiment_protocol.md`. Only use loopback or an explicitly authorized
isolated test network.

## Results

Generated attack artifacts are placed under `results/standard_attack/` by the
example commands. Model-produced metrics remain wherever the model writes
them; visualizations belong in `results/figures/`. Generated files are
intentionally not treated as scientific ground truth: inspect the TIFF bands
and manifests, not only the PNG preview.

## Web applications

The existing role-specific web applications remain unchanged:

- `Web Attacker/`: attacker-side experiment interface.
- `Web Defender/`: defender-side command-center interface.

Install and run each application from its own directory with `npm install` and
`npm run dev`. These dashboards must use the same authorization and local-lab
rules as the Python experiments; they are not a license to target external
systems.
