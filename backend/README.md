# Backend Bridge (Planned)

This folder is reserved for the future dashboard backend bridge.

Planned responsibilities:
- Translate ROS 2 telemetry/events into frontend-consumable APIs.
- Expose HTTP APIs used by the dashboard (`/api/model`, `/api/replay`, and future endpoints).
- Own WebSocket fan-out and protocol versioning between ROS and the dashboard UI.

Current state:
- The ROS dashboard bridge node remains in the ROS workspace.
- The frontend in user-interface can run in `mock`, `offline`, or `backend` mode.
