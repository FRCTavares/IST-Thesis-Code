# Selected-target tracking evidence

Last reviewed: 2026-09-16

## Purpose

Reviewed TIM-MARS, tracker, appearance, resilience, sensitivity, and
selected-target evaluation evidence.

This namespace contains evidence from multiple algorithm versions and claim
boundaries. Development evidence, historical frozen evidence, and the current
prospective held-out freeze must not be combined as though they were produced
by one configuration.

## Start here

| Path | Role |
| --- | --- |
| `p058_heldout_architecture_comparison_20260916.md` | Final Issue #27/#58 prospective H01-H03 architecture comparison and bounded thesis conclusion. |
| `p058_heldout_architecture_comparison_20260916.json` | Machine-readable final cell, aggregate, provenance, repair, and hash record. |
| `p058_heldout_bootstrap_forensics_20260916.md` | Retained pre-edit diagnosis of the physical-reference time-alignment defect. |
| `p058_deepsort_predetermined_instant_forensics_20260916.md` | Retained pre-edit diagnosis of the DeepSORT exact-instant defect. |
| `tim_mars_prospective_freeze_20260908.md` | Stage-7 prospective Issue #27 freeze and held-out claim boundary. |
| `p027_heldout_capture_preparation_20260915.md` | Post-freeze H01/H02/H03 source-capture, independent-backup, and human-annotation-preparation checkpoint; no held-out algorithm evaluation. |
| `tim_mars_presence_conditioned_development_20260908.md` | Current presence-conditioned development characterisation. |
| `hard_reentry_multi_tracker_summary.md` | Historical canonical compact selected-target comparison; uses its recorded evidence version, not the current runtime. |
| `p028_wrong_oracle_audit.md` | Corrected dual-oracle development audit. |
| `p028_component_ablation_development/README.md` | Promoted seven-row component-ablation development evidence. |
| `p031_parameter_sensitivity_summary.md` | Promoted TIM-MARS parameter-sensitivity development summary. |
| `p058_lightweight_vs_integrated_tracking_development/` | Development-only lightweight-versus-integrated appearance-tracker comparison. |
| `p058b_bytetrack_config_sensitivity.md` | Development-only ByteTrack sensitivity result. |
| `p064_gate2_resolution_evaluation.md` | Frozen Issue #64 controlled appearance-resolution result. |
| `p089_wide_crop_reacquisition.md` | Wide-crop reacquisition development evidence. |
| `p090_long_gap_global_reacquisition.md` | Long-gap global appearance reacquisition development evidence. |

## Evidence classes

- **Final prospective held-out evidence** — the Stage-7 freeze, pinned
  reproduction environment, immutable first run, retained protocol diagnoses,
  and final 12/12-cell repair run. Held-out outcomes are available only within
  the bounded claim recorded in `p058_heldout_architecture_comparison_20260916.md`.
- **Promoted development evidence** — reviewed ablations, sensitivity studies,
  resilience investigations, and architecture comparisons.
- **Historical frozen evidence** — older reproducible experiments whose
  configurations and model identities must remain exactly as recorded.
- **Implementation/protocol records** — prospective reporting definitions,
  deterministic replay re-baselines, and methodology records that define how
  evidence may be interpreted.

## Authority

The configuration/evidence-version boundary is defined by:

`../../algorithm/tim_mars_evidence_versions.md`

The active held-out execution procedure is:

`../../flight/P027_HELDOUT_EXECUTION_PLAN_v2.md`

## Rules

- Never infer that a file used the current canonical runtime merely because it lives in this directory.
- Respect each document's development, historical, frozen, or prospective claim boundary.
- Do not rewrite recorded detector, tracker, model, commit, hash, or retired-tool provenance.
- Generated reports become thesis evidence only after explicit review and promotion here.
