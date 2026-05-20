# TIM-V2E Learned Suppression Policy Result

Date: 2026-05-20

## Purpose

Test whether the Tiny16 learned appearance cue can reduce wrong selected-target output by conservatively suppressing low-similarity selected tracks.

This is an offline simulation only. It does not modify live TIM.

## Policy

Conservative suppression only:

- no switching
- no learned reacquisition
- if the currently selected track has learned similarity below threshold, output LOST
- threshold: 0.0
- max similarity time delta: 0.10 s

## Inputs

Critical crossing:

- scores: `reports/tim_v2_sources/tim_v1m_appearance_critical_crossing/target_memory_all_scores__tm_extract_select20p40.csv`
- annotations: `docs/annotations/tim_v1m_appearance_critical_crossing/target_correctness_annotations.csv`

Hard re-entry:

- scores: `reports/tim_v0/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_on__target_1/target_memory_all_scores.csv`
- annotations: `docs/annotations/2026-05-14__hard_reentry_ocsort_tim_on_target1/target_correctness_annotations.csv`

Similarity source:

- `reports/tim_v2_embedding/tiny16_train_memory_eval_csv/test_similarity_scores.csv`

## Critical crossing result

Output:

- `reports/tim_v2_embedding/v2e_learned_suppression_critical_crossing_thr0/summary.md`
- `reports/tim_v2_embedding/v2e_learned_suppression_critical_crossing_thr0/timeline.csv`

Global result:

| Metric | Raw | Policy |
|---|---:|---:|
| correct_s | 12.116 | 12.116 |
| wrong_s | 27.739 | 26.737 |
| lost_s | 0.000 | 1.002 |

Suppressed:

- suppressed_s: 1.048
- suppressed_frames: 23

Event-level result:

| Event | Raw wrong_s | Policy wrong_s | Policy lost_s |
|---|---:|---:|---:|
| hard_reentry | 12.344 | 12.344 | 0.000 |
| late_reentry | 1.458 | 0.638 | 0.820 |
| reentry_id_switch | 2.551 | 2.551 | 0.000 |
| visible_but_wrong_best_candidate | 11.387 | 11.205 | 0.182 |

## Hard re-entry result

Output:

- `reports/tim_v2_embedding/v2e_learned_suppression_hard_reentry_thr0/summary.md`
- `reports/tim_v2_embedding/v2e_learned_suppression_hard_reentry_thr0/timeline.csv`

Global result:

| Metric | Raw | Policy |
|---|---:|---:|
| correct_s | 68.932 | 68.932 |
| wrong_s | 35.613 | 19.677 |
| lost_s | 0.000 | 15.935 |

Suppressed:

- suppressed_s: 15.935
- suppressed_frames: 132

Event-level result:

| Event | Raw wrong_s | Policy wrong_s | Policy lost_s |
|---|---:|---:|---:|
| correct_tracking | 0.604 | 0.604 | 0.000 |
| recovered_target | 2.052 | 2.052 | 0.000 |
| transition_uncertain | 0.483 | 0.241 | 0.241 |
| wrong_target_interval | 32.474 | 16.780 | 15.694 |

## Interpretation

The learned suppression policy is useful in the hard re-entry bag, where it converts a large amount of wrong-target output into LOST.

This is control-safer because wrong target is worse than LOST.

However, suppression-only is not sufficient for the critical crossing bag. It barely affects the main wrong intervals, especially `hard_reentry` and `reentry_id_switch`.

## Decision

Keep learned suppression as a safety mechanism, but do not stop here.

The next TIM-V2E policy must add confirmed learned reacquisition:

1. suppress low-similarity selected output,
2. look for high-similarity candidate tracks,
3. require confirmation for several consecutive frames,
4. then reacquire.

This matches the intended hybrid design: TIM-V2K rank-aware reacquisition plus learned identity evidence.
