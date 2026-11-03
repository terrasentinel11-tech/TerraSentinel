# Architecture

```text
GeoTIFF copy
    -> src/preprocessing.py
    -> src/pipeline.py
    -> ground station all/ground_station/
    -> results/
```

The original `attacker/`, `ground station all/`, `SATELLITE/`,
`Web Attacker/`, and `Web Defender/` directories remain available as role-specific
applications. The top-level `src/` package is the reproducible research facade:
it reuses the same attack, ground-station, cryptographic, and detector
implementations without requiring the web applications to be merged into the
Python pipeline. All defender Python, defender requirements, and defender
tests are kept together in `ground station all/`.
