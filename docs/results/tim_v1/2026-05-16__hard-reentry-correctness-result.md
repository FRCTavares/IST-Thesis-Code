# Hard Re-entry Correctness Result - OC-SORT TIM-on

Bag:

artifacts/bags/eval_matrix/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_on__target_1

Annotation:

docs/annotations/2026-05-14__hard_reentry_ocsort_tim_on_target1/target_correctness_annotations.csv

## Result

| Metric | Raw /target | TIM /target_memory |
|---|---:|---:|
| correct duration [s] | 63.460 | 86.490 |
| wrong duration [s] | 46.520 | 37.270 |
| lost duration [s] | 14.930 | 1.150 |
| visible target duration [s] | 124.910 | 124.910 |
| correct ratio | 0.508 | 0.692 |
| wrong ratio | 0.372 | 0.298 |
| lost ratio | 0.120 | 0.009 |

## Interpretation

TIM improves selected-target correctness compared with the raw selected-ID baseline:

- correct ratio improves from 0.508 to 0.692
- lost ratio decreases from 0.120 to 0.009

However, wrong-target duration remains significant:

- raw wrong ratio: 0.372
- TIM wrong ratio: 0.298

This confirms that valid target duration is not enough as a metric. TIM can remain valid while still following the wrong person.

## Main failure mode

The main failure occurs during close crossings and ID changes:

- around 69.32-101.20 s, the selected target becomes ID 96, but TIM follows distractor ID 1
- around 110.84-116.31 s, the selected target becomes ID 161, but TIM switches back to distractor ID 1

## Next improvement direction

The next TIM improvement should focus on reducing wrong-target duration, not simply increasing valid duration.

Candidate approaches:

- safer appearance-gated reacquisition
- candidate hypothesis memory
- distractor suppression
- explicit penalty for returning to a recently identified distractor
