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
  const fpsWindowSeconds = snapshot?.fps_window_seconds ?? 3;
  const fpsWindowLabel = `${fmt(fpsWindowSeconds, 1, "s")} roll`;
  const health = snapshot?.health_score ?? null;
  const healthTone = health === null ? "default" : health >= 80 ? "ok" : health >= 60 ? "info" : "warn";

  return (
    <PanelShell
      title="Perception Metrics"
      className="mt-3"
      action={
        <button
          type="button"
          onClick={() => setCollapsed((prev) => !prev)}
          className="inline-flex items-center gap-1 rounded-md border border-zinc-700/80 bg-zinc-900/70 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-zinc-300 hover:border-zinc-500 hover:text-zinc-100"
        >
          {collapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          {collapsed ? "Open" : "Collapse"}
        </button>
      }
    >
      {!collapsed && (
        <>
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-6">
            <MetricCard
              label="Pipeline Health"
              value={fmt(health, 0, " /100")}
              detail="combined latency + throughput + cadence"
              tone={healthTone}
            />
            <MetricCard
              label="Camera Input FPS"
              value={fmt(snapshot?.camera_input_fps_roll ?? snapshot?.camera_input_fps_inst, 1)}
              detail={`inst ${fmt(snapshot?.camera_input_fps_inst, 1)} | ${fpsWindowLabel} (camera_input_fps)`}
              tone="info"
            />
            <MetricCard
              label="Detection Output FPS"
              value={fmt(snapshot?.det_out_fps_roll ?? snapshot?.det_out_fps_inst, 1)}
              detail={`inst ${fmt(snapshot?.det_out_fps_inst, 1)} | ${fpsWindowLabel} (det_out_fps)`}
              tone="info"
            />
            <MetricCard
              label="Detection E2E p95"
              value={fmt(snapshot?.e2e_det_p95_ms, 1, " ms")}
              detail={`inst ${fmt(snapshot?.e2e_det_ms_inst, 1, " ms")} | warn>${fmt(snapshot?.e2e_det_warn_ms, 0, " ms")} (e2e_det_ms)`}
              tone={(snapshot?.e2e_det_p95_ms ?? 0) > (snapshot?.e2e_det_warn_ms ?? 120) ? "warn" : "default"}
            />
            <MetricCard
              label="Detection Cadence p95"
              value={fmt(snapshot?.pub_dt_p95_ms, 1, " ms")}
              detail={`inst ${fmt(snapshot?.pub_dt_ms_inst, 1, " ms")} | warn>${fmt(snapshot?.pub_dt_warn_ms, 0, " ms")} (pub_dt_ms)`}
              tone={(snapshot?.pub_dt_p95_ms ?? 0) > (snapshot?.pub_dt_warn_ms ?? 120) ? "warn" : "default"}
            />
            <MetricCard
              label="Detections"
              value={String(snapshot?.detections_now ?? 0)}
              detail={`rolling avg ${fmt(snapshot?.detections_10s_avg, 1)} | max ${fmt(snapshot?.detections_10s_max, 0)}`}
              tone="ok"
            />
          </div>
        </>
      )}
    </PanelShell>
  );
}
