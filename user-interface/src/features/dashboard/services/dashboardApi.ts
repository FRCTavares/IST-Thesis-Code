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

  return postJson<DashboardControlResponse>(`${dashboardConfig.apiBaseUrl}/api/model`, { model });
}

export async function requestReplay(): Promise<DashboardControlResponse> {
  if (dashboardConfig.mode === "mock" || dashboardConfig.mode === "offline") {
    return { ok: true, action: "replay" };
  }

  return postJson<DashboardControlResponse>(`${dashboardConfig.apiBaseUrl}/api/replay`, {});
}

async function postJson<T>(url: string, payload: object): Promise<T> {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const json = (await response.json()) as T;
  return json;
}
