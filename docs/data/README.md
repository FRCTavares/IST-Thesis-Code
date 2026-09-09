# Data metadata

Last reviewed: 2026-09-09

## Purpose

Small, tracked research inputs and metadata used to reproduce, interpret, and
audit thesis experiments. Large recordings and generated datasets do not belong
here.

## Contents

| Path | Role |
| --- | --- |
| `annotations/` | Historical trusted tracker-ID annotation CSVs used by earlier TIM-MARS evaluation. |
| `physical_target_references/` | Tracker-independent physical-person bbox references; v2 is the current contract. |
| `ablations/` | Frozen component-ablation specifications. |
| `catalogue/` | Bag inventories, evidence maps, retention policy, and related metadata. |
| `external_benchmark/` | Contracts and manifests for external benchmark evaluation. |
| `splits/` | Versioned development and prospective held-out split definitions. |
| `parameter_sensitivity/` | Frozen TIM-MARS parameter-sensitivity experiment definitions. |
| `tracker_sensitivity/` | Frozen tracker-sensitivity experiment definitions. |
| `final_experiment_inventory.md` | Promoted replay/evidence inventory. |
| `reproduce_final_results.md` | Current reproduction entrypoints and historical-result boundaries. |

## Annotation workflow

Manual physical-reference annotation is performed in CVAT. The maintained
exact-frame bridge is `tools/analysis/cvat_physical_reference.py`.

Canonical physical references use the `tim_physical_target_bbox_v2` contract
implemented by `tools/analysis/physical_target_reference_v2.py`. Human review is
authoritative; CVAT numeric IDs and drawing order are not physical identity.

Historical tracker-ID annotations and historical provenance are retained as
evidence and must not be rewritten to look like they were produced by the
current workflow.

## Rules

- ROS 2 recordings live under `bags/`, not `docs/data/`.
- Large external/processed datasets remain local under the repository `data/`
  tree unless a tracked manifest explicitly requires otherwise.
- In-progress annotation exports may remain local and untracked.
- Frozen manifests, splits, hashes, and physical references are not rewritten
  merely because current tooling or runtime defaults later change.
