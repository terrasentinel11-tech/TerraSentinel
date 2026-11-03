# BLACK PIXEL AGRI V3 — Clean Rebuild (Experimental Alpha)

**Independent Python research toolkit** for controlled modifications of agricultural satellite image *copies*. It does not connect to satellites or ground stations. This is a **new codebase**; it does not overwrite V1/V2.

## What works in this alpha

- **Automatic Attack Lab**: analyzes uploaded images and selects a compatible attack without a manual chooser.
- **Automatic Dataset Forge**: enables all 13 methods, selecting one compatible attack per input source.
- The Python API/CLI retains manual method selection for reproducible research tests.
- **Coverage**: local / regional / global where supported, with an automatic coverage default.
- **Intensity**: subtle / balanced / strong / extreme / expert / auto. Expert is a *configuration*, not guaranteed realism or evasion.
- **13 experimental transformations**: content patch replacement, copy-move cloning, vegetation-stress proxy, recovery proxy, harvested-soil proxy, optical cloud insertion, cloud-shadow proxy, haze proxy, scanline corruption, NIR-only perturbation, band misregistration, calibration-gain modification, and metadata-only georeference shift.
- **Visualization**: ORIGINAL | ACTUAL ATTACK REGION | ATTACKED, plus numerical difference map and private actual-change masks.
- **Dataset Forge Option A**: `pair_000001_original.tif`, `pair_000001_attacked.tif`, `pair_000001_preview.png` in the *executed attack's folder*, `dataset_summary.csv`, `skipped.csv`, `dataset_report.json`, resumable with configuration checking.
- **Preserves original source files** (the output includes an exact source copy); GeoTIFF bands, data type and georeferencing are preserved except in an explicitly geospatial experiment.
- **CLI** for large datasets, **Streamlit** for single-image trials and small batches.

**Not yet included:** GAN/diffusion inpainting, verified parcel boundaries, SAR modifications, temporal-series replay, advanced adaptive evasion, full physical cloud radiative transfer, full multi-stage attack composition. No scientifically verified photorealism claims. The scene-derived segments are *not cadastral parcel masks*. No real 10,000-image dataset has been generated here.

## Windows setup (Python 3.12)

Open PowerShell in the extracted project directory. Python 3.12 is recommended due to binary-wheel compatibility on Windows.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[ui,test]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Or use `SETUP_WINDOWS.ps1` followed by `START_APP_WINDOWS.ps1` (may require `Set-ExecutionPolicy -Scope Process Bypass`). **Always start Streamlit using the venv executable**, not a system-wide `streamlit` command.

The core project does not require `scikit-image`. If installed, it uses SLIC candidate segmentation; otherwise a SciPy fallback is used. This avoids the previous `ModuleNotFoundError: skimage` failure on machines without that optional package.

## First test, no dataset needed

```powershell
.\.venv\Scripts\python.exe -m black_pixel_agri.cli make-demo --output examples\synthetic_farms.tif
.\.venv\Scripts\python.exe -m black_pixel_agri.cli run --input examples\synthetic_farms.tif --attack cloud_injection --coverage regional --output my_first_attack
```

Open `my_first_attack/preview.png`. The original is a **synthetic test raster**, not a real Sentinel-2 scene.

## Full inspection on your image

**Known** EuroSAT 13-band provenance (requires user confirmation of its real source):

```powershell
.\.venv\Scripts\python.exe -m black_pixel_agri.cli run --input "D:\DATA\AnnualCrop_2.tif" --profile eurosat --attack field_patch_replacement --output test_result
```

For a spectral trial, add `--assume-scale 10000` **only if you explicitly accept a research-only DN denominator and understand this does not verify physical calibration**. Unlabeled 13-band TIFFs cannot be used for spectral operations with `--profile auto`.

## SEN12MS-CR integration

1. Extract the desired `*_s2` `.tar.gz` archives completely. Do **not** give the CLI `.tar.gz` paths.
2. Inspect them first; the dataset contains multiple land-cover classes, not just agriculture.
3. Use `--profile sen12ms-cr` only when these are truly the intended Sentinel-2 13-band files.
4. Confirm radiometric scale and processing level from the actual archive/source documentation before using a scale-dependent experiment. `--assume-scale 10000` is an experimental assumption, not an independent verification.

```powershell
.\.venv\Scripts\python.exe -m black_pixel_agri.cli scan --input "D:\SEN12MS\ROIs1158_spring_s2" "D:\SEN12MS\ROIs1868_summer_s2" --limit 5
```

## Generate a 20-pair pilot, then 10K

**First, test with 20 valid source scenes.** Use quotes around paths containing spaces.

```powershell
.\.venv\Scripts\python.exe -m black_pixel_agri.cli build `
  --input "D:\SEN12MS\ROIs1158_spring_s2" "D:\SEN12MS\ROIs1868_summer_s2" `
  --output "D:\BLACK_PIXEL_DATASET_10K" `
  --total 20 `
  --profile sen12ms-cr `
  --selection auto `
  --attacks cloud_injection,field_patch_replacement,atmospheric_haze
```

Only when the pilot is validated, repeat with `--total 10000` using **identical settings**, output path and seed: the generator resumes completed items. It **does not automatically turn unverified scenes into agricultural fields**. Curate or independently classify agricultural source scenes before final delivery.

To generate only one chosen attack per input:

```powershell
.\.venv\Scripts\python.exe -m black_pixel_agri.cli build --input "D:\IMAGES" --output "D:\DATASET_CLOUD" --total 100 --selection manual --attacks cloud_injection
```

Optional quotas (for auto selection):

```powershell
  --quotas '{"cloud_injection":5000,"field_patch_replacement":5000}'
```

If a campaign is already present, **changing attacks/profile/seed or quotas requires a new output folder**. The target number can be increased while preserving consistent settings.

## Dataset structure

```text
BLACK_PIXEL_DATASET_10K/
├── cloud_injection/
│   ├── pair_000001_original.tif
│   ├── pair_000001_attacked.tif
│   └── pair_000001_preview.png
├── field_patch_replacement/
│   ├── pair_000002_original.tif
│   ├── pair_000002_attacked.tif
│   └── pair_000002_preview.png
├── private_ground_truth/
│   ├── pair_000001_masks.npz
│   └── pair_000001_manifest.json
├── campaign_config.json
├── dataset_summary.csv
├── skipped.csv
└── dataset_report.json
```

Only attack folders with successfully generated samples appear. A completed 10K run will produce **10,000 pairs = 20,000 TIFF + 10,000 previews**. If not enough scenes are suitable, the report states the actual count. Image pairs are intended for authorized defensive benchmarking; use independent scene/geographic splits when training detectors to avoid leakage.

## Essential scientific constraints

- The RGB `preview.png` is **not** the multispectral scientific result. Inspect the TIFFs and band-wise changes.
- `Actual Attack Region` is derived from actual band-level raster differences, *not* a guess about crop parcel boundaries. A georeference-only attack has **zero changed pixels** and is annotated as metadata-only.
- Cloud and agronomic effects are **synthetic proxies**, not physically certified simulation or proof of drought/irrigation.
- Never claim a detector was evaded from appearance alone; independent evaluation is required.
- A SHA-256 over an image helps verify bit-for-bit equality with a **trusted reference**; a raw hash alone does not establish real-world truth.


## Automatic Streamlit edition

In Attack Lab, upload a TIFF and click **Analyze and auto-generate attack**. The top-ranked compatible transformation is selected using scene heuristics. The existing three-panel preview and difference map show what changed.

Dataset Forge enables all 13 registered methods and automatic selection without manual controls. For old dataset campaigns made with a different allowlist, **choose a new output directory**; configuration mismatch checks intentionally prevent mixing campaigns. The CLI/API still accept manual attacks for reproducible tests.
