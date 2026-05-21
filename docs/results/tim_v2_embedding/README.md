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
