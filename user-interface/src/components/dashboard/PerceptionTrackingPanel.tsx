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
  const detectorFps = snapshot?.det_out_fps_roll ?? snapshot?.det_out_fps_inst ?? telemetry?.det_out_fps ?? null;
  const cameraFps = snapshot?.camera_input_fps_roll ?? snapshot?.camera_input_fps_inst ?? telemetry?.camera_input_fps ?? null;
  const e2eDetMs = snapshot?.e2e_det_ms_inst ?? telemetry?.e2e_det_ms ?? null;
  const fpsWindowSeconds = snapshot?.fps_window_seconds ?? 3;
  const fpsWindowLabel = `${fmt(fpsWindowSeconds, 1, "s")} rolling`;

  return (
    <PanelShell title="Perception & Tracking" className="">
      <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3">
        <MetricCard
          label="Detection Output FPS"
          value={fmt(detectorFps, 1)}
          detail={`${fpsWindowLabel} (det_out_fps)`}
          tone="info"
        />
        <MetricCard
          label="Camera Input FPS"
          value={fmt(cameraFps, 1)}
          detail={`${fpsWindowLabel} (camera_input_fps)`}
          tone="info"
        />
        <MetricCard
          label="Detection E2E"
          value={fmt(e2eDetMs, 1, " ms")}
          detail={`p95 ${fmt(snapshot?.e2e_det_p95_ms, 1, " ms")} | key e2e_det_ms`}
          tone={(snapshot?.e2e_det_p95_ms ?? 0) > (snapshot?.e2e_det_warn_ms ?? 120) ? "warn" : "default"}
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
          detail={`rolling avg ${fmt(snapshot?.detections_10s_avg, 1)}`}
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
