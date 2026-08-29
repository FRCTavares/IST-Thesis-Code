# Issue #58 — Simple Target-ReID baseline calibration

## Status

Development-only calibration evidence. This result is not held-out evidence and
must not be used as a final generalisation claim.

## Baseline contract

The simple Target-ReID baseline uses ByteTrack candidates and the same CPU
MARS-small128 model and crop/preprocessing path used by TIM-MARS.

One valid MARS embedding from the operator-selected ByteTrack target is captured
as an immutable anchor. After bootstrap, tracker ID has no identity authority.
At each tracker update, all candidates with valid embeddings are ranked only by
cosine similarity to the fixed anchor. The highest-ranked candidate is
published only when its similarity meets the calibrated threshold; otherwise
the output is LOST.

The baseline excludes TIM-MARS geometry fusion, adaptive or trusted appearance
memory updates, hard negatives, temporal confirmation, recovery heuristics, and
TIM state-machine authority.

## Frozen calibration protocol

Development sequence: `dev_may_hard_reentry`.

Threshold grid was frozen before outcome review:

    0.00, 0.05, ..., 0.95

The inherited Issue #58 asymmetric safety selector is:

1. fail closed against the raw ByteTrack wrong-person and target-absence output
   durations, allowing only the historical 0.05 s evaluator tolerance;
2. among promotable thresholds, minimize wrong-person output duration;
3. break ties by minimizing lost/suppressed duration;
4. if both are exactly tied, prefer the higher threshold as a deterministic
   final tie-break.

Safety and availability are not combined into a weighted scalar.

## Selected development operating point

The frozen selector chooses threshold `0.90`.

Physical-target v2 metrics over `67.864909774 s`:

| Metric | Target-ReID |
| --- | ---: |
| Correct-target output | 23.152773497 s |
| Wrong-person output | 0.000000000 s |
| Identity unresolved | 0.000000000 s |
| Lost/suppressed | 44.712136277 s |
| Target absent | 0.000000000 s |
| Target absent with output | 0.000000000 s |

Replay provenance:

- selected tracker ID used only for anchor bootstrap: `1`
- anchor bootstrap frame: `104`
- image geometry: `640 x 640`
- tracks normalized: `false`
- causal image-age limit: `250 ms`
- tracker messages: `950`
- Target-ReID messages: `950`
- valid Target-ReID publications: `283`
- CPU appearance model: `models/reid/mars-small128.pb`
- MARS model SHA-256: `e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1`
- physical-reference file: `docs/data/physical_target_references/dev_may_hard_reentry.json`
- physical-reference SHA-256: `45d620d97e6488fb174e4ce66c49403079e084bc577d6d621c8365265f0d238c`

## Interpretation

The fixed-template Target-ReID baseline can eliminate physical wrong-person
output on this development sequence, but only with a large availability cost:
roughly two thirds of the evaluated duration is suppressed as LOST.

This is the intended scientific role of the baseline. It demonstrates that a
simple appearance threshold can be made highly conservative, while allowing
the later Issue #58 comparison to test whether full TIM-MARS preserves
substantially more useful controller-facing target authority without accepting
unsafe identity transfers.

No threshold, grid, or selector rule may be changed retrospectively based on
this outcome.
