# Experiment Results Guide

## Required evidence bundle

The current controller creates a unique directory containing:

```text
<experiment_id>/
  report.json
  original_tile.npy
  attacked_tile.npy
  actual_change_mask.npy
```

`report.json` contains the source/modified hashes in embedded attack metadata, experiment configuration, expected result, receiver response when executed, runtime, and current defense status. The three NPY artifacts are shape/dtype validated before writing, and the JSON report is finalized with an atomic replacement.

For a jury campaign, preserve the controller bundle unchanged and add, rather than overwrite, raw Satellite/Ground Station logs and a human-reviewed summary. Desirable future additions are separate event JSONL, receiver-response JSON, component-specific commit IDs, and a generated Markdown report.

## Mandatory experiment fields

- Schema version and experiment ID.
- UTC recorded timestamp and measured runtime; future schema versions should add explicit start/end timestamps.
- Target component and scenario.
- Git commit IDs for Red Team, Satellite, and Ground Station code.
- Configuration with secrets redacted.
- Input path/reference, shape, dtype, band profile, and calibration basis.
- BLACK PIXEL attack, coverage, severity, seed, and full attack manifest.
- Original and modified SHA-256.
- Actual changed-pixel count and mask path.
- Mutation position: `none`, `pre_sign`, or `post_sign`.
- Endpoint or `offline`; never include private-key bytes.
- Expected result defined before execution.
- Actual receiver response and detector response, if any.
- Runtime and relevant errors/logs.
- Machine-readable status and human-readable conclusion.

## Status vocabulary

Use exactly one primary outcome:

- `MANIPULATION_CREATED`: BLACK PIXEL produced measurable intended output; no receiver claim.
- `TAMPERING_ACCEPTED`: a post-sign malicious mutation was accepted and released unchanged.
- `TAMPERING_REJECTED`: receiver rejected/quarantined a post-sign mutation as expected.
- `ACCEPTED_SUSPICIOUS_IMAGE`: a pre-sign manipulated image passed crypto; semantic outcome absent or suspicious.
- `SEMANTIC_DETECTION_REPORTED`: an actual configured detector returned a documented detection result.
- `CLEAN_BASELINE_ACCEPTED`: valid unmodified frame accepted.
- `TEST_FAILED`: harness/setup assertion failed before a trustworthy security result.
- `UNDETERMINED`: evidence is incomplete, ambiguous, or the receiver response was unavailable.

Do not label a crypto-valid pre-sign test as `TAMPERING_ACCEPTED`; cryptography authenticated the bytes it was asked to authenticate.

## Defense assessment

Record defense status independently from experiment execution:

- `PREVENTED`: malicious content was not released through the tested path.
- `DETECTED_NOT_PREVENTED`: receiver/detector flagged it but still released data.
- `NOT_DETECTED`: tested malicious content was accepted without the relevant warning.
- `NOT_APPLICABLE`: offline image generation or no relevant defense exists.
- `NOT_CONFIGURED`: optional detector/TLS component was absent.
- `UNDETERMINED`: insufficient evidence.

## Report structure

Every `report.md` should contain:

1. Objective and authorization boundary.
2. Exact input and code versions.
3. Scenario and mutation position.
4. Expected result and success criterion.
5. Actions performed by the harness.
6. Actual raw receiver/detector result.
7. Hash/mask comparison.
8. Runtime and environment.
9. Outcome and defense assessment.
10. Limitations and reproducibility command/config reference.

## Scientific and presentation rules

- Report counts and timings from recorded execution only.
- Preserve raw responses; summaries must be derivable from them.
- Treat BLACK PIXEL agronomic/cloud outputs as synthetic proxies.
- Do not call scene-derived segments cadastral parcels.
- Do not claim model evasion from visual inspection.
- Report detector absence as `NOT_CONFIGURED`, not zero false negatives.
- Separate simulated/software-loopback, LAN, and Raspberry Pi hardware results.
- Never merge mock web-dashboard metrics into experiment evidence.

## Jury-ready campaign summary

Aggregate only completed, schema-valid experiments. Group by attack, mutation position, and receiver decision. Include denominators and exclusions. Report median and tail latency only when sample size is disclosed. Link every aggregate cell to experiment IDs so reviewers can inspect its inputs, response, mask, and logs.

Recommended final tables:

- Clean baseline reliability.
- Post-sign integrity/replay/malformed-frame outcomes.
- Pre-sign image attack crypto outcomes.
- Semantic detector outcomes, if implemented.
- Runtime and resource overhead.
- Unsupported attacks and unresolved tests.

