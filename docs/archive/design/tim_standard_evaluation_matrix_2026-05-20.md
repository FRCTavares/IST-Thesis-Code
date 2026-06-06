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

## Generalisation requirement

TIM is useful only if it improves selected-target control safety beyond the two development bags.

Future evaluations must cover:

1. clean two-person no crossing,
2. hard re-entry ID switch,
3. critical crossing,
4. short occlusion,
5. target leaves/re-enters,
6. similar-clothing distractor if available,
7. longer-distance or small-target case.

## Reporting rule

No future TIM claim should be accepted without:

- Raw baseline,
- TIM variant result,
- correctness table,
- visual evidence,
- short interpretation.

## Flight-safety rule

Live flight should only use documented, explicitly enabled TIM behaviour.

Experimental learned TIM-V2E models remain offline-only until:

1. runtime implementation exists behind explicit flags,
2. default live behaviour remains unchanged,
3. crop extraction and end-to-end callback latency are measured,
4. held-out bag evaluation is complete.

## Next candidate work after initial standard comparisons

Date: 2026-05-21

The current standard comparison evidence supports TIM-V2E as the best available wrong-target suppression candidate, but not yet as a complete reacquisition solution.

### Current scenario status

| Scenario | Current use | Interpretation |
|---|---|---|
| Hard re-entry | Positive evidence | TIM-V2E reduces wrong-person following, with more LOST time |
| Critical crossing | Mixed evidence / limitation | TIM-V2E suppresses wrong target in automatic evaluation, but manual review still shows difficult reacquisition |

### Next method candidate

The next method candidate should be TIM-V2F Conservative Reacquisition Memory.

Objective:

- preserve TIM-V2E wrong-target suppression,
- reduce LOST time after occlusion,
- avoid increasing wrong-target duration,
- keep the method offline-only until validated on more bags.

Main mechanisms to test:

1. frozen pre-loss appearance template,
2. CANDIDATE/probation state before REACQUIRED,
3. asymmetric stay-locked versus reacquire thresholds,
4. no memory update while ambiguous,
5. optional small template memory bank.

### Evaluation rule

A candidate policy is only better if:

| Metric | Rule |
|---|---|
| wrong_s | must not increase meaningfully |
| correct_s | should increase |
| lost_s | should decrease |
| video review | must remain visually explainable |
| control interpretation | LOST/CANDIDATE must be safer than wrong-person output |

### Next scenario coverage needed

Before live integration, add at least one scenario from each group:

| Group | Purpose |
|---|---|
| Clean single-person | Verify no unnecessary suppression |
| Two-person no crossing | Verify no over-conservative behaviour |
| Hard re-entry | Measure wrong-target suppression |
| Critical crossing | Measure reacquisition limits |
| Long occlusion | Verify conservative LOST behaviour |
| Similar clothing distractor | Stress appearance ambiguity |
| Small/far person | Stress tiny-person handling |

### Current live-integration decision

Do not integrate TIM-V2E or TIM-V2F live yet.

The next safe step is offline policy simulation plus standard comparison reports. Live integration should wait until a policy reduces LOST or improves reacquisition without increasing wrong_s across multiple scenarios.

