import { useEffect, useState } from "react";
import { ChevronRight } from "lucide-react";
import { DashboardWebSocketProvider, useDashboardRealtime } from "@/features/dashboard/providers/dashboardWebSocketProvider";
import { VideoOverlay } from "@/components/dashboard/VideoOverlay";
import { MetricsGrid } from "@/components/dashboard/MetricsGrid";
import { TrackingMetricsGrid } from "@/components/dashboard/TrackingMetricsGrid";
import { SystemMetricsGrid } from "@/components/dashboard/SystemMetricsGrid";
import { PerformanceChart } from "@/components/dashboard/PerformanceChart";
import { StatusPanel } from "@/components/dashboard/StatusPanel";
import { ControlPanel } from "@/components/dashboard/ControlPanel";
import { PanelShell } from "@/components/dashboard/PanelShell";
import { StatusBadge } from "@/components/dashboard/StatusBadge";
import { dashboardConfig } from "@/services/config";
import type { DashboardModel, DashboardTracker, MetricsSnapshot } from "@/types/dashboard";
import { useDashboardMetrics } from "@/features/dashboard/hooks/useDashboardMetrics";
import { requestModelSwitch, requestTrackerSwitch } from "@/features/dashboard/services/dashboardApi";
import { exportMetricsCsv } from "@/features/dashboard/utils/csv";

type DashboardTab = "overview" | "control" | "charts";

function DashboardPage() {
  const { telemetry, status } = useDashboardRealtime();
  const [activeModel, setActiveModel] = useState<DashboardModel>("yolov6n");
  const [activeTracker, setActiveTracker] = useState<DashboardTracker>("sort");
  const [controlStatus, setControlStatus] = useState("Export saves rolling telemetry.");
  const [samples, setSamples] = useState<MetricsSnapshot[]>([]);
  const [activeTab, setActiveTab] = useState<DashboardTab>("overview");
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isModelSwitching, setIsModelSwitching] = useState(false);
  const [isTrackerSwitching, setIsTrackerSwitching] = useState(false);

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
    setIsModelSwitching(true);
    const response = await requestModelSwitch(model);
    if (response.ok) {
      setActiveModel(model);
      setControlStatus(`Model switch requested: ${model}`);
      setIsModelSwitching(false);
      return;
    }
    setControlStatus(
      `Model switch failed (${dashboardConfig.apiBaseUrl}/api/model): ${response.error ?? "unknown error"}`,
    );
    setIsModelSwitching(false);
  };

  const handleTrackerSwitch = async (tracker: DashboardTracker) => {
    setIsTrackerSwitching(true);
    const response = await requestTrackerSwitch(tracker);
    if (response.ok) {
      setActiveTracker(tracker);
      setControlStatus(`Tracker switch requested: ${tracker}`);
      setIsTrackerSwitching(false);
      return;
    }
    setControlStatus(
      `Tracker switch failed (${dashboardConfig.apiBaseUrl}/api/tracker): ${response.error ?? "unknown error"}`,
    );
    setIsTrackerSwitching(false);
  };

  const handleExport = () => {
    exportMetricsCsv(samples, activeModel);
    setControlStatus(`Exported ${samples.length} samples to CSV.`);
  };

  const wsLabel = dashboardConfig.wsUrl.replace(/^wss?:\/\//, "");
  const streamLabel = telemetry ? "LIVE" : "WAIT";

  return (
    <div className="mx-auto grid w-full max-w-[1500px] gap-3 p-3 lg:p-4">
      <PanelShell
        className="bg-slate-800/70"
        contentClassName="flex flex-wrap items-center justify-between gap-3 p-3"
      >
        <div className="flex flex-1 flex-wrap items-center gap-3 lg:gap-4">
          <div className="hidden pr-2 md:block">
            <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">Micro-UAV</div>
            <div className="text-lg font-semibold tracking-[0.08em] text-slate-100">Perception Console</div>
          </div>

          <div className="inline-flex items-center rounded-xl border border-slate-700/80 bg-slate-900/70 p-1 shadow-[inset_0_1px_0_rgba(148,163,184,0.08)]">
            <button
              type="button"
              onClick={() => setActiveTab("overview")}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.14em] transition-all ${activeTab === "overview"
                ? "bg-sky-500/20 text-sky-100 shadow-[0_0_0_1px_rgba(56,189,248,0.35),0_0_18px_rgba(56,189,248,0.18)]"
                : "text-slate-400 hover:bg-slate-800/80 hover:text-slate-200"
                }`}
            >
              Overview
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("control")}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.14em] transition-all ${activeTab === "control"
                ? "bg-sky-500/20 text-sky-100 shadow-[0_0_0_1px_rgba(56,189,248,0.35),0_0_18px_rgba(56,189,248,0.18)]"
                : "text-slate-400 hover:bg-slate-800/80 hover:text-slate-200"
                }`}
            >
              Control
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("charts")}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.14em] transition-all ${activeTab === "charts"
                ? "bg-sky-500/20 text-sky-100 shadow-[0_0_0_1px_rgba(56,189,248,0.35),0_0_18px_rgba(56,189,248,0.18)]"
                : "text-slate-400 hover:bg-slate-800/80 hover:text-slate-200"
                }`}
            >
              Charts
            </button>
          </div>

          <div className="flex flex-wrap items-center gap-1.5">
            <StatusBadge tone={telemetry ? "ok" : "warn"}>STREAM {streamLabel}</StatusBadge>
            <StatusBadge tone="info">MODEL {activeModel.toUpperCase()}</StatusBadge>
            <StatusBadge tone="info">TRACKER {activeTracker.toUpperCase()}</StatusBadge>
          </div>
        </div>

        <div className="hidden lg:flex items-center gap-2">
          <StatusBadge tone="info">WS {wsLabel}</StatusBadge>
          {isSidebarCollapsed && (
            <button
              type="button"
              onClick={() => setIsSidebarCollapsed(false)}
              className="h-9 w-9 rounded-md border border-slate-700/80 bg-slate-900/90 text-slate-300 shadow-[0_8px_24px_rgba(2,6,23,0.35)] transition-all hover:border-slate-500 hover:text-slate-100"
              aria-label="Expand side panel"
              title="Expand side panel"
            >
              <ChevronRight className="mx-auto h-4 w-4" />
            </button>
          )}
        </div>
      </PanelShell>

      {activeTab === "overview" ? (
        <div className={`grid grid-cols-1 gap-3 transition-[grid-template-columns] duration-300 ease-in-out ${isSidebarCollapsed ? "lg:grid-cols-1" : "lg:grid-cols-[2.2fr_1fr]"}`}>
          <section>
            <PanelShell title="Live Camera Feed" contentClassName="p-2.5">
              <VideoOverlay telemetry={telemetry} videoUrl={dashboardConfig.videoUrl} />
            </PanelShell>
            <MetricsGrid snapshot={metricState.snapshot} />
            <TrackingMetricsGrid telemetry={telemetry} />
            <SystemMetricsGrid snapshot={metricState.snapshot} />
          </section>

          {!isSidebarCollapsed && (
            <StatusPanel status={status} mode={dashboardConfig.mode} telemetry={telemetry} snapshot={metricState.snapshot} activeModel={activeModel} activeTracker={activeTracker} onModelSwitch={handleModelSwitch} onTrackerSwitch={handleTrackerSwitch} onExport={handleExport} onCloseSidebar={() => setIsSidebarCollapsed(true)} isModelSwitching={isModelSwitching} isTrackerSwitching={isTrackerSwitching} controlStatus={controlStatus} />
          )}
        </div>
      ) : null}

      {activeTab === "control" ? (
        <div className={`grid grid-cols-1 gap-3 transition-[grid-template-columns] duration-300 ease-in-out ${isSidebarCollapsed ? "lg:grid-cols-1" : "lg:grid-cols-[1.55fr_1fr]"}`}>
          <ControlPanel
            activeModel={activeModel}
            activeTracker={activeTracker}
            onModelSwitch={handleModelSwitch}
            onTrackerSwitch={handleTrackerSwitch}
            isModelSwitching={isModelSwitching}
            isTrackerSwitching={isTrackerSwitching}
            onExport={handleExport}
            controlStatus={controlStatus}
          />

          {!isSidebarCollapsed && (
            <StatusPanel status={status} mode={dashboardConfig.mode} telemetry={telemetry} snapshot={metricState.snapshot} activeModel={activeModel} activeTracker={activeTracker} onModelSwitch={handleModelSwitch} onTrackerSwitch={handleTrackerSwitch} onExport={handleExport} onCloseSidebar={() => setIsSidebarCollapsed(true)} isModelSwitching={isModelSwitching} isTrackerSwitching={isTrackerSwitching} controlStatus={controlStatus} />
          )}
        </div>
      ) : null}

      {activeTab === "charts" ? (
        <div className={`grid grid-cols-1 gap-3 transition-[grid-template-columns] duration-300 ease-in-out ${isSidebarCollapsed ? "lg:grid-cols-1" : "lg:grid-cols-[2fr_1fr]"}`}>
          <section className="space-y-3">
            <PerformanceChart samples={samples} />
            <MetricsGrid snapshot={metricState.snapshot} />
            <TrackingMetricsGrid telemetry={telemetry} />
            <SystemMetricsGrid snapshot={metricState.snapshot} />
          </section>

          {!isSidebarCollapsed && (
            <StatusPanel status={status} mode={dashboardConfig.mode} telemetry={telemetry} snapshot={metricState.snapshot} activeModel={activeModel} activeTracker={activeTracker} onModelSwitch={handleModelSwitch} onTrackerSwitch={handleTrackerSwitch} onExport={handleExport} onCloseSidebar={() => setIsSidebarCollapsed(true)} isModelSwitching={isModelSwitching} isTrackerSwitching={isTrackerSwitching} controlStatus={controlStatus} />
          )}
        </div>
      ) : null}
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
