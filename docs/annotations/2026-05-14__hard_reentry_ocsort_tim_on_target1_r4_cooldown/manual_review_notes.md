# Manual Review Notes - Hard Re-entry OC-SORT TIM-on Target 1 r4 Cooldown

Eval bag:

artifacts/bags/eval_matrix/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_on__target_1__r4

## Manual interval review

- 0.00-4.74 s: selected person is visible as ID 1, but no target has been selected yet.
- 4.74-50.28 s: selected person is ID 1 and TIM follows ID 1 correctly.
- 50.28-50.67 s: selected person remains ID 1, but TIM briefly outputs no target.
- 50.67-69.99 s: selected person is ID 1 and TIM follows ID 1 correctly.
- 69.99-101.87 s: selected person becomes ID 94, but TIM follows distractor ID 1. This is a wrong-target interval.
- 101.87-111.51 s: selected person is ID 140 and TIM follows ID 140 correctly. Raw /target is incorrect in this interval.
- 111.51-116.98 s: selected person is ID 159, but TIM follows distractor ID 1. This is a wrong-target interval.
- 116.98-end: selected person is ID 159 and TIM follows ID 159 correctly.

## Interpretation

The cooldown run still has wrong-target intervals, but it also contains a useful recovery interval where TIM follows the correct target while raw /target is incorrect.

The main failure remains persistent distractor association during close crossings and tracker ID changes.
