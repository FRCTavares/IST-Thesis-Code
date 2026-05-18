# TIM-V2F/TIM-V2G Generalisation Test on TIM-V1M

Date: 2026-05-18

## Bag

`2026-05-11__11-31-27__video__tim_v1m_appearance_critical_crossing`

Annotation:

`docs/annotations/tim_v1m_appearance_critical_crossing/target_correctness_annotations.csv`

All-scores source:

`reports/tim_v2_sources/tim_v1m_appearance_critical_crossing/target_memory_all_scores__tm_extract.csv`

## Oracle Candidate Presence

| Metric | Value |
|---|---:|
| correct_present_ratio | 0.957 |
| correct_absent_ratio | 0.043 |
| correct_rank0_ratio | 0.672 |
| correct_rank1_ratio | 0.283 |
| correct_rank2plus_ratio | 0.001 |

The correct target is usually present in the candidate list, often as rank 0 or rank 1. Therefore, the bag is targetable from the candidate set.

## Fixed TIM-V2F Result

Using the fixed parameters selected from the hard-reentry bag:

| Parameter | Value |
|---|---:|
| runner_min_geom | 0.40 |
| runner_max_gap | 0.35 |
| runner_confirm_frames | 15 |
| reacquire_confirm_frames | 3 |

Result:

| Correct | Wrong | Lost |
|---:|---:|---:|
| 0.422 | 0.351 | 0.227 |

This does not generalise cleanly.

## TIM-V2F Sweep Result

With lost ratio constrained below 0.30, the best geometry-only runner-up result was approximately:

| Correct | Wrong | Lost |
|---:|---:|---:|
| 0.430 | 0.299 | 0.271 |

No configuration achieved `correct >= 0.60` while keeping `lost < 0.30`.

## TIM-V2G Appearance-Augmented Runner-Up Result

TIM-V2G added appearance evidence:

`evidence = geometry + app_weight * appearance_raw`

With lost ratio constrained below 0.30, the best result was:

| app_weight | Correct | Wrong | Lost |
|---:|---:|---:|---:|
| 0.10 | 0.446 | 0.280 | 0.274 |

Appearance improves wrong-target suppression slightly, but correct-target availability remains too low.

## Interpretation

TIM-V2F improves the first hard-reentry bag but does not generalise to the TIM-V1M appearance-critical crossing.

TIM-V1M is harder because the selected target and distractor repeatedly exchange dominance, and simple geometry or weak appearance evidence is insufficient to maintain the correct selected identity without either:

- following the wrong target, or
- becoming LOST/UNCERTAIN for too much of the visible interval.

## Consequence for TIM-V2

A universal geometry-only runner-up policy is not sufficient.

The next TIM-V2 direction should be a hybrid selected-target validity policy:

1. use runner-up recovery only when the runner-up is persistent and identity evidence is reliable,
2. suppress output when identity is contested,
3. use appearance only when it is computed and reliable,
4. otherwise prefer LOST/UNCERTAIN over wrong LOCKED output.

The goal should remain control safety and selected-target correctness, not simply increasing valid target duration.
