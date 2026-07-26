# P1.5 positive-memory bootstrap evidence

## Provenance

- Baseline commit: `055984a3867b5fb1bfc22615f052bc17831e61a3`
- Candidate commit: `f1fbb7994766080481fe8cf3b9acac9862867c9b`
- Evaluation date: 26 July 2026
- Aggregate gate: **PASS**
- Replay matrix: four baseline runs, four candidate runs, and one independent candidate Seq04 repeat
- Correctness and event-type evaluations: 8/8 passed

## Correctness comparison

| Sequence | Baseline correct [s] | Candidate correct [s] | Baseline wrong [s] | Candidate wrong [s] | Baseline lost [s] | Candidate lost [s] |
|---|---:|---:|---:|---:|---:|---:|
| may_hard_reentry | 62.513 | 62.513 | 0.100 | 0.100 | 5.087 | 5.087 |
| seq01_clean | 108.750 | 108.750 | 0.000 | 0.000 | 13.590 | 13.590 |
| seq03_crossing | 73.892 | 73.892 | 6.053 | 6.053 | 15.782 | 15.782 |
| seq04_occlusion | 39.593 | 39.593 | 0.000 | 0.000 | 17.229 | 17.229 |

The corrective candidate exactly matched the accepted baseline for correct, wrong, lost, and target-absent output duration on all four sequences.

## Bootstrap provenance

| Role | Sequence | Selected ID | Accepted frame | Appearance source frame | Action | Gate |
|---|---|---:|---:|---:|---|---|
| candidate | may_hard_reentry | 1 | 106 | 104 | protected_anchor_bootstrap | PASS |
| candidate | seq01_clean | 1 | 335 | 335 | protected_anchor_bootstrap | PASS |
| candidate | seq03_crossing | 2 | 271 | 271 | protected_anchor_bootstrap | PASS |
| candidate | seq04_occlusion | 1 | 217 | 217 | protected_anchor_bootstrap | PASS |
| candidate_repeat | seq04_occlusion_repeat | 1 | 217 | 217 | protected_anchor_bootstrap | PASS |

Every candidate sequence emitted exactly one valid bootstrap event with supported operator lineage, eligible crop provenance, no ambiguity, and no hard-negative rejection.

The corrective May hard-reentry case accepted frame `106` using appearance sourced from frame `104`. Transient policy suppression therefore no longer imitates true tracker-ID absence.

## Repeatability

- Semantic digest schema: `tim_mars_replay_generated_fields_v2`
- Candidate semantic SHA-256: `f5b6e14c8801e9f0286f2eb8971e4c2379fb0f4430e95018e6bc96bc385819f2`
- Repeat semantic SHA-256: `f5b6e14c8801e9f0286f2eb8971e4c2379fb0f4430e95018e6bc96bc385819f2`
- Repeatability gate: **PASS**

Resolved-runtime artifact fingerprints differ between executions, but runtime arguments, canonical configuration, model, source manifest, topic contract, message counts, bootstrap event, and generated semantic output are equal.

## Evidence contents

- `evaluation/evaluation_gate.json`
- `evaluation/correctness_comparison.json`
- `evaluation/correctness_comparison.md`
- `evaluation/bootstrap_event_audit.json`
- `evaluation/repeatability.json`
- `evaluation/correctness/`
- `evaluation/event_type/`
- `provenance/replay_manifest.tsv`
- `provenance/matrix_provenance.txt`
- `provenance/metadata/`

## Conclusion

P1.5 is accepted. Unsupported same-ID lineage cannot define immutable operator appearance memory. Legitimate pre-anchor authorization survives transient policy suppression only while the usable operator ID remains continuously present.
