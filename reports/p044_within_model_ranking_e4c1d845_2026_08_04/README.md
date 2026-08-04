# P044 within-model ranking analysis

This package records the independent within-model comparison between the
CPU MARS-small128 embedding space and the observational Hailo RepVGG 512D
embedding space.

The two vector spaces are never compared directly. Each candidate is
scored against a causal model-specific target gallery in its own embedding
space. The current frame is evaluated before its embedding can enter the
gallery.

## Primary cohort

The primary gallery contains only prior paired target observations whose
CPU-authoritative TIM status reported `positive_memory_updated`.

- Evaluated frames: 75
- Top-1 MARS/RepVGG agreement: 70/75 (93.33%)
- Pairwise ordering agreement: 71/77 (92.21%)
- RepVGG agreement with CPU `best`: 70/75 (93.33%)

## Strict complete-candidate cohort

The strict cohort additionally requires the paired candidate IDs to match
the full CPU `all_scores` candidate set and requires CPU `best` to be
present.

- Evaluated frames: 64
- Top-1 MARS/RepVGG agreement: 64/64 (100%)
- Pairwise ordering agreement: 65/66 (98.48%)
- RepVGG agreement with CPU `best`: 64/64 (100%)

## Guarded-state limitation

The complete agreement does not hold for incomplete asynchronous guarded
frames.

- `all_candidates_hailo`: 59/59 top-1 agreement
- `ambiguity_guarded_hailo`: 11/16 top-1 agreement
- `LOST`: 3/6 top-1 agreement
- `UNCERTAIN`: 4/6 top-1 agreement

All five primary top-1 disagreements occurred in non-strict
`ambiguity_guarded_hailo` frames during `LOST` or `UNCERTAIN`.

## Decision

The evidence supports ranking preservation when the complete candidate set
is available. It does not support general RepVGG ranking equivalence in
the guarded states where asynchronous candidate loss occurs.

RepVGG therefore remains observational. CPU MARS remains authoritative,
runtime behaviour is unchanged, and canonical policy remains
`all_candidates`.

Failure-injection fallback, BEST_EFFORT reliability, safety equivalence,
and sustained onboard operation remain unvalidated.
