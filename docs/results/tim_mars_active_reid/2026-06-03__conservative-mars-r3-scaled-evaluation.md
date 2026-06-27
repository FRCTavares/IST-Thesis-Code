# Conservative TIM-MARS R3 scaled evaluation

Date: 2026-06-03

## Purpose

This run evaluates a conservative TIM-MARS output filter. The goal is to reduce wrong selected-target output, even if this increases LOST output.

## Bag

`artifacts/bags/replay/eval_matrix/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_off__target_1__tracker_ocsort__tim_mars__target_1__r3`

## Annotation

`docs/data/annotations/may_hard_reentry/ocsort_hard_reentry.csv`

## Parameters

- `MARS_APPEARANCE_WEIGHT=0.30`
- `MARS_APPEARANCE_MIN_SIMILARITY=0.35`
- `MARS_APPEARANCE_AMBIGUOUS_ONLY=false`
- `MARS_APPEARANCE_CHALLENGE_ENABLED=false`
- `MARS_APPEARANCE_CONSERVATIVE_ENABLED=true`
- `MARS_APPEARANCE_CONSERVATIVE_MIN_SIMILARITY=0.65`
- `MARS_APPEARANCE_CONSERVATIVE_MARGIN=0.25`

## Evaluation result

| Stream | Correct [s] | Wrong [s] | Lost [s] | Correct ratio | Wrong ratio | Lost ratio |
|---|---:|---:|---:|---:|---:|---:|
| Raw OCSORT | 131.150 | 96.700 | 43.510 | 0.483 | 0.356 | 0.160 |
| Conservative TIM-MARS | 183.400 | 30.050 | 57.910 | 0.676 | 0.111 | 0.213 |

## Comparison with active TIM-MARS R1

| Variant | Correct [s] | Wrong [s] | Lost [s] |
|---|---:|---:|---:|
| Active TIM-MARS R1 | 186.060 | 82.950 | 2.350 |
| Conservative TIM-MARS R3 | 183.400 | 30.050 | 57.910 |

## Interpretation

Conservative TIM-MARS R3 strongly reduces wrong selected-target output compared with active TIM-MARS R1, from 82.950 s to 30.050 s. Correct-target duration remains similar, decreasing only from 186.060 s to 183.400 s.

The cost is increased LOST output, from 2.350 s to 57.910 s. This is an acceptable safety trade-off for the selected-target tracking problem, because outputting no target is safer than outputting the wrong target.

This result supports the use of ReID not only as a score bonus, but as a conservative safety filter for target-memory output.
