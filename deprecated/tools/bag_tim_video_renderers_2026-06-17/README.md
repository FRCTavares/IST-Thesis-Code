# Deprecated TIM video renderers

Deprecated on 2026-06-17.

These scripts were replaced by:

    python3 tools/visualization/video.py tim-header-all

Reason:

- old renderers mixed source time, bag time, and manual time scaling;
- some workflows depended on --eval-time-scale;
- official TIM-MARS visual validation now uses ROS message header time;
- the canonical output location is reports/visual_validation_header_time_2026-06-17/.

Kept for reference only. Do not use for official header-time validation.
