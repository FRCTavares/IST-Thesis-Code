# P1.7 hard-negative lifecycle evidence

## Scope

This package validates Issue #18 hard-negative lifecycle provenance, duplicate merging, explicit trusted-continuity expiry, lifecycle diagnostics, and the evidence-backed canonical maximum age.

## Final configuration

- Baseline commit: `bc71088ca4639f6bc75af98a5589fb246c6bff5d`
- Lifecycle implementation commit: `dc64ad7e5129d5d171d3dfadd1652803f1211cdb`
- Canonical promotion commit: `6ba28c6133ff2e105ca6db4c17d0b0759c27b565`
- Canonical maximum age: `247` tracker frames
- Decay policy: `none_until_expiry`
- Safety tolerance: `0.05 s`
- Frozen sequences: May hard re-entry, Seq01 clean, Seq03 crossing, and Seq04 occlusion

Hard-negative appearance vectors remain at full strength. There is no vector decay or silent similarity weakening. A committed prototype may expire only during uninterrupted trusted `LOCKED -> LOCKED` continuity.

## Evidence-based age decision

The age-zero run first reproduced the validated P1.6 metrics exactly.

Observed committed-prototype age distributions produced the tested maximum ages `62`, `93`, `247`, `394`, and `427` tracker frames.

| Maximum age | Committed expiries | Maximum wrong-target increase | Correct duration delta | Lost duration delta | Decision |
|---:|---:|---:|---:|---:|---|
| 62 | 10 | +0.000 s | +0.000 s | +0.000 s | Safe but unnecessarily aggressive |
| 93 | 7 | +0.000 s | +0.000 s | +0.000 s | Safe but unnecessarily aggressive |
| 247 | 2 | +0.000 s | +0.000 s | +0.000 s | Promoted |
| 394 | 0 | +0.000 s | +0.000 s | +0.000 s | No-expiry control |
| 427 | 0 | +0.000 s | +0.000 s | +0.000 s | No-expiry control |

The `247`-frame candidate was the largest tested finite age that exercised committed expiry without degrading annotated-ID or spatial safety metrics.

## Repeatability

An independent `247`-frame run reproduced, on all four sequences:

- generated semantic digests;
- topic counts;
- source manifests;
- resolved runtime parameters;
- complete lifecycle payloads;
- expiry-event counts;
- annotated-ID metrics;
- spatial metrics.

After promotion into the committed canonical YAML, a final replay again matched the validated `247`-frame reference exactly.

## Validation

- Python suite: `238 passed, 1 skipped`
- ROS result set: `252 tests, 0 errors, 0 failures, 2 skipped`
- `thesis_bringup` package build: passed
- Live UI TypeScript project build (`tsc -b`): passed
- Live UI Vite production build: passed

The live UI validation uses the repository's `npm run build` contract, which executes `tsc -b && vite build`.

## Evidence inventory

- `canonical_manifest.tsv`: frozen source bags, annotations, target IDs, and annotation hashes
- `tim_mars_canonical.yaml`: promoted canonical configuration
- `decision/`: age-zero preservation, age distributions, finite-age sweep, deltas, and recommendation
- `repeatability/`: independent exact repeatability gate
- `final/`: committed promoted-canonical equivalence gate
- `metrics/`: age-zero and final candidate evaluator summaries
- `validation/`: final tests, build, ROS result, and live-UI build logs
- `provenance.txt`: implementation and artifact fingerprints
- `checksums.sha256`: curated package checksums

The safety priority remains: a lost target is preferable to a wrong target.
