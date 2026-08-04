# P044 observational multi-run audit

Execution commit: `ea1868fdbe807a3039d03cb857c3792150c34f34`

This compact package audits all six recorded Hailo conditions from the
three-repetition guarded-Hailo matrix. The raw paired MARS 128D and RepVGG
512D vectors remain outside the repository and are not promoted.

## Aggregate extraction

- Runs: 6
- Requests: 1692
- RepVGG results: 1331
- Paired exact-crop observations: 1331
- Rejected observations: 361
- Rejection reasons: {'missing_repvgg_result': 361}
- Candidate frames: 1097
- Multi-candidate frames: 232
- Repeated run/track histories: 32
- Histories with at least five observations:
  18
- Paired observations with TIM status context:
  1331

## Interpretation

The recordings contain exact-crop paired observations, multi-candidate
frames, repeated per-track histories, and CPU-authoritative TIM status
context. These are sufficient inputs for the next independent
within-model ranking-agreement implementation.

This package does not compare a 128D MARS vector directly with a 512D
RepVGG vector. It does not calculate ranking agreement, target-decision
equivalence, or safety equivalence. CPU MARS remains authoritative,
runtime behaviour is unchanged, and canonical policy remains
`all_candidates`.

The exact CPU target-decision status field must be confirmed manually
before decision-equivalence metrics are implemented.
