import { dashboardConfig } from "@/services/config";
import type { DashboardControlResponse, DashboardModel, DashboardModelsResponse, DashboardTracker } from "@/types/dashboard";

const VALID_TRACKERS = new Set<DashboardTracker>(["sort", "ocsort", "bytetrack", "deepsort"]);

export async function requestModelSwitch(model: DashboardModel): Promise<DashboardControlResponse> {
  if (!model.trim()) {
    return { ok: false, error: "invalid model" };
  }

  if (dashboardConfig.mode === "mock" || dashboardConfig.mode === "offline") {
    return { ok: true, requested_model: model };
  }

  try {
    return await postJson<DashboardControlResponse>(`${dashboardConfig.apiBaseUrl}/api/model`, { model });
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : "model switch request failed" };
  }
}

export async function requestTrackerSwitch(tracker: DashboardTracker): Promise<DashboardControlResponse> {
  if (!VALID_TRACKERS.has(tracker)) {
    return { ok: false, error: "invalid tracker" };
  }

  if (dashboardConfig.mode === "mock" || dashboardConfig.mode === "offline") {
    return { ok: true, requested_tracker: tracker };
  }

  try {
    return await postJson<DashboardControlResponse>(`${dashboardConfig.apiBaseUrl}/api/tracker`, { tracker });
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : "tracker switch request failed" };
  }
}

export async function fetchSupportedModels(): Promise<DashboardModelsResponse> {
  if (dashboardConfig.mode === "mock" || dashboardConfig.mode === "offline") {
    return {
      ok: true,
      models: [
        { key: "yolov6n", hef_file: "yolov6n_hailo8.hef", hef_path: "", available: true },
        { key: "yolov8s", hef_file: "yolov8s.hef", hef_path: "", available: true },
        { key: "yolov8m", hef_file: "yolov8m.hef", hef_path: "", available: true },
      ],
    };
  }

  try {
    return await getJson<DashboardModelsResponse>(`${dashboardConfig.apiBaseUrl}/api/models`);
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : "model list request failed" };
  }
}

export async function requestTargetFocus(target: number | null): Promise<DashboardControlResponse> {
  if (dashboardConfig.mode === "mock" || dashboardConfig.mode === "offline") {
    return { ok: true, requested_target: target, action: "target" };
  }

  try {
    return await postJson<DashboardControlResponse>(`${dashboardConfig.apiBaseUrl}/api/target`, { target });
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : "target focus request failed" };
  }
}

async function postJson<T>(url: string, payload: object): Promise<T> {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  let json: unknown = null;
  try {
    json = await response.json();
  } catch {
    json = null;
  }

  if (!response.ok) {
    const serverError =
      typeof json === "object" && json !== null && "error" in json
        ? String((json as { error?: unknown }).error ?? "request failed")
        : `HTTP ${response.status}`;
    throw new Error(serverError);
  }

  if (json === null) {
    throw new Error("empty response from control API");
  }

  return json as T;
}

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);

  let json: unknown = null;
  try {
    json = await response.json();
  } catch {
    json = null;
  }

  if (!response.ok) {
    const serverError =
      typeof json === "object" && json !== null && "error" in json
        ? String((json as { error?: unknown }).error ?? "request failed")
        : `HTTP ${response.status}`;
    throw new Error(serverError);
  }

  if (json === null) {
    throw new Error("empty response from control API");
  }

  return json as T;
}
