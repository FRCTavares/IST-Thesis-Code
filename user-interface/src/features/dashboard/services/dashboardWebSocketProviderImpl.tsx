import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { DashboardTelemetry } from "@/types/dashboard";
import { createDashboardSocketClient } from "@/features/dashboard/services/dashboardSocket";

interface DashboardRealtimeState {
  telemetry: DashboardTelemetry | null;
  status: string;
}

const DashboardRealtimeContext = createContext<DashboardRealtimeState | null>(null);

export function DashboardWebSocketProvider({ children }: { children: ReactNode }) {
  const [telemetry, setTelemetry] = useState<DashboardTelemetry | null>(null);
  const [status, setStatus] = useState("Initializing dashboard data source...");

  useEffect(() => {
    const client = createDashboardSocketClient();
    client.start(setTelemetry, setStatus);

    return () => {
      client.stop();
    };
  }, []);

  const value = useMemo(() => ({ telemetry, status }), [telemetry, status]);

  return <DashboardRealtimeContext.Provider value={value}>{children}</DashboardRealtimeContext.Provider>;
}

export function useDashboardRealtime(): DashboardRealtimeState {
  const context = useContext(DashboardRealtimeContext);
  if (!context) {
    throw new Error("useDashboardRealtime must be used inside DashboardWebSocketProvider");
  }
  return context;
}
