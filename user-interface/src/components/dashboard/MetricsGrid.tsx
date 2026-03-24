import type { ReactNode } from "react";
import type { MetricsSnapshot } from "@/types/dashboard";
import { fmt } from "@/features/dashboard/utils/metrics";

interface MetricsGridProps {
  snapshot: MetricsSnapshot | null;
}

function HeatBar({ value, threshold }: { value: number | null | undefined; threshold: number }) {
  const pct = value === null || value === undefined ? 0 : Math.max(0, Math.min(100, Number(value)));
  const hot = pct >= threshold;

  return (
    <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-200">
      <div
        className={`h-full transition-all ${hot ? "bg-gradient-to-r from-amber-500 to-rose-700" : "bg-gradient-to-r from-teal-400 to-teal-700"}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function MetricCard({ label, value, meta, bar }: { label: string; value: string; meta: string; bar?: ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-slate-50 p-3">
      <div className="mb-1 text-xs uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="text-2xl font-semibold leading-tight">{value}</div>
      <div className="mt-1 font-mono text-xs text-muted-foreground">{meta}</div>
      {bar}
    </div>
  );
}

export function MetricsGrid({ snapshot }: MetricsGridProps) {
  return (
    <div className="grid grid-cols-1 gap-3 p-3 md:grid-cols-2">
      <MetricCard
        label="Video FPS"
        value={fmt(snapshot?.video_fps_10s ?? snapshot?.video_fps_inst, 1)}
        meta={`inst ${fmt(snapshot?.video_fps_inst, 1)} | 10s ${fmt(snapshot?.video_fps_10s, 1)}`}
      />
      <MetricCard
        label="Detection FPS"
        value={fmt(snapshot?.det_fps_10s ?? snapshot?.det_fps_inst, 1)}
        meta={`inst ${fmt(snapshot?.det_fps_inst, 1)} | 10s ${fmt(snapshot?.det_fps_10s, 1)}`}
      />
      <MetricCard
        label="Latency"
        value={fmt(snapshot?.latency_ms_inst, 1, " ms")}
        meta={`p50 ${fmt(snapshot?.latency_p50_ms, 1)} | p95 ${fmt(snapshot?.latency_p95_ms, 1)}`}
      />
      <MetricCard
        label="Detections"
        value={String(snapshot?.detections_now ?? 0)}
        meta={`10s avg ${fmt(snapshot?.detections_10s_avg, 1)} | max ${fmt(snapshot?.detections_10s_max, 0)}`}
      />
      <MetricCard
        label="CPU Load"
        value={fmt(snapshot?.cpu_percent_inst, 1, " %")}
        meta={`10s avg ${fmt(snapshot?.cpu_percent_10s_avg, 1)} %`}
        bar={<HeatBar value={snapshot?.cpu_percent_inst} threshold={88} />}
      />
      <MetricCard
        label="Memory Use"
        value={
          snapshot?.mem_percent_inst !== null && snapshot?.mem_percent_inst !== undefined
            ? `${fmt(snapshot?.mem_percent_inst, 1, " %")} / ${fmt(snapshot?.mem_used_mb_inst, 0, " MB")}`
            : "--"
        }
        meta={`10s avg ${fmt(snapshot?.mem_percent_10s_avg, 1)} %`}
        bar={<HeatBar value={snapshot?.mem_percent_inst} threshold={92} />}
      />
      <MetricCard
        label="CPU Temperature"
        value={fmt(snapshot?.temp_c_inst, 1, " C")}
        meta={`10s avg ${fmt(snapshot?.temp_c_10s_avg, 1)} C`}
        bar={<HeatBar value={snapshot?.temp_c_inst ? (snapshot?.temp_c_inst / 85) * 100 : 0} threshold={92} />}
      />
    </div>
  );
}
