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

## Current recommended policy

For the hard re-entry evaluation, the current effective conservative policy is:

- `MARS_APPEARANCE_WEIGHT=0.30`
- `MARS_APPEARANCE_MIN_SIMILARITY=0.35`
- `MARS_APPEARANCE_AMBIGUOUS_ONLY=false`
- `MARS_APPEARANCE_CHALLENGE_ENABLED=false`
- `MARS_APPEARANCE_CONSERVATIVE_ENABLED=true`
- `MARS_APPEARANCE_CONSERVATIVE_REQUIRE_APPEARANCE=false`
- `MARS_APPEARANCE_CONSERVATIVE_MIN_SIMILARITY=0.65`
- `MARS_APPEARANCE_CONSERVATIVE_MARGIN=0.25`
- `MARS_RANK_AWARE_REACQUISITION_ENABLED=true`
- `MARS_RANK_AWARE_CONFIRM_FRAMES=1`
- `MARS_RANK_AWARE_MISSING_TTL_FRAMES=8`

These values are not yet universal defaults. They are the current hard re-entry evaluation policy.

## Tracker dependence

TIM-MARS behaviour depends strongly on the base tracker.

Current hard re-entry verdict:

1. ByteTrack fixed + TIM-MARS is the best current result.
2. Raw DeepSORT-MARS is already very strong and safest under wrong-target minimisation.
3. OCSORT + TIM-MARS is defensible but weaker than ByteTrack + TIM-MARS.
4. SORT is too fragmented for this TIM-MARS configuration.

## Main result

Current main result source:

- `docs/results/selected_target_tracking/hard_reentry_multi_tracker_summary.md`

Best result:

- ByteTrack + TIM-MARS
- correct ratio = 0.970
- wrong ratio = 0.013
- lost ratio = 0.017

## Design conclusion

TIM-MARS is useful when the base tracker has recoverable identity instability.

It is less useful when the base tracker is already highly stable.

It is unsafe when the base tracker is too fragmented, because memory either follows wrong candidates or becomes overly conservative.
