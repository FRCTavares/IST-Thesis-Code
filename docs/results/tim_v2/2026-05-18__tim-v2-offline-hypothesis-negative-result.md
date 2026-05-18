# TIM-V2 Offline Hypothesis Simulation: Negative Result

Date: 2026-05-18

## Bag

Frozen hard re-entry eval bag:

`2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_on__target_1`

Scores:

`reports/tim_v0/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_on__target_1/target_memory_all_scores.csv`

Annotations:

`docs/annotations/2026-05-14__hard_reentry_ocsort_tim_on_target1/target_correctness_annotations.csv`

## Baseline

TIM-V1 hard re-entry correctness reference:

| Method | Correct | Wrong | Lost |
|---|---:|---:|---:|
| TIM-V1 | 0.680 | 0.310 | 0.009 |

## Tested TIM-V2 Offline Policies

| Policy | Correct | Wrong | Lost | Result |
|---|---:|---:|---:|---|
| V2A naive total-score accumulation | 0.652 | 0.346 | 0.002 | worse than TIM-V1 |
| V2B anti-switch confirmation, total evidence | 0.649 | 0.332 | 0.018 | worse than TIM-V1 |
| V2C neutral evidence | 0.644 | 0.333 | 0.023 | worse than TIM-V1 |
| V2C geometry evidence | 0.644 | 0.333 | 0.023 | worse than TIM-V1 |

## Main Observation

Geometry-only hypothesis competition does not reduce wrong-target duration on this hard re-entry bag.

The main failure interval remains dominated by track ID `1`, even after the selected person has re-entered as new tracker IDs. The all-scores diagnostics show that ID `1` remains geometrically strong relative to the current memory state, while true-target re-entry IDs receive no identity evidence strong enough to dominate.

## Interpretation

This is not simply an appearance-weight or threshold problem.

The score file contains candidate scores relative to the current TIM-V1 memory. Once TIM-V1 has locked onto the wrong person, geometry-based scoring continues to favour the wrong track because the memory state has effectively drifted.

Therefore, a hypothesis accumulator over the same scores can reinforce the wrong identity instead of correcting it.

## Consequence for TIM-V2

The next TIM-V2 direction should not claim reliable true-target reacquisition from geometry alone.

Instead, TIM-V2 should focus first on wrong-target suppression:

- detect identity contradiction,
- enter UNCERTAIN instead of staying confidently LOCKED,
- prevent unsafe control output when the selected identity is no longer reliable.

This reframes TIM-V2 as a control-safety improvement:

> Reduce wrong-LOCKED duration, even if this increases LOST/UNCERTAIN duration.

For UAV following, this is preferable because following the wrong person is worse than hovering or waiting for target confirmation.
