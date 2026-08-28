# Promoted evidence package register

`reports/` is git-ignored (`/reports/*`). The packages below are the only
`reports/` contents deliberately force-added as reviewed exceptions, per the
policy in `reports/README.md`.

This file is a register, not an authority. It records what is tracked and where
each package is referenced. It does not restate scientific claims. The claim
boundaries are owned by:

- `docs/algorithm/tim_mars_evidence_versions.md` (evidence versions and claim limits);
- `docs/data/catalogue/tim_evidence_versions.json` (machine-readable);
- `docs/data/final_experiment_inventory.md` (final bags, reports, annotations);
- `docs/results/` (reviewed human-facing summaries);
- each package's own `README.md` or `closure_summary.md`.

Each package also carries `commands.md` / `run_metadata.json` /
`*_resolved_runtime.json` / `SHA256SUMS` provenance sidecars.

## Tracked packages

| Package | Package title (from its own docs) | Promoted | Package doc | Referenced from `docs/` |
| --- | --- | --- | --- | --- |
| `p002_historical_deepsort_93e047b5_2026_07_19` | P0.2 Historical Unsafe DeepSORT Reproduction | 2026-07-20 | `README.md` | `docs/data/catalogue/tim_eval_catalogue.yaml` |
| `p004_ocsort_tim_1b7dc400_2026_07_20` | P0.4 Clean OC-SORT Sequence Evidence | 2026-07-20 | `README.md` | `tim_eval_catalogue.yaml`, `tim_evidence_versions.json`, `docs/results/selected_target_tracking/hard_reentry_multi_tracker_summary.md` |
| `p004_tim_matrix_1b7dc400_2026_07_20` | P0.4 Clean Canonical Matrix Evidence | 2026-07-20 | `README.md` | `tim_eval_catalogue.yaml`, `tim_evidence_versions.json`, `hard_reentry_multi_tracker_summary.md` |
| `p006b_hard_negative_03409564_2026_07_21` | Issue #6 — Hard-negative structural safety evidence | 2026-07-21 | `closure_summary.md` (no `README.md`) | `docs/algorithm/tim_mars_evidence_versions.md`, `tim_evidence_versions.json`, `docs/design/tim_tooling_index.md` |
| `p007_rank_aware_add2b8b8_2026_07_21` | Issue #7 — Rank-aware bypass safety evidence | 2026-07-21 | `closure_summary.md` (no `README.md`) | `tim_mars_evidence_versions.md`, `tim_evidence_versions.json`, `tim_tooling_index.md` |
| `p014_protected_appearance_2026_07_17` | P1.4 Protected and Adaptive Appearance Memory | 2026-07-18 | `README.md` | `tim_eval_catalogue.yaml` |
| `p015_positive_memory_bootstrap_f1fbb799_2026_07_26` | P1.5 positive-memory bootstrap evidence | 2026-07-26 | `README.md` | not referenced from `docs/` |
| `p017_fragment_safety_f1049263_2026_07_27` | P1.6 target-fragment hard-negative safety evidence | 2026-07-27 | `README.md` | not referenced from `docs/` |
| `p018_hard_negative_lifecycle_6ba28c61_2026_07_28` | P1.7 hard-negative lifecycle evidence | 2026-07-28 | `README.md` | not referenced from `docs/` |
| `p018_ocsort_tim_2d1ae5e9_2026_07_19` | P0.18 OC-SORT Sequence Evidence Package | 2026-07-19 | `README.md` | not referenced from `docs/` |
| `p018_tim_matrix_36ecd17d_2026_07_19` | P0.18 Four-Tracker Evidence Package | 2026-07-19 | `README.md` | not referenced from `docs/` |
| `p044_guarded_cpu_matrix_7c4bedad_2026_08_03` | Issue #44 guarded CPU ReID workload matrix | 2026-08-04 | `guarded_cpu_matrix_analysis.md` (no `README.md`) | not referenced from `docs/` |
| `p044_guarded_hailo_load_175d3279_2026_08_04` | Issue #44 guarded Hailo load evidence | 2026-08-04 | `evidence_summary.md` (no `README.md`) | not referenced from `docs/` |
| `p044_hailo_reid_load_matrix_e0c2a52d_2026_08_03` | Issue #44 Hailo ReID Load Matrix | 2026-08-03 | `README.md` | not referenced from `docs/` |
| `p044_hailo_reid_matrix_c3b34633_2026_08_02` | P044 Three-Repetition Hailo ReID Matrix | 2026-08-02 | `README.md` | not referenced from `docs/` |
| `p044_live_reid_fault_acceptance_7283a973_2026_08_04` | P044 Live ReID Fault Acceptance | 2026-08-04 | `README.md` | not referenced from `docs/` |
| `p044_observational_multirun_audit_ea1868fd_2026_08_04` | P044 observational multi-run audit | 2026-08-04 | `README.md` | not referenced from `docs/` |
| `p044_reconciled_reid_smoke_52c84c2a_2026_08_02` | P044 Reconciled Hailo ReID Smoke Evidence | 2026-08-02 | `README.md` | not referenced from `docs/` |
| `p044_sustained_reid_acceptance_a6259182_2026_08_04` | P044 Sustained Observational ReID Acceptance | 2026-08-04 | `README.md` | not referenced from `docs/` |
| `p044_within_model_ranking_e4c1d845_2026_08_04` | P044 within-model ranking analysis | 2026-08-04 | `README.md` | not referenced from `docs/` |

## Open review items

These are recorded for the owner; this pass does not resolve them.

- Five packages have no top-level `README.md` (`p006b`, `p007`,
  `p044_guarded_cpu_matrix`, `p044_guarded_hailo_load`); their entry point is a
  `closure_summary.md` / `evidence_summary.md` / analysis markdown instead.
- The ten `p044_*` packages belong to Issue #44, which is closed. They are
  retained as embedded-appearance-offload evidence but are not linked from any
  `docs/` index.
- `p015`, `p017`, and the three `p018_*` packages are not referenced from any
  tracked document under `docs/`.
- `docs/data/final_experiment_inventory.md` cites `reports/p026_event_recovery_*`
  and `reports/p031_parameter_sensitivity_*` as final evidence; those directories
  are present on the Pi but are **not** in the tracked set.
