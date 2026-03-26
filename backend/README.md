# Backend Bridge (Planned Extraction)

This folder is intentionally a placeholder for a future standalone backend service.

## Current implementation (ROS-native)

Today, dashboard bridge functionality runs in the ROS workspace, not in this folder:

- Telemetry and state are exposed through `dashboard_bridge_node`.
- MJPEG video is served by `web_video_server`.
- The dashboard frontend supports `mock`, `offline`, and `backend` data modes.

Current live API endpoints are provided by `dashboard_bridge_node` (port `8090`):

- `POST /api/model`
- `POST /api/replay` (placeholder behavior in live mode)

Operational notes:

- MJPEG stream compatibility requires `qos_profile=sensor_data` when consuming `/camera/dashboard`.
- Overlay geometry depends on bridge normalization matching inference detection basis (`640x640` in the current stack).

## Planned backend responsibilities

When extracted from ROS, this backend layer should:

- Translate ROS 2 telemetry/events into frontend-oriented APIs.
- Own HTTP API surface and versioning for dashboard control endpoints.
- Own WebSocket fan-out and protocol evolution between ROS and dashboard UI.
- Isolate frontend/backend contracts from ROS node internals.
