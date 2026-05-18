# TIM-V2E Frame-Level Contradiction Result

Date: 2026-05-18

## Frozen Evaluation Bag

`2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_on__target_1`

## Objective

TIM-V2E tests whether wrong-target duration can be reduced by suppressing control-valid output when the selected target identity becomes contested.

The policy does not claim to recover the true target from geometry alone. Instead, it detects frame-level contradiction and outputs `UNCERTAIN` when another candidate is too close to the selected candidate.

## Baseline

| Method | Correct | Wrong | Lost |
|---|---:|---:|---:|
| TIM-V1 | 0.680 | 0.310 | 0.009 |

## TIM-V2E Sweep Summary

Best practical configuration:

| frame_margin | confirm_frames | Correct | Wrong | Lost |
|---:|---:|---:|---:|---:|
| 0.35 | 5 | 0.574 | 0.247 | 0.179 |

More aggressive configurations reduced wrong duration further but caused excessive LOST or UNCERTAIN output:

| frame_margin | confirm_frames | Correct | Wrong | Lost |
|---:|---:|---:|---:|---:|
| 0.35 | 3 | 0.504 | 0.213 | 0.283 |
| 0.35 | 4 | 0.548 | 0.231 | 0.221 |
| 0.35 | 5 | 0.574 | 0.247 | 0.179 |
| 0.35 | 8 | 0.617 | 0.276 | 0.107 |
| 0.30 | 4 | 0.641 | 0.308 | 0.051 |

## Main Result

TIM-V2E with `frame_margin=0.35` and `confirm_frames=5` reduces wrong-target ratio from 0.310 to 0.247.

Relative wrong-target reduction:

`(0.310 - 0.247) / 0.310 = 20.3%`

This comes at the cost of increasing LOST/UNCERTAIN ratio from 0.009 to 0.179.

## Interpretation

The earlier TIM-V2A/B/C variants failed because they accumulated candidate scores derived from the already-drifted TIM-V1 memory. Once the memory followed the wrong person, geometry-only hypothesis accumulation reinforced the wrong target.

TIM-V2E changes the objective from true-target reacquisition to wrong-target suppression. It uses per-frame candidate competition as a contradiction signal. When the selected target is no longer uniquely supported, TIM-V2E suppresses control-valid output instead of continuing to publish a confident wrong target.

## Thesis Positioning

TIM-V2E is a safety-oriented selected-target memory extension:

> It reduces wrong-control duration by converting contested identity intervals into UNCERTAIN/LOST output.

For UAV following, this is preferable to confidently following the wrong person.

## Current Limitation

TIM-V2E does not solve true re-identification. It cannot reliably select the correct re-entering person using geometry alone. Additional appearance, operator confirmation, or a stronger identity cue is still needed for robust reacquisition after hard crossings.
