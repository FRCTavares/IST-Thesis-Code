# TIM-V2E Embedding Results

This folder contains the current curated TIM-V2E result documents.

Older exploratory notes were moved to:

- `deprecated/docs/results/tim_v2_embedding/`

## Current active result chain

Read these in order:

1. `2026-05-20__hybrid-runtime-margin-gate-result.md`
2. `2026-05-20__runtime-margin-sweep-result.md`
3. `2026-05-20__tiny16-cpu-latency-result.md`
4. `2026-05-20__video-review-evaluation-result.md`

## Current TIM-V2E status

TIM-V2E learned appearance is offline-only.

Current best offline candidate:

- Tiny16 hybrid embedding,
- runtime top-2 margin gate,
- selected low similarity threshold: 0.0,
- candidate high similarity threshold: 0.3,
- confirmation frames: 3,
- CPU inference feasible for event-triggered use.

Do not live-integrate yet.

## Interpretation

TIM-V2E currently supports a narrow claim:

- it reduces wrong-person following in hard re-entry and critical crossing simulations,
- it does this by converting unsafe wrong output into correct reacquisition or LOST,
- it still needs more bags and runtime-state integration before flight use.

## Historical results

Intermediate HSV, triplet, suppression-only, source-filtering, and dataset-building notes are preserved under:

- `deprecated/docs/results/tim_v2_embedding/`

## Next work after standard matrix checkpoint

Date: 2026-05-21

Current verdict:

- TIM-V2E hybrid runtime margin gate is the current best wrong-target suppression candidate.
- It should be claimed as a wrong-target suppression layer, not as a fully solved reacquisition system.
- TIM-V2E remains offline-only and should not be live-integrated yet.

Next method candidate:

- TIM-V2F Conservative Reacquisition Memory.

Main mechanisms to test:

1. frozen pre-loss appearance template,
2. CANDIDATE/probation state before REACQUIRED,
3. asymmetric stay-locked versus reacquire thresholds,
4. no memory update while ambiguous,
5. optional small template memory bank.

Acceptance rule:

- wrong_s must not meaningfully increase,
- correct_s should increase,
- lost_s should decrease,
- overlay/video review must remain explainable.

Detailed next-work plan is maintained in:

- `docs/design/tim_standard_evaluation_matrix.md`

