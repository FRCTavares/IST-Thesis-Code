# TIM-V2F Persistent Runner-Up Policy Result

Date: 2026-05-18

## Frozen Evaluation Bag

`2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_on__target_1`

## Motivation

Oracle candidate-presence analysis showed that the annotated correct target is present in most evaluated frames:

| Metric | Value |
|---|---:|
| correct_present_ratio | 0.913 |
| correct_absent_ratio | 0.087 |
| correct_rank0_ratio | 0.656 |
| correct_rank1_ratio | 0.258 |

This means the bag is not impossible from the candidate list. However, a correct policy must sometimes select a persistent rank-1 candidate rather than blindly following the rank-0 geometric candidate.

## Policy

TIM-V2F uses a persistent runner-up rule:

- keep the current selected ID by default,
- monitor the strongest non-selected candidate,
- if a runner-up remains geometrically plausible and close to the selected candidate for several consecutive frames, switch to the runner-up,
- require confirmation before reacquiring after loss.

Chosen fixed configuration:

| Parameter | Value |
|---|---:|
| runner_min_geom | 0.40 |
| runner_max_gap | 0.35 |
| runner_confirm_frames | 15 |
| reacquire_confirm_frames | 3 |

## Result

| Method | Correct | Wrong | Lost |
|---|---:|---:|---:|
| TIM-V1 baseline | 0.680 | 0.310 | 0.009 |
| TIM-V2E frame contradiction | 0.574 | 0.247 | 0.179 |
| TIM-V2F runner-up policy | 0.693 | 0.277 | 0.030 |

## Main Finding

TIM-V2F reduces wrong-target ratio from 0.310 to 0.277 while also improving correct-target ratio from 0.680 to 0.693.

Relative wrong-target reduction:

`(0.310 - 0.277) / 0.310 = 10.6%`

Unlike TIM-V2E, this improvement does not come from aggressively converting output to LOST/UNCERTAIN. The lost ratio only increases from 0.009 to 0.030.

## Interpretation

TIM-V2E is safety-oriented: it reduces wrong-target duration by suppressing contested output.

TIM-V2F is identity-recovery-oriented: it uses persistent runner-up evidence to recover from cases where the correct target is present as a stable rank-1 candidate.

For this bag, TIM-V2F is the stronger candidate because it improves wrong-target duration without collapsing target availability.

## Current Limitation

This result is still from one annotated hard re-entry bag. The same fixed parameters must be validated on at least one additional hard bag before live TIM-V2 implementation.
