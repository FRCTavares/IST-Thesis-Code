# TIM Standard Matrix — Hard Re-entry OCSORT Target 1

Date: 2026-05-20

## Scenario

Scenario:

- hard re-entry / tracker ID switch
- tracker: OCSORT
- selected target: initial track ID 1
- source bag: `2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_on__target_1`

This scenario is relevant because raw selected-ID following can remain attached to the wrong person after crossing/re-entry.

## Compared outputs in this first standard package

This first standard package compares:

1. Raw selected tracker-ID output
2. TIM-V2E offline runtime-margin candidate

TIM-V2E candidate:

- Tiny16 hybrid embedding
- runtime top-2 margin gate
- margin threshold: 0.10
- selected low similarity threshold: 0.0
- candidate high similarity threshold: 0.3
- reacquire confirmation frames: 3
- max similarity time delta: 0.10 s

Note: TIM-V2E is offline-only at this stage. It is not live-integrated.

## Automatic timeline result

Source:

- `reports/tim_v2_embedding/v2e_hybrid_hard_reentry_runtime_margin010_thr0_high03_c3/summary.md`

| Metric | Raw | TIM-V2E offline | Delta |
|---|---:|---:|---:|
| correct_s | 68.932 | 72.553 | +3.621 |
| wrong_s | 35.613 | 16.901 | -18.712 |
| lost_s | 0.000 | 15.090 | +15.090 |

Interpretation:

- TIM-V2E reduces wrong selected-target output substantially.
- TIM-V2E increases correct output slightly.
- The cost is increased LOST time.
- For UAV control, this is a favourable direction because wrong-person following is worse than LOST.

## Manual video-review result

Source:

- `docs/annotations/tim_v2e_video_review_hard_reentry/target_correctness_annotations.csv`
- `reports/tim_v2_embedding/video_review_eval/summary.md`

| Metric | Raw | TIM-V2E video review | Delta |
|---|---:|---:|---:|
| correct_s | 83.920 | 86.680 | +2.760 |
| wrong_s | 31.870 | 20.880 | -10.990 |
| lost_s | 8.680 | 16.910 | +8.230 |

Interpretation:

- Manual visual review confirms the same qualitative trend.
- TIM-V2E reduces visually confirmed wrong-person following.
- Some unsafe wrong output becomes LOST, which is safer for control.

## Tiny16 CPU latency

Source:

- `reports/tim_v2_embedding/tiny16_hybrid_latency_cpu/summary.md`

| Batch | mean_ms | p95_ms | per_crop_p95_ms |
|---:|---:|---:|---:|
| 1 | 1.901 | 2.126 | 2.126 |
| 2 | 2.329 | 2.378 | 1.189 |

Interpretation:

- Tiny16 CPU inference is feasible for event-triggered use.
- Hailo should remain dedicated to detector inference.
- Tiny16 should run on CPU only during ambiguity/re-entry events.

## Visual evidence

Available visual output:

- `reports/tim_v2_embedding/videos/hard_reentry_raw_vs_tim_v2e_learned.mp4`
- exported review frames under `reports/tim_v2_embedding/video_review_frames/hard_reentry`

Important observed behaviour:

- Raw remains on wrong ID 1 after re-entry.
- TIM-V2E sometimes reacquires the correct target, for example ID 96.
- TIM-V2E also sometimes outputs LOST instead of following the wrong person.

## Current conclusion

This scenario supports a narrow but useful claim:

> In a hard re-entry / ID-switch scenario, TIM-V2E learned appearance reduces wrong-person following compared with raw selected-ID tracking, with the expected trade-off of more LOST time.

This is a control-safety improvement.

## Limits

This result does not yet prove generalisation.

Remaining requirements:

1. compare against TIM-V0, TIM-V1, and TIM-V2K in the same standard matrix format,
2. repeat on more scenario categories,
3. convert TIM-V2E from offline simulation to real runtime TIM-state gates,
4. verify crop extraction and full TIM callback latency,
5. validate on held-out bags.
