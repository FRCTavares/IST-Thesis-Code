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

This renderer requires one bag containing the image, `/tracks`, raw `/target`,
and TIM-MARS `/target_memory_mars` streams. Both panels use the same image
header time origin and annotation intervals. The annotated track is drawn as a
white dashed reference box; solid boxes show each method's output.

```bash
python3 tools/bag/render_tim_comparison_video.py \
  --bag BAG \
  --annotation ANNOTATIONS.csv \
  --sequence-label "Seq03 crossing ambiguity" \
  --tracker-label "OC-SORT" \
  --output reports/videos/seq03_raw_vs_tim_mars.mp4
```

The default one-second output-age gate matches the quantitative evaluator.
Presentation output is H.264 at constant 15 FPS, with held source frames
rather than interpolated motion. Each panel scales the complete recorded
camera image to 960 pixels wide while preserving its native aspect ratio, then
places a 112-pixel information header above it. The header cannot cover camera
pixels, and the camera image is never cropped or stretched.

The renderer reads the track header's coordinate contract. Versioned
`tim_mars_source_pixels_resize_v1` boxes are already source-camera pixels and
are not transformed twice. Legacy replay boxes with bare `frame_<n>` headers
are mapped from their 640×640 inference plane to the camera by independent X/Y
scaling; this correctly maps legacy 640×640 boxes onto 640×480 dashboard
frames without assuming letterboxing.

## Relationship to the annotation UI

The annotation UI has its own rendering modules and MP4 export under
`tools/bag_annotation_ui/`. Keep this folder for standalone bag-video helpers
that do not depend on the interactive UI.
