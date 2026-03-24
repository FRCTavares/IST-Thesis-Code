import { useMemo, useRef } from "react";
import type { DashboardModel, DashboardTelemetry, MetricsSnapshot } from "@/types/dashboard";
import { fmt, mean, percentile, pushSeries } from "@/features/dashboard/utils/metrics";

interface SeriesStore {
  videoFps: number[];
  detFps: number[];
  latency: number[];
  detCount: number[];
  cpu: number[];
  mem: number[];
  temp: number[];
}

export function useDashboardMetrics(telemetry: DashboardTelemetry | null, model: DashboardModel) {
  const seriesRef = useRef<SeriesStore>({
    videoFps: [],
    detFps: [],
    latency: [],
    detCount: [],
    cpu: [],
    mem: [],
    temp: [],
  });

  return useMemo(() => {
    if (!telemetry) {
      return {
        snapshot: null,
        formatted: null,
      };
    }

    const series = seriesRef.current;
    const detCount = telemetry.detections.length;
    const videoFpsInst = telemetry.video_fps ?? telemetry.fps;

    pushSeries(series.videoFps, videoFpsInst);
    pushSeries(series.detFps, telemetry.det_fps);
    pushSeries(series.latency, telemetry.latency_ms);
    pushSeries(series.detCount, detCount);
    pushSeries(series.cpu, telemetry.system.cpu_percent);
    pushSeries(series.mem, telemetry.system.mem_percent);
    pushSeries(series.temp, telemetry.system.temp_c);

    const snapshot: MetricsSnapshot = {
      timestamp_iso: new Date().toISOString(),
      model,
      video_fps_inst: videoFpsInst,
      video_fps_10s: mean(series.videoFps.slice(-100)),
      det_fps_inst: telemetry.det_fps,
      det_fps_10s: mean(series.detFps.slice(-100)),
      latency_ms_inst: telemetry.latency_ms,
      latency_p50_ms: percentile(series.latency.slice(-120), 50),
      latency_p95_ms: percentile(series.latency.slice(-120), 95),
      replay_progress: telemetry.replay_progress,
      detections_now: detCount,
      detections_10s_avg: mean(series.detCount.slice(-120)),
      detections_10s_max: series.detCount.length ? Math.max(...series.detCount.slice(-120)) : null,
      cpu_percent_inst: telemetry.system.cpu_percent,
      cpu_percent_10s_avg: mean(series.cpu.slice(-100)),
      mem_percent_inst: telemetry.system.mem_percent,
      mem_percent_10s_avg: mean(series.mem.slice(-100)),
      mem_used_mb_inst: telemetry.system.mem_used_mb,
      temp_c_inst: telemetry.system.temp_c,
      temp_c_10s_avg: mean(series.temp.slice(-100)),
    };

    return {
      snapshot,
      formatted: {
        videoFps: fmt(snapshot.video_fps_10s ?? snapshot.video_fps_inst, 1),
        detFps: fmt(snapshot.det_fps_10s ?? snapshot.det_fps_inst, 1),
        latency: fmt(snapshot.latency_ms_inst, 1, " ms"),
      },
    };
  }, [model, telemetry]);
}
