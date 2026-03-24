import type { DashboardDataMode } from "@/types/dashboard";

const modeRaw = (import.meta.env.VITE_DASHBOARD_DATA_MODE ?? "backend") as string;

export const dashboardConfig = {
  mode: parseMode(modeRaw),
  apiBaseUrl: String(import.meta.env.VITE_DASHBOARD_API_BASE_URL ?? window.location.origin),
  wsUrl: String(
    import.meta.env.VITE_DASHBOARD_WS_URL ??
      `ws://${window.location.hostname || "127.0.0.1"}:8765`,
  ),
  videoUrl: `http://${window.location.hostname || "127.0.0.1"}:8080/stream?topic=/camera/dashboard&type=mjpeg`,
};

function parseMode(input: string): DashboardDataMode {
  const mode = input.toLowerCase().trim();
  if (mode === "mock" || mode === "offline" || mode === "backend") {
    return mode;
  }
  return "backend";
}
