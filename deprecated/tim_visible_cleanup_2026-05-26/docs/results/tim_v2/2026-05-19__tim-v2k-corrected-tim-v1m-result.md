# TIM-V2K Corrected TIM-V1M Result

Date: 2026-05-19

## Context

A timing mismatch was found in the earlier TIM-V1M analysis: the replay extraction selected target ID 1 too early, before the annotated operator-selection time.

Corrected extraction uses:

- `select_delay_s=20.40`
- corrected all-scores file: `reports/tim_v2_sources/tim_v1m_appearance_critical_crossing/target_memory_all_scores__tm_extract_select20p40.csv`

## Sanity Checks

Corrected oracle result:

| Policy | Correct | Wrong | Lost |
|---|---:|---:|---:|
| always_lost | 0.000 | 0.000 | 1.000 |
| rank0 | 0.509 | 0.431 | 0.060 |
| oracle_if_present | 0.901 | 0.000 | 0.099 |

This confirms that the corrected score/annotation pair is valid and that naive rank-0 selection is unsafe.

## TIM-V2K Policy

TIM-V2K changes LOST-state reacquisition from rank-0 selection to rank-aware appearance-driven selection.

Instead of selecting the highest total-score candidate, TIM-V2K scans all plausible candidates and selects the best candidate by appearance evidence, subject to basic geometry and confidence constraints.

Best corrected TIM-V2K configuration:

| Parameter | Value |
|---|---:|
| lock_min_total | 0.30 |
| lock_min_geom | 0.10 |
| lost_min_total | 0.40 |
| lost_min_geom | 0.10 |
| lost_min_app | 0.05 |
| lost_app_margin | 0.03 |
| lost_confirm_frames | 1 |
| missing_ttl_frames | 8 |
| appearance_source | appearance_raw |

## Result

| Method | Correct | Wrong | Lost |
|---|---:|---:|---:|
| rank0 baseline | 0.509 | 0.431 | 0.060 |
| TIM-V2K | 0.613 | 0.120 | 0.266 |

TIM-V2K reduces wrong-target ratio from 0.431 to 0.120.

Relative wrong-target reduction:

`(0.431 - 0.120) / 0.431 = 72.2%`

Correct-target ratio also improves from 0.509 to 0.613, at the cost of increased LOST output.

## Failure Analysis

TIM-V2K correctly tracks:

- ID 1 before the first occlusion,
- ID 9 after the first hard re-entry,
- ID 10 after the second re-entry.

The remaining main issue is the interval:

`56.11-70.55 s`

where the annotated correct ID is 11, but distractors or duplicate fragments may compete.

## Same-Person Duplicate Issue

An alias-aware audit showed that ID 18 appears to be a near-duplicate or track fragment of the same selected person as ID 11.

For the upper-body frozen-HSV policy:

| Evaluation | Correct | Wrong | Lost |
|---|---:|---:|---:|
| strict | 0.342 | 0.499 | 0.159 |
| alias-aware, 11/18 treated as same person | 0.608 | 0.233 | 0.159 |

This shows that strict single-ID evaluation can over-penalise same-person duplicate fragments. However, TIM-V2L still has higher true wrong output than TIM-V2K and is not the current best policy.

## Current Conclusion

TIM-V2K is the strongest current offline candidate.

It provides a control-safety improvement by substantially reducing wrong-person following while preserving more correct target availability than conservative LOST-only policies.

The next implementation target should be TIM-V2K-style rank-aware appearance reacquisition, with careful handling of duplicate same-person fragments in evaluation.
