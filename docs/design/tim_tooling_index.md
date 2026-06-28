# TIM tooling index

Date: 2026-06-06

## Purpose

Map the active TIM-MARS tools, runtime nodes, annotations, and result locations.

This file describes the current active TIM-MARS workflow. Older exploratory TIM notes are archived.

## Runtime nodes

Current selected-target memory implementation:

- `ros2_ws/src/thesis_bringup/thesis_bringup/target_memory.py`
- `ros2_ws/src/thesis_bringup/thesis_bringup/nodes/target_memory_mars_node.py`

Related older HSV memory node:


Tracker node:

- `ros2_ws/src/thesis_tracker/thesis_tracker/nodes/tracker_node.py`

## Tracker configs

Active tracker configs are under:

- `ros2_ws/src/thesis_bringup/config/`

Important current config:

- `ros2_ws/src/thesis_bringup/config/tracker_bytetrack.yaml`

The ByteTrack config must preserve low-score recovery support:

- `min_score: 0.2`
- `track_thresh: 0.5`
- `match_thresh: 0.8`
- `track_buffer: 30`
- `det_thresh: 0.2`
- `second_match_thresh: 0.5`
- `new_track_thresh: 0.6`
- `unconfirmed_match_thresh: 0.7`

## Replay and evaluation scripts

Use for clean replay generation:

- `tools/experiments/run_one_clean_tim_replay.sh`

Use for selected-target correctness evaluation:

- `tools/analysis/evaluate_tim_target_correctness.py`

Use for ReID and status diagnostics:

- `tools/analysis/extract_tim_mars_reid_similarity.py`
- `tools/analysis/extract_tim_all_scores.py`

## Visual audit tools

Use for status and overlay review:

- `tools/bag_annotation_ui/video.py`
  - canonical header-time TIM-MARS visual validation renderer
  - official command: `python3 tools/bag_annotation_ui/video.py tim-header-all`
  - replaces the deprecated TIM-specific bag renderers under `deprecated/tools/bag_tim_video_renderers_2026-06-17/`
- `tools/bag/render_bag_overlay_video.py`
- `tools/bag_annotation_ui/render_all_tracks_id_video.py`

For the current source-image status audit renderer, use:

- `--eval-time-scale 2.0`

## Active annotations

Trusted hard re-entry annotations:

- `docs/data/annotations/may_hard_reentry/bytetrack_hard_reentry.csv`
- `docs/data/annotations/may_hard_reentry/deepsort_hard_reentry.csv`
- `docs/data/annotations/may_hard_reentry/ocsort_hard_reentry.csv`

Archived annotations:

- `docs/archive/annotations/`

## Active result docs

Current selected-target tracking result source:

- `docs/results/selected_target_tracking/hard_reentry_multi_tracker_summary.md`

Current compute/throughput result source:

- `docs/results/selected_target_tracking/hard_reentry_compute_throughput_summary.md`

Generated final reports:

- `reports/final_selected_target_tracking/bytetrack_tim_mars/summary.md`
- `reports/final_selected_target_tracking/deepsort_mars/summary.md`
- `reports/final_selected_target_tracking/ocsort_tim_mars/summary.md`

Reports are generated artefacts and are not committed by default.

## Active replay bags

Current hard re-entry bags:

- ByteTrack + TIM-MARS: `bags/replay/eval_matrix/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_off__target_1__tracker_bytetrack__tim_mars__target_1__r4`
- DeepSORT-MARS + TIM-MARS: `bags/replay/eval_matrix/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_off__target_1__tracker_deepsort__tim_mars__target_1`
- OCSORT + TIM-MARS: `bags/replay/eval_matrix/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_off__target_1__tracker_ocsort__tim_mars__target_1`

Bags are generated artefacts and should not be committed.

## Generated folders

Do not commit generated files from:

- `reports/`
- `bags/`
- `ros2_ws/log/`
- generated videos

Only commit curated summaries and design notes under `docs/`.

## Rule for future TIM experiments

Every future TIM experiment should produce:

1. metrics;
2. visual evidence;
3. short interpretation;
4. clear comparison with raw tracker output;
5. explicit safety interpretation under the rule that wrong target is worse than LOST.
