import { useEffect, useState } from "react";
import { DashboardWebSocketProvider, useDashboardRealtime } from "@/features/dashboard/providers/dashboardWebSocketProvider";
import { VideoOverlay } from "@/components/dashboard/VideoOverlay";
import { MetricsGrid } from "@/components/dashboard/MetricsGrid";
import { PerformanceChart } from "@/components/dashboard/PerformanceChart";
import { StatusPanel } from "@/components/dashboard/StatusPanel";
import { dashboardConfig } from "@/services/config";
import type { DashboardModel, MetricsSnapshot } from "@/types/dashboard";
import { useDashboardMetrics } from "@/features/dashboard/hooks/useDashboardMetrics";
import { requestModelSwitch, requestReplay } from "@/features/dashboard/services/dashboardApi";
import { exportMetricsCsv } from "@/features/dashboard/utils/csv";

function DashboardPage() {
  const { telemetry, status } = useDashboardRealtime();
  const [activeModel, setActiveModel] = useState<DashboardModel>("yolov6n");
  const [controlStatus, setControlStatus] = useState("Replay starts auto logging. Export saves rolling telemetry.");
  const [samples, setSamples] = useState<MetricsSnapshot[]>([]);

  const metricState = useDashboardMetrics(telemetry, activeModel);

  useEffect(() => {
    const snapshot = metricState.snapshot;
    if (!snapshot) {
      return;
    }
    setSamples((prev: MetricsSnapshot[]) => {
      const next = [...prev, snapshot];
      if (next.length > 2400) {
        next.shift();
      }
      return next;
    });
  }, [metricState.snapshot]);

  const handleModelSwitch = async (model: DashboardModel) => {
    const response = await requestModelSwitch(model);
    if (response.ok) {
      setActiveModel(model);
      setControlStatus(`Model switch requested: ${model}`);
      return;
    }
    setControlStatus(`Model switch failed: ${response.error ?? "unknown error"}`);
  };

  const handleReplay = async () => {
    const response = await requestReplay();
    if (response.ok) {
      setControlStatus("Replay request sent. Auto logging can be started by backend loop control.");
      return;
    }
    setControlStatus(`Replay failed: ${response.error ?? "unknown error"}`);
  };

  const handleExport = () => {
    exportMetricsCsv(samples, activeModel);
    setControlStatus(`Exported ${samples.length} samples to CSV.`);
  };

  return (
    <div className="mx-auto grid w-full max-w-[1360px] grid-cols-1 gap-4 p-4 lg:grid-cols-[2fr_1fr]">
      <section className="overflow-hidden rounded-2xl border border-border bg-card shadow-panel">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3">
          <div className="text-base font-semibold tracking-wide">Bird Detection Monitor</div>
          <div className="font-mono text-xs text-muted-foreground">ws={dashboardConfig.wsUrl}</div>
        </div>

        <div className="p-3">
          <VideoOverlay telemetry={telemetry} videoUrl={dashboardConfig.videoUrl} />
        </div>

        <MetricsGrid snapshot={metricState.snapshot} />

        <div className="p-3 pt-0">
          <PerformanceChart samples={samples} />
        </div>
      </section>

      <StatusPanel
        status={status}
        mode={dashboardConfig.mode}
        activeModel={activeModel}
        onModelSwitch={handleModelSwitch}
        onReplay={handleReplay}
        onExport={handleExport}
        controlStatus={controlStatus}
      />
    </div>
  );
}

export function App() {
  return (
    <DashboardWebSocketProvider>
      <DashboardPage />
    </DashboardWebSocketProvider>
  );
}
