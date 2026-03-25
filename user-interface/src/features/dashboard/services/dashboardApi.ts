import { dashboardConfig } from "@/services/config";
import type { DashboardControlResponse, DashboardModel } from "@/types/dashboard";

const VALID_MODELS = new Set<DashboardModel>(["yolov6n", "yolov8s", "yolov8m"]);

export async function requestModelSwitch(model: DashboardModel): Promise<DashboardControlResponse> {
  if (!VALID_MODELS.has(model)) {
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

export async function requestReplay(): Promise<DashboardControlResponse> {
  if (dashboardConfig.mode === "mock" || dashboardConfig.mode === "offline") {
    return { ok: true, action: "replay" };
  }

  try {
    return await postJson<DashboardControlResponse>(`${dashboardConfig.apiBaseUrl}/api/replay`, {});
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : "replay request failed" };
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
