# Live Inspection Tools

This folder contains small command-line helpers for live ROS 2 operation.

These tools are for runtime inspection only. They should not be used as final
evaluation scripts.

## Tools

| Tool | Status | Purpose |
| --- | --- | --- |
| `print_track_ids.py` | Support workflow | Prints observed tracker IDs, scores, and bbox summaries from a live `/tracks` topic. |
| `run_issue55_m6_integration.sh` | Issue #55 M6 gate | Bag-replay live UI / dashboard-backend integration gate. Starts a fresh canonical TIM-MARS, a fresh dashboard bridge, an image relay, `web_video_server`, and the external `IST-Thesis-UI` launcher on loopback, drives target select/clear, and checks the HTTP/WebSocket/MJPEG contract. Never starts the controller, MAVROS, Pixhawk, camera, detector, or Hailo. |
| `m6_integration_probe.py` | Issue #55 M6 gate | HTTP / WebSocket / MJPEG / target-authority assertions used by the M6 gate. |
| `m6_image_relay.py` | Issue #55 M6 gate | Minimal best-effort `sensor_msgs/Image` relay (`/camera/image_raw` -> `/camera/dashboard`) for the M6 gate; `topic_tools` is not installed and `image_transport republish` is QoS-incompatible with the recorded camera bag. Not part of the perception pipeline. |

## Typical use

Use `print_track_ids.py` while the live stack is running to confirm which
tracker IDs are visible before selecting or debugging a target.

For final selected-target metrics, use `tools/analysis/`.

## Issue #55 M6 integration gate

`run_issue55_m6_integration.sh` is a dedicated, repeatable engineering
integration test for the external-frontend / dashboard-backend contract. It
produces no scientific result. Every long-lived child runs under
`tools/lib/run_in_owned_process_group.py`, and only processes the harness
started are torn down. Evidence is written under
`ros2_ws/log/issue55_m6/<timestamp>/`.

```
bash tools/live/run_issue55_m6_integration.sh
```

Override the bag with `M6_BAG=/path/to/bag` and the domain with
`ROS_DOMAIN_ID=<id>` if required.
