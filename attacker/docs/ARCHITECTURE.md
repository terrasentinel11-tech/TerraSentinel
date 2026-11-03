# Technical Design: Clean V3 Alpha

- `raster.py`: read arrays and metadata, opt-in 13-band profiles, exact source SHA256, matching GeoTIFF export.
- `analysis.py`: RGB/NDVI features and candidate SLIC / SciPy segmentation. Segments are **candidate image regions**, not verified agricultural boundaries.
- `attacks.py`: separately registered attack methods. Spatial replacement is a donor-copy operation with measurable content change, not a semantic generative model.
- `engine.py`: manual or heuristic auto recommendation and execution. The manually selected method is never silently replaced. Real altered pixel mask computed by raster difference.
- `visuals.py`: identical RGB stretch for original and attacked, 3-panel preview with exact changes, difference map.
- `dataset.py`: recursive scan, selected attack whitelist, optional quotas, failure accounting, resumable successful runs, original copied byte-for-byte, private NPZ/JSON annotations outside image folders.
- `cli.py`: scan/run/build/make-demo.
- `app.py`: single image lab, small batch frontend, catalog.

**Milestones:** (1) verified input profiles + failure diagnostics; (2) improve scene segmentation using trusted parcel polygons; (3) physically constrained atmospheric/agrarian methods; (4) legitimate multi-date and S1 cross-sensor experiments; (5) optional generative image synthesis; (6) independent held-out testing with the team detector.

Research ground-truth expectations: `selected_mask` covers intended edit region; `changed_mask` is actual band-level differences. For metadata-only experiments there are no changed raster samples. Two metadata state descriptors and their values are recorded instead.

The default attack scoring is a **heuristic compatibility rank**, not a calibrated confidence score or proof of realism. No generative AI model has been installed or claimed.
