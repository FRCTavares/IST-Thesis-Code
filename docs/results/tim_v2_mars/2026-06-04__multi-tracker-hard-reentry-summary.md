# Multi-tracker TIM-MARS hard-reentry summary

Date: 2026-06-04

Sequence:
2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_off__target_1

## Problem

This evaluation tests whether TIM-MARS improves selected-target robustness after occlusion, identity switches, and target re-entry.

The metric is selected-target correctness over the visible-target interval:

- correct_target_duration_s
- wrong_target_duration_s
- lost_target_duration_s
- correct_target_ratio
- wrong_target_ratio
- lost_target_ratio

Core safety rule:

Wrong target is worse than LOST.

A useful TIM configuration must reduce wrong-target output without destroying correct output.

## ByteTrack configuration fix

ByteTrack was initially unstable because the shared tracker configuration was not suitable for its two-stage association logic.

Initial ID churn:

- sampled IDs: 1192
- unique IDs: 644
- max ID: 947

Main causes:

- min_score = 0.35 starved ByteTrack of low-score recovery detections.
- match_thresh and second_match_thresh were treated like IoU thresholds, while the backend uses IoU distance.

Final ByteTrack configuration:

- tracker_type: bytetrack
- min_score: 0.2
- track_thresh: 0.5
- match_thresh: 0.8
- track_buffer: 30
- det_thresh: 0.2
- second_match_thresh: 0.5
- new_track_thresh: 0.6
- unconfirmed_match_thresh: 0.7

After the fix:

- sampled IDs: 2544
- unique IDs: 39
- max ID: 71

This made ByteTrack a usable base tracker for TIM-MARS.

## TIM-MARS conservative appearance fix

Strict conservative TIM-MARS was rejecting almost every frame when appearance was unavailable.

Observed in /target_memory_mars/status:

- LOST = 931
- UNCERTAIN = 18
- LOCKED = 3
- appearance_conservative_reject:no_appearance_used = 837

The fix introduced:

appearance_conservative_require_appearance: bool = False

Corrected logic:

- if conservative appearance filtering is enabled and appearance is available, similarity and margin checks are applied;
- if appearance is unavailable, the target is rejected only when appearance_conservative_require_appearance is true;
- otherwise, missing appearance does not automatically force LOST.

This preserves conservative appearance filtering when useful, without making missing or stale appearance a hard rejection condition in normal operation.

## Final ByteTrack result

Final trusted bag:

artifacts/bags/eval_matrix/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_off__target_1__tracker_bytetrack__tim_mars__target_1__r4

Final report:

reports/bytetrack_fixed_mars_nonstrict_conservative_eval_scaled4/

Final visual audit:

reports/bytetrack_fixed_mars_r4_visual_audit/bytetrack_mars_r4_tim_status_audit_scaled2.mp4

| Method | Correct [s] | Wrong [s] | Lost [s] | Correct ratio | Wrong ratio | Lost ratio |
|---|---:|---:|---:|---:|---:|---:|
| Raw ByteTrack | 185.790 | 31.100 | 53.680 | 0.687 | 0.115 | 0.198 |
| ByteTrack + TIM-MARS | 262.310 | 4.010 | 4.250 | 0.969 | 0.015 | 0.016 |

Interpretation:

ByteTrack fixed + TIM-MARS non-strict conservative is the best current result. It strongly improves correct target duration and almost eliminates wrong-target output while also reducing LOST.

## OCSORT comparison

Best OCSORT conservative result:

| Method | Correct [s] | Wrong [s] | Lost [s] |
|---|---:|---:|---:|
| Raw OCSORT | 131.150 | 96.700 | 43.510 |
| OCSORT + TIM-MARS conservative | 183.400 | 30.050 | 57.910 |

Interpretation:

OCSORT + TIM-MARS conservative is defensible. It significantly reduces wrong-target persistence while maintaining high correct output. However, ByteTrack fixed + TIM-MARS is stronger on this sequence.

## DeepSORT-MARS trade-off

DeepSORT uses the real MARS ReID model:

models/reid/mars-small128.pb

DeepSORT result:

| Method | Correct [s] | Wrong [s] | Lost [s] | Correct ratio | Wrong ratio | Lost ratio |
|---|---:|---:|---:|---:|---:|---:|
| Raw DeepSORT-MARS | 251.220 | 0.000 | 19.350 | 0.928 | 0.000 | 0.072 |
| DeepSORT-MARS + TIM-MARS | 249.820 | 13.750 | 7.000 | 0.923 | 0.051 | 0.026 |

Interpretation:

Raw DeepSORT-MARS is already a very strong baseline. TIM-MARS reduces LOST but introduces wrong output during occlusions. Under the rule that wrong target is worse than LOST, this is not a strict improvement. It is a continuity-versus-safety trade-off.

## SORT limitation

SORT is not defensible for this TIM-MARS configuration.

Observed behaviour:

- raw SORT is safe but weak, with high LOST;
- TIM-HSV or TIM-MARS can increase continuity, but often introduces wrong output;
- strict TIM-MARS becomes too conservative and loses most of the sequence.

Conclusion:

SORT is too fragmented. TIM either introduces wrong output or becomes too conservative.

## Visual audit note

For source-image status audit rendering, --eval-time-scale 2.0 was visually correct.

Rejected values:

- 1.0: time-misaligned boxes
- 4.0: time-misaligned boxes

Important distinction:

--eval-time-scale is a visual synchronisation parameter for rendering. It is not the same as the annotation scaling factor.

Do not overwrite these final audit videos:

- reports/bytetrack_fixed_mars_r4_visual_audit/bytetrack_mars_r4_tim_status_audit_scaled2.mp4
- reports/deepsort_mars_visual_audit/deepsort_mars_tim_status_audit_scaled2.mp4

## Current tracker verdict

Under the strict safety metric:

1. ByteTrack fixed + TIM-MARS non-strict conservative
2. Raw DeepSORT-MARS
3. OCSORT + TIM-MARS conservative
4. DeepSORT-MARS + TIM-MARS
5. Raw ByteTrack fixed
6. Raw OCSORT
7. SORT variants

## Thesis interpretation

TIM-MARS is most useful when the base tracker has recoverable identity instability.

Evidence:

- strong improvement for ByteTrack after configuration repair;
- strong wrong-target reduction for OCSORT;
- limited usefulness for DeepSORT-MARS because the base tracker is already stable;
- unsafe or unstable behaviour with SORT because the base tracker is too fragmented.

Core thesis position:

TIM-MARS is a selected-target memory layer that improves control-target robustness when the base tracker produces recoverable identity instability, but it must be configured conservatively because wrong-target output is worse than LOST.

## Limitations

- Results are currently based on one hard re-entry sequence.
- Annotation scaling and visual audit synchronisation must be kept separate.
- DeepSORT shows that TIM-MARS is not universally beneficial when the base tracker is already identity-stable.
- SORT shows that TIM-MARS cannot rescue a tracker that is too fragmented.
- Final claims should be framed around selected-target safety and robustness, not generic MOT improvement.
