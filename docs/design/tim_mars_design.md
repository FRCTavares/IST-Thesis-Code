# TIM-MARS design

Date: 2026-06-06

## Purpose

TIM-MARS is the current selected-target memory variant that uses MARS ReID appearance embeddings to improve target identity robustness after occlusion, identity switches, and re-entry.

It is designed as a lightweight control-safety layer above an existing tracker.

## Position in the pipeline

TIM-MARS consumes:

- `/tracks`
- `/target`
- `/camera/dashboard`

TIM-MARS publishes:

- `/target_memory_mars`
- `/target_memory_mars/status`

The base tracker still performs multi-object tracking. TIM-MARS only decides whether the selected target output should remain locked, switch to a candidate, or become lost.

## Why MARS is used

Geometry alone is not enough during hard crossings and re-entry.

MARS appearance embeddings provide an identity cue that can distinguish candidates when tracker IDs change or when the selected target reappears under a different ID.

MARS is used as supporting evidence, not as an unconditional replacement for geometry and tracker state.

## Matching logic

TIM-MARS combines:

- geometry consistency;
- distance consistency;
- scale consistency;
- confidence;
- appearance similarity;
- ambiguity checks;
- conservative rejection rules.

The selected candidate must be strong enough and not too ambiguous.

## Conservative appearance filtering

The conservative filter is used to prevent wrong-target handovers.

When enabled, appearance evidence can reject a candidate if:

- appearance similarity is too low;
- the appearance margin over competing candidates is too small;
- the candidate is identity-ambiguous.

This is intentionally conservative because wrong target is worse than LOST.

## Missing appearance policy

A critical implementation detail is:

- `appearance_conservative_require_appearance`

Default:

- `false`

Reason:

Conservative appearance filtering is useful when appearance is available. However, missing or stale appearance should not automatically force LOST in normal operation.

The corrected behaviour is:

- if appearance is available, apply conservative similarity and margin checks;
- if appearance is missing, reject only when `appearance_conservative_require_appearance=true`;
- otherwise, allow non-appearance evidence to decide.

This prevents strict conservative mode from rejecting almost every frame when appearance is temporarily unavailable.

## Diagnostic strict mode

`appearance_conservative_require_appearance=true` is useful as a diagnostic mode.

It answers the question:

> What happens if we require appearance evidence for every conservative output?

It is not the normal operating mode because it can produce excessive LOST output when crops or embeddings are unavailable.

## Current canonical evidence policy

The promoted P0.18 evidence uses:

- `ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml`;
- configuration SHA-256
  `16f21b2032135858d2ea7d5d8081536eb24204a3ef0f12efb05a628d626a0655`;
- MARS model SHA-256
  `e96f3cc09dbce76e2f6aeff09c8f2502916b4745f21e27911ee50d102a4a75f1`;
- image-header-time evaluation with a `0.05 s` step and safety tolerance.

This configuration is frozen for the recorded evidence. It is not a universal preset.

## Tracker dependence

TIM-MARS behaviour depends strongly on the base tracker and sequence.

The canonical hard-reentry matrix rejects the single preset for ByteTrack, SORT, OC-SORT, and DeepSORT:

- ByteTrack: `+0.700 s` wrong-target output;
- SORT: `+5.300 s` wrong-target output and `+0.150 s` target-absence valid output;
- OC-SORT: `+0.200 s` target-absence valid output;
- DeepSORT: `+15.203 s` wrong-target output.

Repeated OC-SORT sequence evidence also rejects promotion across the required pair:

- Seq03: `+1.350 s` wrong-target output;
- Seq04: `+0.050 s`, exactly the one-step tolerance boundary.

Motion-only tracker association is therefore not sufficient to guarantee safe layering. Appearance-based tracker association remains outside the current safe claim.

## Main result

Canonical evidence sources:

- `reports/p018_tim_matrix_36ecd17d_2026_07_19/`;
- `reports/p018_ocsort_tim_2d1ae5e9_2026_07_19/`.

The main result is a scoped design boundary rather than a universal winning tracker:

- the tracker-output interface is modular;
- the single canonical preset is not safety-portable;
- each tracker and configuration pairing requires its own calibration and held-out safety evaluation.

## Design conclusion

TIM-MARS can substantially improve correct-target availability when the base tracker provides recoverable candidate continuity.

That benefit can coexist with unsafe wrong-target output. Aggregate correctness or reduced LOST duration is not sufficient for promotion.

The implementation may remain tracker-interface modular, but the safety claim must be tracker-, configuration-, and sequence-specific.
