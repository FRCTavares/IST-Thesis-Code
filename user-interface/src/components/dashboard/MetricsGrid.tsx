import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { MetricsSnapshot } from "@/types/dashboard";
import { fmt } from "@/features/dashboard/utils/metrics";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { PanelShell } from "@/components/dashboard/PanelShell";

interface MetricsGridProps {
  snapshot: MetricsSnapshot | null;
}

export function MetricsGrid({ snapshot }: MetricsGridProps) {
  const [collapsed, setCollapsed] = useState(false);
  const hasSnapshot = Boolean(snapshot);

  return (
    <PanelShell
      title="Perception Metrics"
      className="mt-3"
      action={
        <button
          type="button"
          onClick={() => setCollapsed((prev) => !prev)}
          className="inline-flex items-center gap-1 rounded-md border border-slate-700/80 bg-slate-900/70 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-300 hover:border-slate-500 hover:text-slate-100"
        >
          {collapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          {collapsed ? "Open" : "Collapse"}
        </button>
      }
    >
      {!collapsed && (
        <>
          {!hasSnapshot && (
            <div className="mb-2 rounded-md border border-slate-700/70 bg-slate-900/45 px-2.5 py-2 text-[11px] text-slate-400">
              No live telemetry yet. Waiting for perception metrics stream.
            </div>
          )}
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-4">
            <MetricCard
              label="Video FPS"
              value={fmt(snapshot?.video_fps_10s ?? snapshot?.video_fps_inst, 1)}
              detail={`inst ${fmt(snapshot?.video_fps_inst, 1)} | 10s ${fmt(snapshot?.video_fps_10s, 1)}`}
              tone="info"
            />
            <MetricCard
              label="Detector FPS"
              value={fmt(snapshot?.det_fps_10s ?? snapshot?.det_fps_inst, 1)}
              detail={`inst ${fmt(snapshot?.det_fps_inst, 1)} | 10s ${fmt(snapshot?.det_fps_10s, 1)}`}
              tone="info"
            />
            <MetricCard
              label="Latency"
              value={fmt(snapshot?.latency_ms_inst, 1, " ms")}
              detail={`p50 ${fmt(snapshot?.latency_p50_ms, 1)} | p95 ${fmt(snapshot?.latency_p95_ms, 1)}`}
              tone={(snapshot?.latency_ms_inst ?? 0) > 120 ? "warn" : "default"}
            />
            <MetricCard
              label="Detections"
              value={String(snapshot?.detections_now ?? 0)}
              detail={`10s avg ${fmt(snapshot?.detections_10s_avg, 1)} | max ${fmt(snapshot?.detections_10s_max, 0)}`}
              tone="ok"
            />
          </div>
        </>
      )}
    </PanelShell>
  );
}
