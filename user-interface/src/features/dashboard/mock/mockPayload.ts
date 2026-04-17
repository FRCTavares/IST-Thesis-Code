import type { DashboardTelemetry } from "@/types/dashboard";

export function buildMockTelemetry(seed: number): DashboardTelemetry {
  const phase = seed / 10;
  const detectionCount = Math.floor((Math.sin(phase) + 1.2) * 2);
  const cameraInputFps = 25 + Math.sin(phase * 0.7);
  const detOutFps = 8 + Math.cos(phase * 0.8) * 2;
  const e2eDetMs = 80 + Math.sin(phase * 0.5) * 12;
  const pubDtMs = detOutFps > 0 ? 1000 / detOutFps : null;

  const detections = Array.from({ length: detectionCount }).map((_, index) => ({
    x: 0.2 + (index * 0.15 + (Math.sin(phase + index) + 1) * 0.2) % 0.6,
    y: 0.25 + ((Math.cos(phase * 0.6 + index) + 1) * 0.2),
    w: 0.14,
    h: 0.18,
    label: "person",
    score: 0.8 + ((Math.sin(phase + index) + 1) / 10),
  }));

  return {
    tracks: [],
    detections,
    target: null,
    camera_input_fps: cameraInputFps,
    det_out_fps: detOutFps,
    e2e_det_ms: e2eDetMs,
    pub_dt_ms: pubDtMs,
    metrics_schema_version: 3,
    metric_windows: {
      det_out_fps_seconds: 3,
    },
    metric_thresholds_ms: {
      e2e_det_ms: 120,
      pub_dt_ms: 120,
    },
    replay_progress: ((seed % 200) / 200),
    system: {
      cpu_percent: 45 + Math.sin(phase * 0.9) * 12,
      mem_percent: 61 + Math.cos(phase * 0.5) * 6,
      mem_used_mb: 1710 + Math.sin(phase * 0.4) * 200,
      temp_c: 63 + Math.sin(phase * 0.3) * 5,
    },
  };
}
