import type { MetricsSnapshot } from "@/types/dashboard";
import { fmt } from "@/features/dashboard/utils/metrics";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { PanelShell } from "@/components/dashboard/PanelShell";

interface MetricsGridProps {
  snapshot: MetricsSnapshot | null;
}

function HeatBar({ value, threshold }: { value: number | null | undefined; threshold: number }) {
  const pct = value === null || value === undefined ? 0 : Math.max(0, Math.min(100, Number(value)));
  const warning = pct >= threshold;

  return (
    <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-700/70">
      <div
        className={`h-full transition-all ${warning ? "bg-gradient-to-r from-amber-400 to-red-500" : "bg-gradient-to-r from-sky-500 to-emerald-500"}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export function MetricsGrid({ snapshot }: MetricsGridProps) {
  return (
    <PanelShell title="Tracking Metrics" className="mt-3">
      <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
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
        <MetricCard
          label="CPU Load"
          value={fmt(snapshot?.cpu_percent_inst, 1, " %")}
          detail={`10s avg ${fmt(snapshot?.cpu_percent_10s_avg, 1)} %`}
          tone={(snapshot?.cpu_percent_inst ?? 0) >= 88 ? "warn" : "default"}
          footer={<HeatBar value={snapshot?.cpu_percent_inst} threshold={88} />}
        />
        <MetricCard
          label="Memory Use"
          value={
            snapshot?.mem_percent_inst !== null && snapshot?.mem_percent_inst !== undefined
              ? `${fmt(snapshot?.mem_percent_inst, 1, " %")} / ${fmt(snapshot?.mem_used_mb_inst, 0, " MB")}`
              : "--"
          }
          detail={`10s avg ${fmt(snapshot?.mem_percent_10s_avg, 1)} %`}
          tone={(snapshot?.mem_percent_inst ?? 0) >= 92 ? "warn" : "default"}
          footer={<HeatBar value={snapshot?.mem_percent_inst} threshold={92} />}
        />
        <MetricCard
          label="CPU Temp"
          value={fmt(snapshot?.temp_c_inst, 1, " C")}
          detail={`10s avg ${fmt(snapshot?.temp_c_10s_avg, 1)} C`}
          tone={(snapshot?.temp_c_inst ?? 0) >= 75 ? "warn" : "default"}
          footer={<HeatBar value={snapshot?.temp_c_inst ? (snapshot?.temp_c_inst / 85) * 100 : 0} threshold={92} />}
        />
      </div>
    </PanelShell>
  );
}
