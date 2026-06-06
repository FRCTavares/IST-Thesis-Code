# TIM evaluation protocol

Date: 2026-06-06

## Purpose

Define the active evaluation protocol for selected-target memory methods, including TIM-MARS.

TIM is evaluated as a selected-target control-safety layer, not as generic MOT.

## Required comparison

Every selected-target memory evaluation must compare:

1. raw tracker selected target, usually `/target`;
2. memory-filtered selected target, currently `/target_memory_mars`.

The comparison must use the same bag, same annotation file, and same scoring step.

## Primary metrics

| Metric | Meaning |
|---|---|
| `correct_target_duration_s` | output is on the true selected person |
| `wrong_target_duration_s` | output is on the wrong person |
| `lost_target_duration_s` | no valid selected-target output while the selected person is visible |
| `correct_target_ratio` | correct duration divided by visible target duration |
| `wrong_target_ratio` | wrong duration divided by visible target duration |
| `lost_target_ratio` | lost duration divided by visible target duration |

## Safety priority

Wrong target is worse than LOST.

Therefore, a valid improvement may:

- reduce wrong-target duration;
- increase LOST duration;
- preserve or improve correct-target duration.

A method is not useful if it reduces wrong target only by destroying most correct output.

## Required evidence

Each major result must include:

1. raw baseline metrics;
2. TIM/TIM-MARS metrics;
3. annotation file path;
4. evaluated bag path;
5. generated report path;
6. visual audit or representative video evidence;
7. short interpretation.

## Current trusted annotation files

Hard re-entry active annotations:

- `docs/annotations/hard_reentry/bytetrack_tim_mars_final.csv`
- `docs/annotations/hard_reentry/deepsort_mars_target1_final.csv`
- `docs/annotations/hard_reentry/ocsort_tim_mars_r1.csv`

Older annotations are archived under:

- `docs/archive/annotations/`

## Current evaluation command pattern

Use:

- `tools/analysis/evaluate_tim_target_correctness.py`

Required arguments:

- bag path;
- `--annotations`;
- `--out-dir`;
- `--raw-topic`;
- `--tim-topic`;
- `--step-s`.

Typical topics:

- raw topic: `/target`;
- TIM-MARS topic: `/target_memory_mars`.

Current scoring step:

- `--step-s 0.05`

## Generated reports

Generated reports should go under:

- `reports/final_selected_target_tracking/`

Reports are generated artefacts and are ignored by Git.

Curated conclusions should be written under:

- `docs/results/selected_target_tracking/`

## Visual audit rule

For the current source-image status audit renderer, use:

- `--eval-time-scale 2.0`

Do not confuse this with annotation time scaling.

The rejected values for the current hard re-entry audit were:

- `1.0`, because boxes were time-misaligned;
- `4.0`, because boxes were time-misaligned.

## Current active result source

Use this file as the current hard re-entry result source:

- `docs/results/selected_target_tracking/hard_reentry_multi_tracker_summary.md`

## Generalisation requirement

The current hard re-entry result is strong but not sufficient for a full thesis claim.

Before making broad claims, evaluate at least:

1. clean single-person tracking;
2. two-person no crossing;
3. hard crossing;
4. hard re-entry;
5. short occlusion;
6. longer occlusion;
7. small or far person;
8. similar-clothing distractor if available.

## Reporting rule

No future TIM claim should be accepted without:

- raw baseline;
- TIM variant result;
- correctness table;
- annotation source;
- visual evidence;
- short safety interpretation.
