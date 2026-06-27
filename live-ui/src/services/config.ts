import type { DashboardDataMode } from "@/types/dashboard";

const modeRaw = (import.meta.env.VITE_DASHBOARD_DATA_MODE ?? "backend") as string;
const browserHost = window.location.hostname || "127.0.0.1";

function normalizeEndpointHost(rawUrl: string): string {
  try {
    const url = new URL(rawUrl, window.location.origin);
    const isLocalHost = url.hostname === "localhost" || url.hostname === "127.0.0.1";
    const browserIsRemote = browserHost !== "localhost" && browserHost !== "127.0.0.1";
    if (isLocalHost && browserIsRemote) {
      url.hostname = browserHost;
    }
    return url.toString();
  } catch {
    return rawUrl;
  }
}

export const dashboardConfig = {
  mode: parseMode(modeRaw),
  apiBaseUrl: normalizeEndpointHost(
    String(import.meta.env.VITE_DASHBOARD_API_BASE_URL ?? `http://${browserHost}:8090`),
  ),
  wsUrl: normalizeEndpointHost(
    String(import.meta.env.VITE_DASHBOARD_WS_URL ?? `ws://${browserHost}:8765`),
  ),
  videoUrl: normalizeEndpointHost(
    `http://${browserHost}:8080/stream?topic=/camera/dashboard&type=mjpeg&qos_profile=sensor_data&quality=45`,
  ),
};

function parseMode(input: string): DashboardDataMode {
  const mode = input.toLowerCase().trim();
  if (mode === "mock" || mode === "offline" || mode === "backend") {
    return mode;
  }
  return "backend";
}
