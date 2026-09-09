# tools/bag

Last reviewed: 2026-09-09

## Purpose

Standalone renderers that turn a ROS 2 bag into an overlay or comparison video
for visual validation and debugging. They produce no quantitative metrics.

## Contents

| Path | Role | Why it exists |
| --- | --- | --- |
| `render_bag_overlay_video.py` | Overlay video | Draws detections, tracker boxes, raw `/target`, TIM `/target_memory_mars` and timing/status onto recorded frames. |
| `render_tim_comparison_video.py` | Comparison video | Paired raw-target vs TIM-MARS panels from one bag, sharing the image time origin and annotation intervals. |

## Rules

- Use these for visual inspection only; for quantitative evaluation use
  `tools/analysis/`.
- Use these when a plain overlay or paired video is sufficient. Manual
  annotation and interactive frame review are handled through CVAT and the
  maintained analysis/import tooling, not a repository-local annotation UI.
- The renderers honour the track header coordinate contract
  (`tim_mars_source_pixels_resize_v1` vs legacy `frame_<n>`); this is covered
  by `tools/tests/test_render_bag_overlay_coordinate_contract.py` and
  `tools/tests/test_render_tim_comparison_video.py`.

## See also

- `docs/design/tim_tooling_index.md` — visual-review path authority
