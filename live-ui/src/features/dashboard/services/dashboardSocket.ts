import { dashboardConfig } from "@/services/config";
import type { DashboardTelemetry } from "@/types/dashboard";
import { buildMockTelemetry } from "@/features/dashboard/mock/mockPayload";

export interface DashboardSocketClient {
  start(onData: (payload: DashboardTelemetry) => void, onStatus: (message: string) => void): void;
  stop(): void;
}

export function createDashboardSocketClient(): DashboardSocketClient {
  if (dashboardConfig.mode === "mock") {
    return createMockSocketClient();
  }

  if (dashboardConfig.mode === "offline") {
    return createOfflineSocketClient();
  }

  return createBackendSocketClient(dashboardConfig.wsUrl);
}

function createMockSocketClient(): DashboardSocketClient {
  let timer: number | null = null;
  let counter = 0;

  return {
    start(onData, onStatus) {
      onStatus("Mock mode active. Using generated telemetry.");
      timer = window.setInterval(() => {
        counter += 1;
        onData(buildMockTelemetry(counter));
      }, 200);
    },
    stop() {
      if (timer !== null) {
        window.clearInterval(timer);
        timer = null;
      }
    },
  };
}

function createOfflineSocketClient(): DashboardSocketClient {
  return {
    start(onData, onStatus) {
      onStatus("Offline mode active. No backend connection required.");
      onData(buildMockTelemetry(0));
    },
    stop() {},
  };
}

function createBackendSocketClient(wsUrl: string): DashboardSocketClient {
  let ws: WebSocket | null = null;
  let reconnectTimer: number | null = null;
  let shouldRun = false;

  const connect = (onData: (payload: DashboardTelemetry) => void, onStatus: (message: string) => void) => {
    ws = new WebSocket(wsUrl);
    onStatus(`Connecting to ${wsUrl}...`);

    ws.onopen = () => {
      onStatus(`Connected to ${wsUrl}`);
    };

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as DashboardTelemetry;
        onData(payload);
      } catch {
        onStatus("Invalid WebSocket payload");
      }
    };

    ws.onclose = () => {
      onStatus("WebSocket disconnected. Retrying...");
      if (shouldRun) {
        reconnectTimer = window.setTimeout(() => connect(onData, onStatus), 1200);
      }
    };

    ws.onerror = () => {
      ws?.close();
    };
  };

  return {
    start(onData, onStatus) {
      shouldRun = true;
      connect(onData, onStatus);
    },
    stop() {
      shouldRun = false;
      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      ws?.close();
      ws = null;
    },
  };
}
