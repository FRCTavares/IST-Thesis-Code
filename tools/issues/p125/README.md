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
  identity, and episode-count checks. It hashes both source archives and
  both audit files, and writes a deterministic `draft_not_frozen` manifest.
- `evaluate_visdrone_selected_person.py` defines the four primary
  physical-person frame buckets and scores one selected identity through its
  last target observation. Missing GT rows stay outside the primary denominator.
  Core wrong-person, handover, LOST-run, first output after LOST,
  reference-gap/reacquisition and attributable target tracker-ID-change events
  are derived from source-frame records. The scorer requires one explicit
  output entry for every source
  frame from selection through the final target GT observation, including GT
  gaps; `None` means no controller output. Runtime-stream integration remains
  pending.
- `controller_output_adapter.py` maps the four raw tracker backend outputs,
  Target-ReID publications, and control-valid TIM-MARS publications into the
  scorer's box and tracker-ID maps. Suppressed TIM-MARS candidate belief is
  excluded. These adapters are synthetic-tested; they do not execute runtimes.
- `analyse_visdrone_selected_person_statistics.py` implements fixed-seed
  paired episode effects, source-sequence cluster bootstrap and the primary
  cluster sign-flip test. It has only been exercised on synthetic data.

These tools do not read architecture outcomes during protocol preparation.

The first implementation stage is deliberately outcome-blind. Do not add
architecture outcome generation here until
`docs/data/external_benchmark_v2/visdrone_selected_person_protocol_v1.json`
has been reconciled from the GT-only audit and changed from
`draft_not_frozen` to `frozen` in a dedicated committed checkpoint.
