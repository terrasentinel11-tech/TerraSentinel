# Validation protocol

Run `python -m pytest -q` inside Python 3.12 project environment.

Acceptance:
- A deliberately selected method is never replaced automatically.
- Source SHA256 remains identical after any successful operation.
- `changed_mask == any(attacked_band != source_band) & valid_data` for pixel attacks.
- `georeference_shift` has 0 changed pixels and an altered affine transform.
- Output is identical shape/count/dtype/band order to original and same CRS (except intentionally altered transform).
- Manual operations reject missing bands, missing DN assumption, incompatible coverage or unsuitable target region.
- Batch creates original/attacked/preview per pair under the executed attack name.
- Original file copy has the same SHA256 as the trusted source.
- Repeated batch with same campaign config resumes without duplicate rows or overwriting outputs.
- A different campaign config cannot append to an existing output folder.

**Unproven:** true agricultural classification, real photorealism, multispectral radiation consistency under actual atmosphere, cross-sensor physical consistency, genuine production-grade 10K throughput, detector false-positive rate. These require independent data and experiments.
