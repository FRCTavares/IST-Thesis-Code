# Micro-UAV Dashboard (Frontend)

This folder contains the dashboard frontend used to monitor perception and telemetry for the Micro-UAV thesis stack.

Technology:
- React + TypeScript + Vite
- Tailwind CSS
- shadcn/ui-compatible setup (`components.json`, Tailwind variables, utility helpers)
- `lucide-react` icons
- `recharts` charts

## Folder architecture

Inside `src/`:
- `app/` app entry and composition
- `components/` shared and dashboard-specific UI components
- `features/` dashboard feature logic, hooks, providers, and services
- `types/` shared TypeScript contracts
- `services/` app-level configuration and service wiring
- `utils/` utility helpers

## Run locally

From repository root:

```bash
cd user-interface
npm install
npm run dev
```

Build for production:

```bash
npm run build
npm run preview
```

## Environment variables

Use `.env` (see `.env.example`):

- `VITE_DASHBOARD_DATA_MODE`
  - `mock` (default)
  - `offline`
  - `backend`
- `VITE_DASHBOARD_API_BASE_URL`
  - HTTP base URL for backend API calls (`/api/model`, `/api/replay`)
- `VITE_DASHBOARD_WS_URL`
  - WebSocket endpoint for telemetry stream

Default behavior is `mock` mode for startup without backend dependencies.

## Data modes

### mock
- Generates synthetic telemetry payloads and detections.
- Supports UI development without ROS or backend running.

### offline
- Keeps the dashboard UI live with a static mock payload.
- Useful for demos where no network data should be consumed.

### backend
- Connects to backend contracts:
  - `POST /api/model`
  - `POST /api/replay`
  - WebSocket telemetry stream
- Backend service is expected to bridge ROS data for the dashboard.

## Backend integration readiness

The dashboard service adapters are prepared in:
- `src/features/dashboard/services/dashboardApi.ts`
- `src/features/dashboard/services/dashboardSocket.ts`
- `src/features/dashboard/services/dashboardWebSocketProvider.ts`

These files define the expected backend contract and include safe placeholder behavior so a running backend is not required during frontend development.

## Live ROS dashboard notes (2026-03-25)

- The dashboard video stream URL should include sensor-data QoS for compatibility with best-effort image publishers:
  - `http://<PI_IP>:8080/stream?topic=/camera/dashboard&type=mjpeg&qos_profile=sensor_data`
- Frontend default config now uses this URL pattern in `src/services/config.ts`.
- Bounding boxes are rendered from normalized center/size values coming from dashboard telemetry.
- Those normalized values depend on dashboard bridge `img_w/img_h` matching the detection bbox coordinate basis (currently inference size `640x640`).

## ROS integration path (planned)

Target flow:

`ROS topics -> backend bridge -> dashboard API/WebSocket -> React frontend`

This keeps ROS-specific concerns outside the frontend and provides a stable contract for real-time UI updates.
