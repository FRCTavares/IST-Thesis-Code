# Bag Directory Policy

This directory stores large ROS bag data. Keep it organized by data role, not by experiment mood.

## Folder roles

| Folder | Role | Deletion policy |
|---|---|---|
| source/curated/ | protected rerunnable source bags used for thesis evaluation | do not delete |
| source/archive/ | original source bags kept for traceability/recovery | do not delete unless backed up |
| annotation_inputs/ | derived bags used directly by the annotation UI and fixed annotation workflows | keep while annotations depend on them |
| replay/ | generated replay/evaluation bags | disposable unless promoted to final evidence |
| reference/ | known-good reference bags, especially tim_good | keep |
| review/ | temporary quarantine/review material | disposable |
| tmp/ | temporary generated bags | disposable |
| ui_replays/ | UI-generated replay bags | disposable unless promoted |

## Core rule

Source/raw bags are precious. Replay/review/tmp bags are disposable unless explicitly promoted.

## Naming contract

Use double underscores between semantic fields.

### Source bags

Source bags preserve capture provenance, including timestamp and original role.

Pattern:

YYYY-MM-DD__HH-MM-SS__source__<campaign>__<seq_id>__<scenario>__<stream_kind>

Example:

2026-06-19__12-55-58__source__2026-06-19__official__seq03__four_person_crossing_ambiguity__image_raw

### Annotation input bags

Annotation input bags are derived bags prepared for manual annotation or fixed evaluation. Their names should be concise and deterministic.

Pattern:

YYYY-MM-DD__seqXX__<scenario>__annotation_input__det_<detector>__trk_<tracker>__tim_<mode>__target_<policy>

Current official annotation inputs:

2026-06-19__seq01__clean_four_person__annotation_input__det_yolov8s__trk_bytetrack__tim_off__target_largest
2026-06-19__seq02__target_reentry__annotation_input__det_yolov8s__trk_bytetrack__tim_off__target_largest
2026-06-19__seq03__crossing_ambiguity__annotation_input__det_yolov8s__trk_bytetrack__tim_off__target_largest
2026-06-19__seq04__occlusion_no_exit__annotation_input__det_yolov8s__trk_bytetrack__tim_off__target_largest

Annotation CSV bag_name values must match the corresponding bag folder name when the bag exists locally.

### Replay bags

Replay bags are generated outputs.

Pattern for future promoted replays:

YYYY-MM-DD__seqXX__<scenario>__replay_<kind>__det_<detector>__trk_<tracker>__tim_<mode>__target_<policy>

Existing submitted-paper replay bags are kept under their historical final folders:

bags/replay/paper_final_tim_results_2026_07_03/
bags/replay/paper_final_deepsort_may_2026_07_03/
bags/replay/paper_final_deepsort_may_memory_2026_07_03/
bags/replay/paper_final_deepsort_june_full_2026_07_04/
bags/replay/paper_final_deepsort_june_memory_2026_07_04/

The `paper_final_*` names are frozen for traceability and should not be used as
the naming pattern for new thesis reruns. Do not treat other replay folders as
final evidence unless they are documented in docs/data/final_experiment_inventory.md.

## Protected source set

The protected rerunnable source set lives in:

bags/source/curated/

These bags contain /camera/image_raw where applicable and are preferred for realistic full detector/tracker/TIM reruns.

Rules:

- Do not delete curated source bags.
- Do not overwrite curated source bags.
- Use curated /camera/image_raw bags for realistic full-pipeline reruns.
- Do not use dashboard-only bags as full-pipeline source inputs.
- Dashboard/video replay bags may be used for visual review, but not as golden full-pipeline inputs.
- Event-level grouping should come from annotations, not from physically splitting bags.

## Seq02 note

The Seq02 annotation input bag is dashboard/full-pipeline-derived and does not contain /camera/image_raw:

bags/annotation_inputs/2026-06-19__seq02__target_reentry__annotation_input__det_yolov8s__trk_bytetrack__tim_off__target_largest

It is useful for annotation and fixed evaluation, but it is not part of the curated full-pipeline image source set.
