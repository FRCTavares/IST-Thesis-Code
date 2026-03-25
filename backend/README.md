# Backend Bridge (Planned)

This folder is reserved for the future dashboard backend bridge.

Planned responsibilities:
- Translate ROS 2 telemetry/events into frontend-consumable APIs.
- Expose HTTP APIs used by the dashboard (`/api/model`, `/api/replay`, and future endpoints).
- Own WebSocket fan-out and protocol versioning between ROS and the dashboard UI.

Current state:
- The ROS dashboard bridge node remains in the ROS workspace.
- The frontend in user-interface can run in `mock`, `offline`, or `backend` mode.

Live integration notes (2026-03-25):
- Active runtime bridge path is still ROS-native (`dashboard_bridge_node` + `web_video_server`), not a separate backend service yet.
- MJPEG stream compatibility requires `qos_profile=sensor_data` when consuming `/camera/dashboard`.
- Dashboard overlay geometry depends on bridge normalization dimensions matching inference detection coordinate basis (`640x640` in the current live stack).
