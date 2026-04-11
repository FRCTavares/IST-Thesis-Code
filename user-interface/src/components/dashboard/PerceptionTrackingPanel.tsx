import type { DashboardTelemetry, MetricsSnapshot } from "@/types/dashboard";
import { fmt } from "@/features/dashboard/utils/metrics";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { PanelShell } from "@/components/dashboard/PanelShell";

interface PerceptionTrackingPanelProps {
  snapshot: MetricsSnapshot | null;
  telemetry: DashboardTelemetry | null;
}

export function PerceptionTrackingPanel({ snapshot, telemetry }: PerceptionTrackingPanelProps) {
  const activeTracks = telemetry?.tracks.length ?? 0;
  const detectionsNow = snapshot?.detections_now ?? telemetry?.detections.length ?? 0;
  const target = telemetry?.target;
  const detectorFps = snapshot?.det_fps_10s ?? snapshot?.det_fps_inst ?? telemetry?.det_fps ?? null;
  const videoFps = snapshot?.video_fps_10s ?? snapshot?.video_fps_inst ?? telemetry?.video_fps ?? null;
  const latencyMs = snapshot?.latency_ms_inst ?? telemetry?.latency_ms ?? null;

  return (
    <PanelShell title="Perception & Tracking" className="">
      <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
        <MetricCard
          label="Detector FPS"
          value={fmt(detectorFps, 1)}
          detail="10s smoothed"
          tone="info"
        />
        <MetricCard
          label="Video FPS"
          value={fmt(videoFps, 1)}
          detail="10s smoothed"
          tone="info"
        />
        <MetricCard
          label="Latency"
          value={fmt(latencyMs, 1, " ms")}
          detail={`p95 ${fmt(snapshot?.latency_p95_ms, 1, " ms")}`}
          tone={(latencyMs ?? 0) > 120 ? "warn" : "default"}
        />
        <MetricCard
          label="Active Tracks"
          value={String(activeTracks)}
          detail="currently tracked"
          tone="ok"
        />
        <MetricCard
          label="Detections"
          value={String(detectionsNow)}
          detail={`10s avg ${fmt(snapshot?.detections_10s_avg, 1)}`}
          tone="ok"
        />
        <MetricCard
          label="Target"
          value={target !== null && target !== undefined ? `#${target}` : "--"}
          detail="selected track"
          tone="default"
        />
      </div>
    </PanelShell>
  );
}
