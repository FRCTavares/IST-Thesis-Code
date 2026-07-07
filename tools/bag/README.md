# Bag Video Tools

This folder contains support tools for rendering or inspecting rosbag2 outputs.

These tools are for visual validation and debugging. They do not produce final
TIM-MARS correctness metrics.

## Tools

| Tool | Status | Purpose |
| --- | --- | --- |
| `render_bag_overlay_video.py` | Support workflow | Renders an annotated overlay video from a ROS 2 bag. |

## `render_bag_overlay_video.py`

This script can overlay detections, tracker boxes, selected-target output,
TIM-MARS output, and timing/status information on top of recorded image frames.

Use it when you need to visually inspect:

- whether detections align with the image,
- whether tracker IDs are stable,
- whether `/target` and `/target_memory_mars` point to the expected person,
- whether timing/status overlays look reasonable.

For final quantitative evaluation, use scripts in `tools/analysis/` instead.

## Relationship to the annotation UI

The annotation UI has its own rendering modules under
`tools/bag_annotation_ui/`. Keep this folder for standalone bag-video helpers
that do not depend on the interactive UI.
