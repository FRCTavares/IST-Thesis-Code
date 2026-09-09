# Dashboard trust boundary

Last reviewed: 2026-09-09

Operational access contract for the live dashboard bridge
(`ros2_ws/src/thesis_bringup/thesis_bringup/dashboard/dashboard_bridge_node.py`),
its HTTP control API, its telemetry WebSocket, and the MJPEG video path. It is
not a public-internet service.

## Frontend ownership

The browser frontend is the independently owned repository
`FRCTavares/IST-Thesis-UI` (normally checked out at `~/Desktop/IST-Thesis-UI`).
Thesis-Code contains no frontend runtime. `tools/start_ui_stack.sh` is a thin
compatibility shim that delegates to `$THESIS_UI_ROOT/tools/start_dashboard.sh`
and forwards `DASHBOARD_CONTROL_TOKEN` to the frontend as
`VITE_DASHBOARD_CONTROL_TOKEN`.

## Topology and ports

Operator laptop browser → Pi over the local network (LAN, Tailnet at home, or
the field Wi-Fi). Nothing is exposed to the public internet, and no secret is
committed to Git.

| Port | Service | Direction | Bind |
| --- | --- | --- | --- |
| 8090 | dashboard HTTP control API | operator → Pi | `$DASHBOARD_BIND` (loopback by default) |
| 8765 | telemetry WebSocket | Pi → operator (read-only stream) | `$DASHBOARD_BIND` (loopback by default) |
| 8080 | `web_video_server` MJPEG (`/camera/dashboard`) | Pi → operator (read-only video) | `web_video_server` default; reachable at the Pi address |
| 5173 | `IST-Thesis-UI` dev/static server | operator laptop | owned by `IST-Thesis-UI` |

## Bind policy

- **Default:** `127.0.0.1`. The HTTP control API and the telemetry WebSocket
  are loopback-only. This is safe with no token.
- **Remote operator use:** the operator must deliberately bind a reachable Pi
  interface, either `./tools/start_live_stack.sh --dashboard-bind <addr>` or
  the `DASHBOARD_BIND` environment variable.
- **Mandatory coupling:** if `--dashboard-bind` resolves to a non-loopback
  address and `DASHBOARD_CONTROL_TOKEN` is empty, `tools/start_live_stack.sh`
  refuses to start the dashboard bridge. There is no silent unauthenticated
  non-loopback fallback. Only `127.0.0.1`, `localhost`, `::1`, and the
  `127.0.0.0/8` range are treated as loopback; anything else requires the
  token.

## Control-endpoint access control

The control POST endpoints — `POST /api/model`, `POST /api/tracker`,
`POST /api/target` — require `Authorization: Bearer <token>` whenever a
control token is configured. A missing or incorrect token returns HTTP `401`
(constant-time comparison). `GET /api/models` and the telemetry WebSocket are
read-only and remain open.

The token is a **local field-network access credential, not a high-security
secret**. Anyone with access to the operator's browser or session can
inherently read it. Its handling contract is:

- never committed to Git; never invented or defaulted;
- never logged;
- never written to experiment / run provenance (only a `configured` / `open`
  marker);
- not passed through the live ROS process command line — the live launcher
  delivers it to `dashboard_bridge_node` **only** through the inherited
  `DASHBOARD_CONTROL_TOKEN` environment variable (the
  `dashboard_control_api_token` ROS parameter exists for hermetic tests; an
  explicit non-empty parameter wins, otherwise the environment variable is
  used);
- the frontend injects it into the browser runtime configuration
  (`window.__IST_THESIS_DASHBOARD_CONFIG__.controlToken`, written to
  `dist/runtime-config.js`) for the active dashboard session only; the
  frontend never reads it as a Vite build-time value, so `vite build` cannot
  bake it into static assets;
- `IST-Thesis-UI/tools/start_dashboard.sh` treats that token-bearing
  `runtime-config.js` as ephemeral session state and restores / removes it on
  normal exit, SIGINT, or SIGTERM.

## CORS and WebSocket origin

- `Access-Control-Allow-Origin` is emitted **only** for an exact origin in
  `dashboard_cors_allowed_origins` (comma-separated). It is never a wildcard.
  An empty allowlist grants no cross-origin access.
- Default allowlist: `http://localhost:5173,http://127.0.0.1:5173` (loopback
  development only). For a remote UI the operator must add their frontend
  origin (`DASHBOARD_CORS_ALLOWED_ORIGINS`).
- The telemetry WebSocket applies the same allowlist. Browser clients from a
  non-allowlisted origin are rejected at the handshake. Local non-browser
  tooling that legitimately sends no `Origin` header (the Issue #55 M6 probe,
  `tools/live/validate_target_authority_ground_run.py`) is accepted.
- Preflight `OPTIONS` advertises `Authorization` among the allowed headers.

## Field network

- `ISR Aero.Next GCS` is the preferred field Wi-Fi; only the explicitly
  approved AERONEXT local-router profile is a permitted fallback.
- Tailscale is disabled/inactive in field mode.
- On the field Wi-Fi, use `--dashboard-bind <pi-field-ip>` with
  `DASHBOARD_CONTROL_TOKEN` set, and add the operator laptop's frontend origin
  to `DASHBOARD_CORS_ALLOWED_ORIGINS`.

## Target authority

- Target selection through `POST /api/target` is a command into TIM-MARS on
  `/target_memory_mars/select` / `/target_memory_mars/clear`. The dashboard is
  **not** the selected-person identity authority; TIM-MARS is. Raw `/target`,
  `/tracks`, detector candidates, and diagnostic candidates never obtain
  controller motion authority.
- Runtime model/tracker switching is disabled in the frozen live profile
  (`runtime_reconfiguration_enabled=false`). A denied `POST /api/model` or
  `POST /api/tracker` returns HTTP `409` as a true no-op: it does not advance
  the target-authority generation, publish a `/target` reset, clear the
  TIM-MARS selection, or change the detector/tracker.
- Every accepted select/clear transaction advances a monotonic
  `target_authority_generation` and is written to the run's
  `target_authority_events.jsonl`.

## See also

- [Flight-day operator sheet](../flight/README.md)
- [Control contracts](../control/README.md)
- Launcher: `tools/start_live_stack.sh`, `tools/lib/live_cli.sh`
- M6 integration gate: `tools/live/run_issue55_m6_integration.sh`
