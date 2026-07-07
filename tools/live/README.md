# Live Inspection Tools

This folder contains small command-line helpers for live ROS 2 operation.

These tools are for runtime inspection only. They should not be used as final
evaluation scripts.

## Tools

| Tool | Status | Purpose |
| --- | --- | --- |
| `print_track_ids.py` | Support workflow | Prints observed tracker IDs, scores, and bbox summaries from a live `/tracks` topic. |

## Typical use

Use `print_track_ids.py` while the live stack is running to confirm which
tracker IDs are visible before selecting or debugging a target.

For final selected-target metrics, use `tools/analysis/`.
