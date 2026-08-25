# Data Metadata

This folder contains small, tracked metadata related to recorded experimental data.

- `annotations/`: trusted manual annotation CSVs used by TIM-MARS evaluation. Tracker-ID-specific (`correct_target_track_id`); see Issue #25.
- `physical_target_references/` (not yet populated): tracker-ID-independent physical-person bbox reference artifacts, one per source sequence, contract `tim_physical_target_bbox_v1`. Frozen in `docs/issues/p1-10-improve-bbox-evaluation.md`; schema/validator in `tools/analysis/physical_target_reference.py`. Reusable across tracker backends and regenerated runs without editing; never a replacement for the files in `annotations/`, which remain historical evidence in their own right. Created via the annotation UI's "Physical reference (Issue #25)" mode (`tools/bag_annotation_ui/tim_clean_ui.py`) or hand-written to the same schema; either way the backend validator in `tools/analysis/physical_target_reference.py` is authoritative.
- `catalogue/`: bag inventory, evaluation catalogue, migration manifests, and keep-policy notes.
- `final_experiment_inventory.md`: promoted final replay bags, reports, and annotation CSVs.
- `reproduce_final_results.md`: local verification steps for the final thesis result artifacts.

Actual ROS 2 bags remain under `bags/` and are generally not tracked by Git.
