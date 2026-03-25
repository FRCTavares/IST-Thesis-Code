import { Activity, Brain, Gauge, Wifi } from "lucide-react";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { PanelShell } from "@/components/dashboard/PanelShell";
import { StatusBadge } from "@/components/dashboard/StatusBadge";
import { fmt } from "@/features/dashboard/utils/metrics";
import type { DashboardDataMode, DashboardTelemetry, MetricsSnapshot } from "@/types/dashboard";

interface StatusPanelProps {
  status: string;
  mode: DashboardDataMode;
  telemetry: DashboardTelemetry | null;
  snapshot: MetricsSnapshot | null;
}

export function StatusPanel({ status, mode, telemetry, snapshot }: StatusPanelProps) {
  const hasTelemetry = Boolean(telemetry);
  const targetVisible = telemetry?.target !== null && telemetry?.target !== undefined;
  const tone = status.toLowerCase().includes("connected") || mode !== "backend" ? "ok" : "warn";
  const targetTrack = telemetry?.tracks.find((track) => track.id === telemetry.target);
  const replayProgress = telemetry?.replay_progress;

  return (
    <aside className="grid gap-3">
      <PanelShell title="Link Status" contentClassName="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-sm text-slate-200">
            <Wifi className="h-4 w-4 text-sky-300" />
            {status}
          </div>
          <StatusBadge tone={tone}>{tone === "ok" ? "Healthy" : "Degraded"}</StatusBadge>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <MetricCard label="Mode" value={mode.toUpperCase()} tone="info" className="p-2" />
          <MetricCard
            label="Stream"
            value={hasTelemetry ? "LIVE" : "WAIT"}
            tone={hasTelemetry ? "ok" : "warn"}
            className="p-2"
          />
        </div>
      </PanelShell>

      <PanelShell
        title="Flight Telemetry"
        action={
          <div className="flex items-center gap-1 text-[10px] uppercase tracking-[0.14em] text-slate-500">
            <Gauge className="h-3.5 w-3.5" />
            Core
          </div>
        }
      >
        <div className="grid grid-cols-2 gap-2">
          <MetricCard
            label="Replay"
            value={replayProgress !== null && replayProgress !== undefined ? `${fmt(replayProgress * 100, 0, "%")}` : "--"}
            tone="info"
            className="p-2"
          />
          <MetricCard
            label="Tracks"
            value={String(telemetry?.tracks.length ?? 0)}
            tone={telemetry?.tracks.length ? "ok" : "warn"}
            className="p-2"
          />
          <MetricCard
            label="CPU"
            value={fmt(snapshot?.cpu_percent_inst, 1, "%")}
            tone={(snapshot?.cpu_percent_inst ?? 0) >= 88 ? "warn" : "default"}
            className="p-2"
          />
          <MetricCard
            label="Battery Proxy"
            value={fmt(snapshot?.mem_percent_inst, 1, "%")}
            detail="memory saturation"
            tone={(snapshot?.mem_percent_inst ?? 0) >= 92 ? "warn" : "default"}
            className="p-2"
          />
        </div>
      </PanelShell>

      <PanelShell
        title="Perception"
        action={
          <div className="flex items-center gap-1 text-[10px] uppercase tracking-[0.14em] text-slate-500">
            <Brain className="h-3.5 w-3.5" />
            Vision
          </div>
        }
      >
        <div className="grid grid-cols-2 gap-2">
          <MetricCard label="Detector FPS" value={fmt(snapshot?.det_fps_inst, 1)} tone="info" className="p-2" />
          <MetricCard
            label="Latency"
            value={fmt(snapshot?.latency_ms_inst, 1, " ms")}
            tone={(snapshot?.latency_ms_inst ?? 0) > 120 ? "warn" : "default"}
            className="p-2"
          />
          <MetricCard
            label="Visible"
            value={targetVisible ? "YES" : "NO"}
            tone={targetVisible ? "ok" : "error"}
            className="p-2"
          />
          <MetricCard
            label="Target ID"
            value={telemetry?.target !== null && telemetry?.target !== undefined ? String(telemetry.target) : "--"}
            detail={targetTrack ? "track matched" : "awaiting lock"}
            tone={targetTrack ? "ok" : "warn"}
            className="p-2"
          />
          <MetricCard
            label="Detections"
            value={String(snapshot?.detections_now ?? telemetry?.detections.length ?? 0)}
            detail={`10s avg ${fmt(snapshot?.detections_10s_avg, 1)}`}
            tone="ok"
            className="p-2 col-span-2"
          />
        </div>
      </PanelShell>

      <div className="rounded-md border border-slate-700/80 bg-slate-900/50 p-2.5">
        <div className="mb-1 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
          <Activity className="h-3.5 w-3.5" />
          Detailed
        </div>
        <div className="grid grid-cols-1 gap-1 font-mono text-[11px] text-slate-400">
          <div>video fps 10s {fmt(snapshot?.video_fps_10s, 1)}</div>
          <div>det fps 10s {fmt(snapshot?.det_fps_10s, 1)}</div>
          <div>lat p50 {fmt(snapshot?.latency_p50_ms, 1)} ms</div>
          <div>lat p95 {fmt(snapshot?.latency_p95_ms, 1)} ms</div>
          <div>mem used {fmt(snapshot?.mem_used_mb_inst, 0)} MB</div>
          <div>temp {fmt(snapshot?.temp_c_inst, 1)} C</div>
        </div>
      </div>
    </aside>
  );
}
