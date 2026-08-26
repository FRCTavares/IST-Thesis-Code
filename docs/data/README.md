# Data Metadata

This folder contains small, tracked metadata related to recorded experimental data.

- `annotations/`: trusted manual annotation CSVs used by TIM-MARS evaluation. Tracker-ID-specific (`correct_target_track_id`); see Issue #25.
- `physical_target_references/`: tracker-ID-independent physical-person bbox reference artifacts, one per source sequence. New canonical artifacts use contract `tim_physical_target_bbox_v2`, frozen in `docs/issues/p1-10-physical-reference-v2-contract.md`, with the authoritative schema/validator in `tools/analysis/physical_target_reference_v2.py`; v1 remains preserved as the historical narrower contract. References are reusable across tracker backends and same-capture regenerated runs without editing, and never replace the files in `annotations/`, which remain historical tracker-ID evidence. For M4B, prefer the exact-frame CVAT bridge in `tools/analysis/cvat_physical_reference.py`; ordered PNG tasks export as **CVAT for images 1.1**, which may contain one `<image><box>` per interpolated frame, while native `<track>` CVAT 1.1 remains a supported alternate input. In both forms, `physical_ref` alone defines annotation-local identity, exact timestamps come from `frame_manifest.json` rather than FPS, and human review remains authoritative. The custom UI's "Physical reference v2 (Issue #25)" mode remains the schema/evaluator inspection and fallback workspace. In-progress human artifacts may remain local and untracked; stage a canonical reference only after the annotator intentionally completes and reviews it. Assisted frame-by-frame proposals, confidence labels, review regions, and suggested anchors are temporary UI/server cache state rather than physical-reference data and must never be staged as canonical evidence.
- `catalogue/`: bag inventory, evaluation catalogue, migration manifests, and keep-policy notes.
- `final_experiment_inventory.md`: promoted final replay bags, reports, and annotation CSVs.
- `reproduce_final_results.md`: local verification steps for the final thesis result artifacts.

Actual ROS 2 bags remain under `bags/` and are generally not tracked by Git.
