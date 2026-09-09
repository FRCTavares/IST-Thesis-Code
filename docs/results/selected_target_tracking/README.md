# Selected-target tracking evidence

Last reviewed: 2026-09-09

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
| `tim_mars_prospective_freeze_20260908.md` | Current Stage-7 prospective Issue #27 freeze and held-out claim boundary. |
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

- **Prospective held-out authority** — the Stage-7 freeze and its pinned
  reproduction environment; H01-H03 outcomes remain unavailable until the
  frozen release procedure permits evaluation.
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
