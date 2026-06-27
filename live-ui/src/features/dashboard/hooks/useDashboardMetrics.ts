import { useMemo, useRef } from "react";
import type { DashboardModel, DashboardTelemetry, MetricsSnapshot } from "@/types/dashboard";
import { fmt, mean, percentile, pushSeries } from "@/features/dashboard/utils/metrics";

const METRICS_SCHEMA_FALLBACK = 3;
const DEFAULT_FPS_WINDOW_SECONDS = 3;
const ASSUMED_TELEMETRY_HZ = 30;
const LATENCY_PERCENTILE_WINDOW_SAMPLES = 120;

function clamp01(value: number): number {
  if (value <= 0) {
    return 0;
  }
  if (value >= 1) {
    return 1;
  }
  return value;
}

function computeHealthScore(args: {
  cameraFpsRoll: number | null;
  detOutFpsRoll: number | null;
  e2eP95Ms: number | null;
  pubDtP95Ms: number | null;
  e2eWarnMs: number;
}): number | null {
  const { cameraFpsRoll, detOutFpsRoll, e2eP95Ms, pubDtP95Ms, e2eWarnMs } = args;

  if (e2eP95Ms === null && detOutFpsRoll === null && pubDtP95Ms === null) {
    return null;
  }

  const e2eGoodMs = 70;
  const e2eBadMs = Math.max(e2eWarnMs * 1.8, e2eGoodMs + 1);
  const latencyScore =
    e2eP95Ms === null ? null : clamp01((e2eBadMs - e2eP95Ms) / (e2eBadMs - e2eGoodMs));

  let throughputScore: number | null = null;
  if (cameraFpsRoll !== null && cameraFpsRoll > 0 && detOutFpsRoll !== null) {
    const ratio = detOutFpsRoll / cameraFpsRoll;
    throughputScore = clamp01(ratio / 0.9);
  } else if (detOutFpsRoll !== null) {
    throughputScore = clamp01(detOutFpsRoll / 20);
  }

  let cadenceScore: number | null = null;
  if (pubDtP95Ms !== null) {
    const targetIntervalMs =
      detOutFpsRoll !== null && detOutFpsRoll > 0 ? 1000 / detOutFpsRoll : 100;
    const cadenceGoodMs = targetIntervalMs * 1.2;
    const cadenceBadMs = targetIntervalMs * 2.0;
    cadenceScore = clamp01((cadenceBadMs - pubDtP95Ms) / (cadenceBadMs - cadenceGoodMs));
  }

  const weighted: Array<[number, number | null]> = [
    [0.45, latencyScore],
    [0.35, throughputScore],
    [0.2, cadenceScore],
  ];

  let acc = 0;
  let weightSum = 0;
  for (const [weight, value] of weighted) {
    if (value !== null) {
      acc += weight * value;
      weightSum += weight;
    }
  }

  if (weightSum <= 0) {
    return null;
  }
  return Math.round((acc / weightSum) * 100);
}

interface SeriesStore {
  videoFps: number[];
  detFps: number[];
  latency: number[];
  detInterval: number[];
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
    detInterval: [],
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
    const metricsSchemaVersion = telemetry.metrics_schema_version ?? METRICS_SCHEMA_FALLBACK;
    const fpsWindowSeconds = telemetry.metric_windows?.det_out_fps_seconds ?? DEFAULT_FPS_WINDOW_SECONDS;
    const rollingFpsSamples = Math.max(5, Math.round(fpsWindowSeconds * ASSUMED_TELEMETRY_HZ));
    const e2eWarnMs = telemetry.metric_thresholds_ms?.e2e_det_ms ?? 120;
    const pubDtWarnMs = telemetry.metric_thresholds_ms?.pub_dt_ms ?? 120;

    const cameraInputFpsInst = telemetry.camera_input_fps ?? null;
    const detOutFpsInst = telemetry.det_out_fps ?? null;
    const e2eDetMsInst = telemetry.e2e_det_ms ?? null;
    const pubDtMsInst = telemetry.pub_dt_ms ?? null;

    pushSeries(series.videoFps, cameraInputFpsInst);
    pushSeries(series.detFps, detOutFpsInst);
    pushSeries(series.latency, e2eDetMsInst);
    pushSeries(series.detInterval, pubDtMsInst);
    pushSeries(series.detCount, detCount);
    pushSeries(series.cpu, telemetry.system.cpu_percent);
    pushSeries(series.mem, telemetry.system.mem_percent);
    pushSeries(series.temp, telemetry.system.temp_c);

    const cameraInputFpsRoll = mean(series.videoFps.slice(-rollingFpsSamples));
    const detOutFpsRoll = mean(series.detFps.slice(-rollingFpsSamples));
    const e2eDetP50Ms = percentile(series.latency.slice(-LATENCY_PERCENTILE_WINDOW_SAMPLES), 50);
    const e2eDetP95Ms = percentile(series.latency.slice(-LATENCY_PERCENTILE_WINDOW_SAMPLES), 95);
    const pubDtP95Ms = percentile(series.detInterval.slice(-LATENCY_PERCENTILE_WINDOW_SAMPLES), 95);
    const healthScore = computeHealthScore({
      cameraFpsRoll: cameraInputFpsRoll,
      detOutFpsRoll,
      e2eP95Ms: e2eDetP95Ms,
      pubDtP95Ms,
      e2eWarnMs,
    });

    const snapshot: MetricsSnapshot = {
      timestamp_iso: new Date().toISOString(),
      model,
      metrics_schema_version: metricsSchemaVersion,
      fps_window_seconds: fpsWindowSeconds,
      e2e_det_warn_ms: e2eWarnMs,
      pub_dt_warn_ms: pubDtWarnMs,
      pub_dt_ms_inst: pubDtMsInst,
      pub_dt_p95_ms: pubDtP95Ms,
      health_score: healthScore,
      camera_input_fps_inst: cameraInputFpsInst,
      camera_input_fps_roll: cameraInputFpsRoll,
      det_out_fps_inst: detOutFpsInst,
      det_out_fps_roll: detOutFpsRoll,
      e2e_det_ms_inst: e2eDetMsInst,
      e2e_det_p50_ms: e2eDetP50Ms,
      e2e_det_p95_ms: e2eDetP95Ms,
      replay_progress: telemetry.replay_progress,
      detections_now: detCount,
      detections_10s_avg: mean(series.detCount.slice(-LATENCY_PERCENTILE_WINDOW_SAMPLES)),
      detections_10s_max: series.detCount.length ? Math.max(...series.detCount.slice(-LATENCY_PERCENTILE_WINDOW_SAMPLES)) : null,
      cpu_percent_inst: telemetry.system.cpu_percent,
      cpu_percent_10s_avg: mean(series.cpu.slice(-rollingFpsSamples)),
      mem_percent_inst: telemetry.system.mem_percent,
      mem_percent_10s_avg: mean(series.mem.slice(-rollingFpsSamples)),
      mem_used_mb_inst: telemetry.system.mem_used_mb,
      temp_c_inst: telemetry.system.temp_c,
      temp_c_10s_avg: mean(series.temp.slice(-rollingFpsSamples)),
    };

    return {
      snapshot,
      formatted: {
        videoFps: fmt(snapshot.camera_input_fps_roll ?? snapshot.camera_input_fps_inst, 1),
        detFps: fmt(snapshot.det_out_fps_roll ?? snapshot.det_out_fps_inst, 1),
        latency: fmt(snapshot.e2e_det_ms_inst, 1, " ms"),
      },
    };
  }, [model, telemetry]);
}
