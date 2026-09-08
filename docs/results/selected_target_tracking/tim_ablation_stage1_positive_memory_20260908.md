# TIM-MARS Stage-1 positive-memory ablations — 8 September 2026

Development-only evidence. H01/H02/H03 were not accessed or captured.

## Provenance note

- The retained selected replays predate explicit development-ablation-control provenance in `tim_mars_resolved_runtime.json`.
- Their selected semantic and candidate-stream digests remain the historical behavior contract; the later treatment controls are recorded explicitly only on the new ablation replays.

## Default-off neutrality

- Seq03 default-off semantic SHA-256 reproduces the selected reference exactly: `307c9c3c2d5ad0f468a452ec8b753552a276e51d3fcd85381158bc13c93811ca`.

## AB-07 — trusted-gallery storage

| Sequence | Correct Δ (s) | Wrong Δ (s) | LOST Δ (s) |
| --- | ---: | ---: | ---: |
| may | -0.066389537 | +0.000000000 | +0.066389537 |
| seq01 | +0.000000000 | +0.000000000 | +0.000000000 |
| seq03 | -2.001367555 | +0.000000000 | +2.001367555 |
| seq04 | -4.565239276 | +0.000000000 | +4.565239276 |

- Aggregate development-sequence correct-authority delta: -6.632996368 s.
- Aggregate wrong-person-authority delta: +0.000000000 s.
- Classification: useful, context-specific availability support.
- Decision: retain trusted-gallery storage.

## AB-08 — adaptive positive representation

| Sequence | Correct Δ (s) | Wrong Δ (s) | LOST Δ (s) |
| --- | ---: | ---: | ---: |
| may | +0.000000000 | +0.000000000 | +0.000000000 |
| seq01 | +0.000000000 | +0.000000000 | +0.000000000 |
| seq03 | -2.031639277 | +0.000000000 | +2.031639277 |
| seq04 | -2.199463314 | +0.000000000 | +2.199463314 |

- Aggregate development-sequence correct-authority delta: -4.231102591 s.
- Aggregate wrong-person-authority delta: +0.000000000 s.
- Classification: useful, context-specific availability support.
- Decision: retain the adaptive positive representation.

## AB-16 — repeated-source adaptive EMA reinforcement

| Sequence | Correct Δ (s) | Wrong Δ (s) | LOST Δ (s) | Adaptive updates | States |
| --- | ---: | ---: | ---: | ---: | --- |
| may | +0.000000000 | +0.000000000 | +0.000000000 | 800 → 219 | equal |
| seq01 | +0.000000000 | +0.000000000 | +0.000000000 | 1512 → 231 | equal |
| seq03 | +0.000000000 | +0.000000000 | +0.000000000 | 524 → 124 | equal |
| seq04 | +0.000000000 | +0.000000000 | +0.000000000 | 839 → 718 | equal |

- Aggregate reported trusted adaptive-memory updates: 3675 → 1292 (64.84% reduction).
- Controller-facing duration buckets and state counts are unchanged on all four development sequences.
- This is not a MARS embedding/inference workload reduction.
- Classification: repeated-source adaptive reinforcement is controller-facing redundant on the available development evidence.
- Decision: AB-16 remains a simplification/hardening candidate.

## Positive-memory Stage-1 decision

- Retain the protected anchor.
- Retain trusted-gallery storage.
- Retain the adaptive positive representation.
- Do not repeatedly reinforce the adaptive EMA from the same source image; AB-16 is the development-supported simplification candidate.
- No canonical behavior or #27 prospective held-out freeze is changed by this development-only decision.
