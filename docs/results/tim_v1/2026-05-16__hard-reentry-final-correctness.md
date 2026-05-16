# Hard Re-entry Final Correctness Result

Bag:

artifacts/bags/eval_matrix/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_on__target_1

Annotation:

docs/annotations/2026-05-14__hard_reentry_ocsort_tim_on_target1/target_correctness_annotations.csv

## Result

| Metric | Raw /target | TIM /target_memory |
|---|---:|---:|
| Correct duration [s] | 62.350 | 84.870 |
| Wrong duration [s] | 47.500 | 38.700 |
| Lost duration [s] | 14.870 | 1.150 |
| Visible target duration [s] | 124.720 | 124.720 |
| Correct ratio | 0.500 | 0.680 |
| Wrong ratio | 0.381 | 0.310 |
| Lost ratio | 0.119 | 0.009 |

## Interpretation

TIM improves selected-target correctness compared with raw tracker-ID following:

- correct ratio improves from 0.500 to 0.680
- lost ratio decreases from 0.119 to 0.009

However, wrong-target duration remains significant:

- raw wrong ratio: 0.381
- TIM wrong ratio: 0.310

This confirms that valid target duration alone is not sufficient. TIM can remain valid while still following the wrong person during close crossings and ID changes.

## Failure mode

The main failure is a persistent distractor with strong geometric continuity. The selected person changes tracker ID, but TIM can keep following the geometrically smooth distractor.

Next improvements should focus on wrong-target suppression and candidate-hypothesis competition, not only increasing valid duration.
