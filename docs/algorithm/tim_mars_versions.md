# TIM-MARS algorithm versions and final scope

This document defines the implemented thesis algorithm. Result claims belong
to a specific evidence version; use
`docs/algorithm/tim_mars_evidence_versions.md` before quoting any metric.

## Thesis name and safety objective

Use the name:

**TIM-MARS: Target Identity Memory with MARS appearance consistency**

TIM-V4A, TIM-V4B, TIM-V4C, and TIM-V4D are internal experiment names, not
final algorithm names.

TIM-MARS is a controller-facing selected-target memory layer placed after the
person detector, multi-object tracker, and operator/raw target selector. Its
safety priority is:

**wrong target is worse than lost target**

When identity evidence is insufficient, TIM-MARS suppresses the target instead
of publishing a likely distractor.

## Final implemented components

The frozen component matrix is
`docs/data/ablations/tim_mars_component_ablation_v1.yaml`. The final row
contains these six identity-policy components:

1. **Geometric memory and state hysteresis.** The last trusted ID, bbox,
   quality, missed-frame count, and finite state are retained. Candidate
   geometry uses bbox IoU, centre distance, scale similarity, confidence, and
   same-ID continuity.
2. **Protected positive MARS memory.** MARS embeddings provide identity
   evidence. The operator anchor and trusted gallery are updated only after
   trusted lock; risky recovery cannot immediately rewrite identity memory.
3. **Conservative appearance margin.** Publication can be suppressed when
   similarity or best-versus-second separation is insufficient.
4. **Hard-negative distractor memory.** Repeated trusted distractor
   observations form bounded negative prototypes. Hard-negative and same-ID
   hijack gates reject candidates compatible with a known distractor.
5. **Short-gap persistence.** The previous ID receives short-gap priority and
   unsupported new IDs can be suppressed during the grace interval.
6. **Rank-aware reacquisition.** Plausible lost/uncertain candidates are
   ordered by explicit geometry and appearance evidence before publication
   safety gates are applied.

Output freshness is an additional controller-validity contract, not an
identity-scoring component.

## Motion claim

TIM-MARS does **not** implement an independent velocity estimator or
motion-prediction model. Its geometry policy compares current candidates with
the last trusted bbox. Individual base trackers may contain their own motion
models, but that is tracker behavior and must not be presented as a TIM-MARS
component. The ablation term “persistence” means short-gap identity hysteresis,
not motion prediction.

## Active thresholds

The current source authority is
`ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml`.

| Parameter | Current value | Meaning |
| --- | ---: | --- |
| `appearance_conservative_margin` | `0.05` | Best-versus-second publication margin |
| `hard_negative_reject_margin` | `0.03` | Positive-versus-negative rejection margin |
| `hard_negative_confirm_observations` | `2` | Consecutive trusted observations before negative promotion |
| `rank_aware_lost_app_margin` | `0.03` | Rank-aware lost-state appearance separation |
| `absence_appearance_margin` | `0.20` | Inactive while `absence_recovery_enabled=false` |

The historical strict appearance margin `0.25` is not the active flight
setting. The appearance and hard-negative margins are different quantities and
must not be substituted for one another.

## State machine

- `NO_TARGET`: no selected target exists; output is invalid.
- `LOCKED`: the selected target is trusted; output may be valid.
- `UNCERTAIN`: evidence is ambiguous; output is suppressed.
- `LOST`: safe target availability has expired; output is suppressed.
- `REACQUIRED`: a recovery candidate was accepted but remains probationary
  until confirmation.

Freshness can invalidate an otherwise locked output when its source age exceeds
the configured limit.

## Version history

### Geometry-only TIM

Established selected-target memory, finite-state hysteresis, bbox geometry,
confidence, and tracker-ID continuity without appearance.

### MARS appearance TIM

Added MARS ReID embeddings as supporting identity evidence. Appearance does not
rescue a geometrically implausible candidate.

### Protected positive memory

Separated the operator anchor/trusted gallery from adaptive memory so an
ambiguous recovery cannot immediately poison the identity reference.

### Hard-negative TIM-MARS

Added bounded distractor prototypes. The promoted P0.6b configuration requires
two consecutive trusted observations before hard-negative insertion.

### Rank-aware and same-ID guarded TIM-MARS

Composed rank-aware recovery with confirmation and added same-ID appearance
hijack protection. These changes produced the current P0.17 configuration
fingerprint.

## Evidence result

The current development result is not flawless:

- the optimistic spatial oracle reports `0.000 s` aggregate final wrong-target
  output;
- the conservative annotated-ID oracle reports `1.300 s`, including a visually
  confirmed `0.100 s` May distractor handover around `41.3 s`;
- both improve substantially over their corresponding raw baselines;
- H01–H03 remain uncaptured and no final held-out claim exists.

See
`docs/results/selected_target_tracking/p028_wrong_oracle_audit.md`
and the evidence-version map for the exact claim boundary.

## Tracker dependence

TIM-MARS is modular at the tracker-output interface, but its safety is **not
tracker-independent**. The P0.4 single-preset cross-tracker evaluation was
rejected. Every tracker, configuration, sequence, and annotation pairing needs
its own evidence.

## Experimental policies outside the final row

The following are not active final components unless an explicit alternative
configuration and separate evidence package say otherwise:

- candidate-belief recovery;
- absence recovery;
- active appearance-first reselection;
- old-ID distrust/handoff/reacquire-block variants;
- hold-last-on-reject;
- historical V4 risk-policy variants.

## Thesis description

TIM-MARS is a conservative selected-target memory layer for RGB-only UAV person
following. It combines bbox continuity and state hysteresis, protected MARS
appearance memory, conservative appearance separation, hard-negative
distractor memory, short-gap identity persistence, and rank-aware
reacquisition. When the selected identity is ambiguous or stale, it suppresses
controller-facing output. Evidence must remain configuration-, tracker-,
sequence-, annotation-, and oracle-specific.
