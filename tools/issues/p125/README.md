# tools/issues/p125

Last reviewed: 2026-09-29

## P125 — Public VisDrone selected-person benchmark

Issue #125 adds the final broad public-dataset selected-person evaluation.

This directory is intentionally issue-scoped because the benchmark has a
prospective pre-result freeze contract. Reusable production algorithms stay in
their existing locations and must not be copied here.

Current pre-result tooling:

- `audit_visdrone_selected_person_corpus.py` performs the GT-only corpus and
  frame-domain audit. It may read source images and official VisDrone ground
  truth only. It must not read detector, tracker, Target-ReID, TIM-MARS, or
  previous result artifacts.
- `build_visdrone_gt_only_episode_manifest.py` combines the train and
  validation audits only after reconciled frame-domain, eligibility-config,
  identity, and episode-count reconciliation. It hashes both source archives
  and both audit files, and writes a deterministic `draft_not_frozen` manifest.
  It never reads architecture outcomes.

The first implementation stage is deliberately outcome-blind. Do not add
architecture outcome generation here until
`docs/data/external_benchmark_v2/visdrone_selected_person_protocol_v1.json`
has been reconciled from the GT-only audit and changed from
`draft_not_frozen` to `frozen` in a dedicated committed checkpoint.
