# Active TIM-MARS R1 scaled evaluation

Date: 2026-06-03

## Purpose

This run verifies the first real active TIM-MARS evaluation where MARS ReID appearance is used inside the target-memory scoring loop.

## Bag

`artifacts/bags/eval_matrix/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_off__target_1__tracker_ocsort__tim_mars__target_1__r1`

## Annotation

`docs/data/annotations/hard_reentry/ocsort_tim_mars_r1.csv`

The annotation was derived from the previous 67.84 s hard re-entry annotation and scaled by 4.0 because this r1 bag has a 271.36 s timeline.

## Active MARS verification

Status sampling confirmed that MARS appearance was actually used:

- Parsed status messages: 89
- Messages with valid appearance features: 50
- Messages with appearance gate passed: 48
- Messages with appearance used: 48

Therefore, this is not only feature extraction. MARS ReID contributed to candidate scoring.

## Evaluation result

| Stream | Correct [s] | Wrong [s] | Lost [s] | Correct ratio | Wrong ratio | Lost ratio |
|---|---:|---:|---:|---:|---:|---:|
| Raw OCSORT | 125.050 | 96.700 | 49.610 | 0.461 | 0.356 | 0.183 |
| Active TIM-MARS | 186.060 | 82.950 | 2.350 | 0.686 | 0.306 | 0.009 |

## Difference

| Metric | Change |
|---|---:|
| Correct target duration | +61.010 s |
| Wrong target duration | -13.750 s |
| Lost target duration | -47.260 s |

## Interpretation

Active TIM-MARS improves selected-target continuity and correctness on the hard re-entry sequence. It strongly reduces lost-target duration and moderately reduces wrong-target duration.

However, wrong-target output remains high at 82.950 s, corresponding to a 0.306 wrong-target ratio. Therefore, this result should not be presented as solving identity-confusion safety. The next required step is a conservative ambiguity or handover rejection policy, where uncertain identity matches are output as LOST/UNCERTAIN rather than forced as a selected target.

