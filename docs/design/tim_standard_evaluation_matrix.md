# TIM Standard Evaluation Matrix

Date: 2026-05-20

## Purpose

Define a repeatable evaluation matrix for Raw vs TIM variants.

TIM must be evaluated as a selected-target control-safety layer, not as generic MOT.

## Compared methods

Minimum comparison:

1. Raw selected tracker ID
2. TIM-V0 geometry memory
3. TIM-V1 appearance HSV
4. TIM-V2K rank-aware reacquisition
5. TIM-V2E learned appearance candidate, offline only for now

## Scenario categories

Each scenario should belong to one or more categories:

- clean tracking
- crossing
- occlusion
- hard re-entry
- tracker ID switch
- visible target but wrong best candidate
- target absent
- ambiguous visibility

## Required outputs per scenario

Each evaluated scenario must produce:

1. `summary.md`
2. `timeline.csv`
3. overlay video or exported review frames
4. short interpretation note under `docs/results/...`

## Primary metrics

| Metric | Meaning |
|---|---|
| correct_s | control-valid output on true selected person |
| wrong_s | control-valid output on wrong person |
| lost_s | no control-valid selected target while target is visible |
| target_absent_valid_s | unsafe output while selected target is absent |
| correct_ratio | correct_s / visible scored time |
| wrong_ratio | wrong_s / visible scored time |
| lost_ratio | lost_s / visible scored time |

## Control-safety priority

Wrong target is worse than LOST.

Therefore, a valid improvement may:

- reduce wrong_s,
- increase lost_s,
- preserve or improve correct_s.

A method is not useful if it reduces wrong_s only by destroying most correct_s.

## Visual evidence requirement

For every major metric claim, include visual evidence:

- overlay frame examples,
- or an overlay video.

At minimum, show:

- one correct Raw/TIM interval,
- one Raw wrong / TIM correct interval,
- one Raw wrong / TIM lost interval,
- one failure interval.

## Current best TIM-V2E candidate

Current offline candidate:

- Tiny16 hybrid embedding,
- runtime top-2 margin gate,
- selected low similarity threshold 0.0,
- candidate high similarity threshold 0.3,
- confirmation frames 3.

This candidate must be tested on more bags before live integration.
