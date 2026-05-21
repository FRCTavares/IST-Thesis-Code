# Critical crossing standard comparison

Date: 2026-05-21

## Purpose

Evaluate the selected TIM-V2E configuration on the critical-crossing scenario using the same standard comparison logic as the hard-reentry case.

## Inputs

- Automatic annotation: `docs/annotations/tim_v1m_appearance_critical_crossing/target_correctness_annotations.csv`
- Manual video-review annotation: `docs/annotations/tim_v2e_video_review_critical_crossing/target_correctness_annotations.csv`
- Selected V2E result: `reports/tim_v2_embedding/v2e_hybrid_critical_crossing_runtime_margin010_thr0_high03_c3/summary.md`
- Generated local summary: `reports/tim_standard_matrix/critical_crossing/summary.md`

## Selected TIM-V2E configuration

- Tiny16 hybrid embedding
- Runtime top-2 margin gate
- Runtime margin threshold: 0.10
- Selected low similarity threshold: 0.0
- Candidate high similarity threshold: 0.3
- Reacquire confirmation frames: 3
- Max similarity time delta: 0.10 s

## Automatic offline result

| Metric | Raw | TIM-V2E policy |
|---|---:|---:|
| correct_s | 12.116 | 29.971 |
| wrong_s | 27.739 | 0.046 |
| lost_s | 0.000 | 9.839 |

## Interpretation

The automatic interval evaluation supports TIM-V2E as a wrong-target suppression mechanism on critical crossing.

The key result is not just more valid target time. The important result is that dangerous wrong-person following is almost eliminated:

- Raw output follows the wrong target for 27.739 s.
- TIM-V2E policy reduces wrong-target time to 0.046 s.
- Some wrong-target intervals become LOST.
- Some intervals are correctly reacquired.

From a UAV control-safety perspective, this is the desired trade-off: LOST is safer than confidently following the wrong person.

## Manual video-review caution

The manual video-review annotation is more conservative and suggests that the visually dominant failure mode remains LOST/reacquisition failure after the selected target passes behind a distractor and returns under a new tracker ID.

Therefore, the thesis claim should remain narrow:

1. TIM-V2E can reduce wrong-person following in hard crossing and re-entry scenarios.
2. TIM-V2E does not yet fully solve robust reacquisition after difficult occlusions.
3. More bags and runtime-state gates are needed before live integration.

## Decision

Keep critical crossing as a standard comparison scenario.

Use it as evidence for wrong-target suppression, but also report it as a limitation case for full reacquisition robustness.

Do not integrate TIM-V2E live yet.
