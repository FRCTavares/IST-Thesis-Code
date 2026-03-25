import { useEffect, useState } from "react";
import { Activity, Cpu, RadioTower, Satellite, Timer } from "lucide-react";
import { DashboardWebSocketProvider, useDashboardRealtime } from "@/features/dashboard/providers/dashboardWebSocketProvider";
import { VideoOverlay } from "@/components/dashboard/VideoOverlay";
import { MetricsGrid } from "@/components/dashboard/MetricsGrid";
import { PerformanceChart } from "@/components/dashboard/PerformanceChart";
import { StatusPanel } from "@/components/dashboard/StatusPanel";
import { ControlPanel } from "@/components/dashboard/ControlPanel";
import { PanelShell } from "@/components/dashboard/PanelShell";
import { StatusBadge } from "@/components/dashboard/StatusBadge";
import { dashboardConfig } from "@/services/config";
import type { DashboardModel, MetricsSnapshot } from "@/types/dashboard";
import { useDashboardMetrics } from "@/features/dashboard/hooks/useDashboardMetrics";
import { requestModelSwitch, requestReplay } from "@/features/dashboard/services/dashboardApi";
import { exportMetricsCsv } from "@/features/dashboard/utils/csv";
import { fmt } from "@/features/dashboard/utils/metrics";

type DashboardTab = "overview" | "control" | "charts";

function DashboardPage() {
  const { telemetry, status } = useDashboardRealtime();
  const [activeModel, setActiveModel] = useState<DashboardModel>("yolov6n");
  const [controlStatus, setControlStatus] = useState("Replay starts auto logging. Export saves rolling telemetry.");
  const [samples, setSamples] = useState<MetricsSnapshot[]>([]);
  const [activeTab, setActiveTab] = useState<DashboardTab>("overview");

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
    setControlStatus(
      `Model switch failed (${dashboardConfig.apiBaseUrl}/api/model): ${response.error ?? "unknown error"}`,
    );
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

  const systemState = status.toLowerCase().includes("connected") || dashboardConfig.mode !== "backend" ? "Online" : "Degraded";

  return (
    <div className="mx-auto grid w-full max-w-[1500px] gap-3 p-3 lg:p-4">
      <section className="grid grid-cols-2 gap-2 lg:grid-cols-5">
        <div className="rounded-md border border-slate-700/80 bg-slate-800/75 px-3 py-2">
          <div className="mb-1 flex items-center gap-1.5 text-[10px] uppercase tracking-[0.16em] text-slate-500">
            <Satellite className="h-3.5 w-3.5" />
            System
          </div>
          <div className="text-sm font-semibold text-emerald-300">{systemState}</div>
        </div>
        <div className="rounded-md border border-slate-700/80 bg-slate-800/75 px-3 py-2">
          <div className="mb-1 flex items-center gap-1.5 text-[10px] uppercase tracking-[0.16em] text-slate-500">
            <RadioTower className="h-3.5 w-3.5" />
            Data Source
          </div>
          <div className="text-sm font-semibold text-sky-300">{dashboardConfig.mode.toUpperCase()}</div>
        </div>
        <div className="rounded-md border border-slate-700/80 bg-slate-800/75 px-3 py-2">
          <div className="mb-1 flex items-center gap-1.5 text-[10px] uppercase tracking-[0.16em] text-slate-500">
            <Activity className="h-3.5 w-3.5" />
            Tracker
          </div>
          <div className="text-sm font-semibold text-sky-300">{fmt(metricState.snapshot?.det_fps_inst, 1)} FPS</div>
        </div>
        <div className="rounded-md border border-slate-700/80 bg-slate-800/75 px-3 py-2">
          <div className="mb-1 flex items-center gap-1.5 text-[10px] uppercase tracking-[0.16em] text-slate-500">
            <Timer className="h-3.5 w-3.5" />
            Latency
          </div>
          <div className={(metricState.snapshot?.latency_ms_inst ?? 0) > 120 ? "text-sm font-semibold text-amber-300" : "text-sm font-semibold text-emerald-300"}>
            {fmt(metricState.snapshot?.latency_ms_inst, 1, " ms")}
          </div>
        </div>
        <div className="rounded-md border border-slate-700/80 bg-slate-800/75 px-3 py-2">
          <div className="mb-1 flex items-center gap-1.5 text-[10px] uppercase tracking-[0.16em] text-slate-500">
            <Cpu className="h-3.5 w-3.5" />
            Stream
          </div>
          <div className={telemetry ? "text-sm font-semibold text-emerald-300" : "text-sm font-semibold text-amber-300"}>
            {telemetry ? "Receiving" : "Waiting"}
          </div>
        </div>
      </section>

      <PanelShell
        className="bg-slate-800/70"
        contentClassName="flex flex-wrap items-center gap-2 p-2"
        action={<StatusBadge tone="info">ws {dashboardConfig.wsUrl}</StatusBadge>}
      >
        <button
          type="button"
          onClick={() => setActiveTab("overview")}
          className={`rounded-md border px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.14em] transition-all ${
            activeTab === "overview"
              ? "border-sky-400/60 bg-sky-500/20 text-sky-200 shadow-[0_0_14px_rgba(56,189,248,0.2)]"
              : "border-slate-700/80 bg-slate-900/65 text-slate-400 hover:border-slate-500 hover:text-slate-200"
          }`}
        >
          Overview
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("control")}
          className={`rounded-md border px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.14em] transition-all ${
            activeTab === "control"
              ? "border-sky-400/60 bg-sky-500/20 text-sky-200 shadow-[0_0_14px_rgba(56,189,248,0.2)]"
              : "border-slate-700/80 bg-slate-900/65 text-slate-400 hover:border-slate-500 hover:text-slate-200"
          }`}
        >
          Control
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("charts")}
          className={`rounded-md border px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.14em] transition-all ${
            activeTab === "charts"
              ? "border-sky-400/60 bg-sky-500/20 text-sky-200 shadow-[0_0_14px_rgba(56,189,248,0.2)]"
              : "border-slate-700/80 bg-slate-900/65 text-slate-400 hover:border-slate-500 hover:text-slate-200"
          }`}
        >
          Charts
        </button>
      </PanelShell>

      {activeTab === "overview" ? (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-[2.2fr_1fr]">
          <section>
            <PanelShell title="Live Camera Feed" contentClassName="p-2.5">
              <VideoOverlay telemetry={telemetry} videoUrl={dashboardConfig.videoUrl} />
            </PanelShell>
            <MetricsGrid snapshot={metricState.snapshot} />
          </section>

          <StatusPanel status={status} mode={dashboardConfig.mode} telemetry={telemetry} snapshot={metricState.snapshot} />
        </div>
      ) : null}

      {activeTab === "control" ? (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1.55fr_1fr]">
          <ControlPanel
            activeModel={activeModel}
            onModelSwitch={handleModelSwitch}
            onReplay={handleReplay}
            onExport={handleExport}
            controlStatus={controlStatus}
          />

          <StatusPanel status={status} mode={dashboardConfig.mode} telemetry={telemetry} snapshot={metricState.snapshot} />
        </div>
      ) : null}

      {activeTab === "charts" ? (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-[2fr_1fr]">
          <section className="space-y-3">
            <PerformanceChart samples={samples} />
            <MetricsGrid snapshot={metricState.snapshot} />
          </section>

          <StatusPanel status={status} mode={dashboardConfig.mode} telemetry={telemetry} snapshot={metricState.snapshot} />
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
