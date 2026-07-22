# Bag Video Tools

This folder contains support tools for rendering or inspecting rosbag2 outputs.

These tools are for visual validation and debugging. They do not produce final
TIM-MARS correctness metrics.

## Tools

| Tool | Status | Purpose |
| --- | --- | --- |
| `render_bag_overlay_video.py` | Support workflow | Renders an annotated overlay video from a ROS 2 bag. |
| `render_tim_comparison_video.py` | Support workflow | Renders a paired raw-target versus TIM-MARS video from two explicitly supplied bags. |

## `render_bag_overlay_video.py`

This script can overlay detections, tracker boxes, selected-target output,
TIM-MARS output, and timing/status information on top of recorded image frames.

Use it when you need to visually inspect:

- whether detections align with the image,
- whether tracker IDs are stable,
- whether `/target` and `/target_memory_mars` point to the expected person,
- whether timing/status overlays look reasonable.

For final quantitative evaluation, use scripts in `tools/analysis/` instead.

## `render_tim_comparison_video.py`

This renderer requires explicit raw bag, TIM-MARS bag, annotation, titles, and
output name. It deliberately has no date-specific or “official” preset because
those silently become invalid when evidence folders move.

```bash
python3 tools/bag/render_tim_comparison_video.py \
  --name OCSORT \
  --raw-bag BAG_RAW \
  --tim-bag BAG_TIM \
  --annotation ANNOTATIONS.csv \
  --raw-title "OCSORT raw target" \
  --tim-title "OCSORT TIM-MARS" \
  --output-name ocsort_comparison.mp4
```

## Relationship to the annotation UI

The annotation UI has its own rendering modules and MP4 export under
`tools/bag_annotation_ui/`. Keep this folder for standalone bag-video helpers
that do not depend on the interactive UI.
