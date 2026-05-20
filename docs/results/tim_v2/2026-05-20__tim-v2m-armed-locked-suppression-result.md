# TIM-V2M Armed Locked-Suppression Result

Date: 2026-05-20

## Bag

Frozen hard-reentry eval-matrix bag:

`artifacts/bags/eval_matrix/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_on__target_1`

Validation method:

- replay frozen `/tracks` and `/camera/dashboard`,
- run target memory only,
- evaluate against the original hard-reentry annotation.

## Objective

TIM-V2M tests whether wrong-LOCKED duration can be reduced by suppressing control output when a plausible challenger appears after a recent instability event.

This targets a failure mode not solved by TIM-V2K:

> TIM remains confidently LOCKED on the wrong person after the selected person re-enters under a new tracker ID.

## Baseline Context

TIM-V2K did not improve this hard-reentry bag because the main failure was not LOST-state reacquisition. The system remained LOCKED on ID 1 while the selected person re-entered as IDs 96, 113, and 142.

## First Armed Suppression Test

Configuration:

| Parameter | Value |
|---|---:|
| challenger_min_total | 0.50 |
| challenger_min_geom | 0.50 |
| challenger_margin_to_current | 0.45 |
| challenger_confirm_frames | 5 |
| arm_after_instability_frames | 90 |

Result:

| Correct | Wrong | Lost |
|---:|---:|---:|
| 0.550 | 0.290 | 0.160 |

This reduced wrong duration compared with the unmodified hard-reentry behaviour, but not enough.

## Sweep Result

No configuration satisfied the practical target:

- correct >= 0.55
- wrong <= 0.25
- lost <= 0.25

Best safety-oriented configuration under `lost <= 0.25`:

| Correct | Wrong | Lost | Notes |
|---:|---:|---:|---|
| 0.511 | 0.243 | 0.246 | Wrong reduced, but correct too low |

Best near-balanced configuration:

| Correct | Wrong | Lost | Notes |
|---:|---:|---:|---|
| 0.554 | 0.264 | 0.182 | Correct acceptable, but wrong still too high |

## Interpretation

TIM-V2M confirms that wrong-LOCKED suppression can reduce wrong-target duration, but the current rule is too blunt.

The policy suppresses some true wrong-LOCKED intervals, but it also suppresses correct LOCKED intervals after benign instability. This makes it unsuitable as a final live policy.

## Conclusion

TIM-V2M should not be implemented live in its current form.

The current evidence separates two failure classes:

1. TIM-V2K helps LOST-state rank-aware reacquisition.
2. TIM-V2M partially addresses wrong-LOCKED suppression but is not selective enough.

The next step should be a more specific wrong-LOCKED detector, using either stronger identity evidence or a better event trigger than generic recent instability.
