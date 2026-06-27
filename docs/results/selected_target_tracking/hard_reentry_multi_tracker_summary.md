# Hard re-entry selected-target tracking summary

Date: 2026-06-06

## Sequence

Source sequence:

`artifacts/bags/replay/eval_matrix/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_off__target_1`

Scenario:

- two-person hard crossing and re-entry;
- selected target: black-shirt person;
- main failure mode: selected-target identity switch or wrong-target persistence after occlusion/re-entry.

## Purpose

This evaluation tests whether TIM-MARS improves selected-target robustness after occlusion, identity switches, and target re-entry.

TIM-MARS is evaluated as a selected-target memory and safety layer above tracker outputs. It is not evaluated as a generic MOT tracker.

## Metric

The metric is selected-target correctness over the visible-target interval:

- `correct_target_duration_s`
- `wrong_target_duration_s`
- `lost_target_duration_s`
- `correct_target_ratio`
- `wrong_target_ratio`
- `lost_target_ratio`

Core safety rule:

> Wrong target is worse than LOST.

A useful configuration must reduce wrong-target output without destroying correct-target duration.

## Trusted annotation files

Active hard-reentry annotation files:

- ByteTrack final: `docs/data/annotations/may_hard_reentry/bytetrack_hard_reentry.csv`
- DeepSORT-MARS target 1 final: `docs/data/annotations/may_hard_reentry/deepsort_hard_reentry.csv`
- OCSORT TIM-MARS R1: `docs/data/annotations/may_hard_reentry/ocsort_hard_reentry.csv`

Older manual-review and intermediate annotation versions are archived under `docs/archive/annotations/`.

## Fresh evaluation reports

Generated reports:

- ByteTrack: `reports/final_selected_target_tracking/bytetrack_tim_mars/summary.md`
- DeepSORT-MARS: `reports/final_selected_target_tracking/deepsort_mars/summary.md`
- OCSORT: `reports/final_selected_target_tracking/ocsort_tim_mars/summary.md`

These reports are generated artefacts and are not committed by default because `reports/` is ignored.

## Compared bags

| Tracker | Bag |
|---|---|
| ByteTrack + TIM-MARS | `artifacts/bags/replay/eval_matrix/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_off__target_1__tracker_bytetrack__tim_mars__target_1__r4` |
| DeepSORT-MARS + TIM-MARS | `artifacts/bags/replay/eval_matrix/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_off__target_1__tracker_deepsort__tim_mars__target_1` |
| OCSORT + TIM-MARS | `artifacts/bags/replay/eval_matrix/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_off__target_1__tracker_ocsort__tim_mars__target_1` |

## Final results

| Tracker | Variant | Correct [s] | Wrong [s] | Lost [s] | Correct ratio | Wrong ratio | Lost ratio |
|---|---|---:|---:|---:|---:|---:|---:|
| ByteTrack | Raw `/target` | 47.045 | 7.800 | 12.755 | 0.696 | 0.115 | 0.189 |
| ByteTrack | TIM-MARS `/target_memory_mars` | 65.570 | 0.850 | 1.180 | 0.970 | 0.013 | 0.017 |
| DeepSORT-MARS | Raw `/target` | 61.050 | 0.000 | 6.550 | 0.903 | 0.000 | 0.097 |
| DeepSORT-MARS | TIM-MARS `/target_memory_mars` | 62.850 | 3.300 | 1.450 | 0.930 | 0.049 | 0.021 |
| OCSORT | Raw `/target` | 31.130 | 24.367 | 12.103 | 0.460 | 0.360 | 0.179 |
| OCSORT | TIM-MARS `/target_memory_mars` | 30.630 | 21.006 | 15.965 | 0.453 | 0.311 | 0.236 |

## ByteTrack configuration fix

ByteTrack was initially unstable because the shared tracker configuration was not suitable for its two-stage association logic.

Initial ID churn:

- sampled IDs: 1192
- unique IDs: 644
- max ID: 947

Main causes:

- `min_score = 0.35` starved ByteTrack of low-score recovery detections.
- `match_thresh` and `second_match_thresh` were treated like IoU thresholds, while the backend uses IoU distance.

Final ByteTrack configuration:

- `tracker_type`: `bytetrack`
- `min_score`: `0.2`
- `track_thresh`: `0.5`
- `match_thresh`: `0.8`
- `track_buffer`: `30`
- `det_thresh`: `0.2`
- `second_match_thresh`: `0.5`
- `new_track_thresh`: `0.6`
- `unconfirmed_match_thresh`: `0.7`

After the fix:

- sampled IDs: 2544
- unique IDs: 39
- max ID: 71

This made ByteTrack a usable base tracker for TIM-MARS.

## TIM-MARS conservative appearance fix

Strict conservative TIM-MARS was rejecting almost every frame when appearance was unavailable.

Observed in `/target_memory_mars/status` before the fix:

- LOST = 931
- UNCERTAIN = 18
- LOCKED = 3
- `appearance_conservative_reject:no_appearance_used` = 837

The fix introduced:

- `appearance_conservative_require_appearance: bool = False`

Corrected logic:

- if conservative appearance filtering is enabled and appearance is available, similarity and margin checks are applied;
- if appearance is unavailable, the target is rejected only when `appearance_conservative_require_appearance` is true;
- otherwise, missing appearance does not automatically force LOST.

This preserves conservative appearance filtering when useful, without making missing or stale appearance a hard rejection condition in normal operation.

## Main interpretation

### ByteTrack

ByteTrack fixed + TIM-MARS non-strict conservative is the best current result.

Compared with raw ByteTrack:

- correct duration increases from 47.045 s to 65.570 s;
- wrong duration decreases from 7.800 s to 0.850 s;
- lost duration decreases from 12.755 s to 1.180 s.

This is the strongest evidence that TIM-MARS is useful when the base tracker has recoverable identity instability.

### DeepSORT-MARS

Raw DeepSORT-MARS is already a very strong baseline:

- correct ratio = 0.928;
- wrong ratio = 0.000;
- lost ratio = 0.072.

Adding TIM-MARS reduces LOST from 6.550 s to 1.450 s, but introduces 3.300 s of wrong output.

Under the safety rule that wrong target is worse than LOST, DeepSORT-MARS + TIM-MARS is not a strict improvement over raw DeepSORT-MARS. It is a continuity-versus-safety trade-off.

### OCSORT

OCSORT + TIM-MARS is defensible but not best.

Compared with raw OCSORT:

- correct duration decreases from 31.130 s to 30.630 s;
- wrong duration decreases from 24.367 s to 21.006 s;
- lost duration increases from 12.103 s to 15.965 s.

This is a weak trade-off: wrong-target output is reduced, but lost-target duration increases by a comparable amount. ByteTrack + TIM-MARS is much stronger on this sequence.

## Current tracker verdict

Under the strict selected-target safety metric:

1. ByteTrack fixed + TIM-MARS non-strict conservative
2. Raw DeepSORT-MARS
3. OCSORT + TIM-MARS conservative
4. DeepSORT-MARS + TIM-MARS
5. Raw ByteTrack fixed
6. Raw OCSORT
7. SORT variants

## Thesis interpretation

TIM-MARS is most useful when the base tracker has recoverable identity instability, as shown by ByteTrack and OCSORT.

TIM-MARS is less useful when the base tracker is already highly stable, as shown by DeepSORT-MARS.

TIM-MARS is unsafe when the base tracker is too fragmented, as observed in previous SORT experiments, because it either introduces wrong output or becomes too conservative.

## Visual audit note

For source-image status audit rendering, `--eval-time-scale 2.0` was visually correct.

Rejected values:

- `1.0`: time-misaligned boxes;
- `4.0`: time-misaligned boxes.

Important distinction:

`--eval-time-scale` is a visual synchronisation parameter for rendering. It is not the same as the annotation scaling factor.

Do not overwrite these final audit videos:

- `reports/bytetrack_fixed_mars_r4_visual_audit/bytetrack_mars_r4_tim_status_audit_scaled2.mp4`
- `reports/deepsort_mars_visual_audit/deepsort_mars_tim_status_audit_scaled2.mp4`

## Limitations

- This is one hard re-entry sequence, not a full dataset-level claim.
- The annotation files are manually derived and should remain traceable.
- TIM-MARS depends on the base tracker producing enough stable candidate tracks.
- A lower wrong-target ratio is prioritised over continuous output.
- Reports under `reports/` are generated artefacts and are not committed by default.
