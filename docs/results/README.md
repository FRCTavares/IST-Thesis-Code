# Current thesis results

This directory contains reviewed result summaries that are still relevant to
the thesis, current engineering validation, or active claim boundaries.

## Selected-target tracking

Use:

- `selected_target_tracking/hard_reentry_multi_tracker_summary.md`
- `selected_target_tracking/p028_wrong_oracle_audit.md`
- `selected_target_tracking/hard_reentry_compute_throughput_summary.md`
- `selected_target_tracking/p023_output_freshness_validation.md`

The evidence-version authority is:

- `../algorithm/tim_mars_evidence_versions.md`

Do not merge values from different evidence versions without explicitly
recording the configuration, tracker, sequence, annotation, oracle, and
repository commit.

## Live-system validation

Current retained live and ground evidence is under `live/`.

These documents validate specific authority, coordinate, freshness, recovery,
or host-operation contracts. They are not substitutes for the final held-out
selected-person evaluation.

## Promotion rule

Generated outputs remain under `reports/`. A generated result may be promoted
here only when its provenance is complete, its interpretation is reviewed, and
its limitations are explicit.

Superseded TIM-V2, TIM-V2Q, active-MARS, conservative-MARS, and early
DeepSORT-versus-TIM interpretations are stored under `../archive/results/`.
