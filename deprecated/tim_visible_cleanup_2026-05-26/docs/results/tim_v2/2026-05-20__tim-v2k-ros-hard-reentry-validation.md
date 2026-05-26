# TIM-V2K ROS Replay Validation on Hard-Reentry Bag

Date: 2026-05-20

## Bag

Frozen eval-matrix bag:

`artifacts/bags/eval_matrix/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_on__target_1`

Validation method:

- replay frozen `/tracks` and `/camera/dashboard`,
- run current `target_memory_node`,
- enable TIM-V2K rank-aware reacquisition,
- evaluate against the original hard-reentry annotation.

This avoids regenerating tracker IDs.

## Result

| Method | Correct | Wrong | Lost |
|---|---:|---:|---:|
| TIM-V2K ROS replay | 0.656 | 0.333 | 0.012 |

## Main Failure Intervals

TIM-V2K remains wrong during the main hard-reentry interval:

| Interval | Selected | Correct |
|---|---:|---:|
| 68.092-68.759 s | 1 | 96 |
| 69.125-100.611 s | 1 | 96 -> 142 |
| 110.043-115.455 s | 142 -> 1 | 161 |

## Interpretation

TIM-V2K does not improve this bag because the dominant failure is not LOST-state reacquisition.

The system remains confidently LOCKED on the wrong target ID 1 while the selected person has re-entered under new tracker IDs. Since TIM-V2K only changes LOST/UNCERTAIN reacquisition, it does not interrupt a wrong but geometrically stable LOCKED target.

## Consequence

TIM-V2K is useful for rank-aware reacquisition from LOST, but it is not sufficient for wrong-LOCKED suppression.

The next TIM-V2 mechanism should target locked-state contradiction:

- detect when the current LOCKED target is contested,
- suppress control by entering UNCERTAIN,
- or switch only after a persistent challenger is confirmed.

This is distinct from TIM-V2K and should be evaluated separately.
