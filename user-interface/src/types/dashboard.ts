export type DashboardDataMode = "mock" | "offline" | "backend";

export interface DashboardBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface DashboardDetection extends DashboardBox {
  label: string;
  score: number;
}

export interface DashboardTrack extends DashboardBox {
  id: number;
}

export interface DashboardSystemMetrics {
  cpu_percent: number | null;
  mem_percent: number | null;
  mem_used_mb: number | null;
  temp_c: number | null;
}

export interface DashboardTelemetry {
  tracks: DashboardTrack[];
  detections: DashboardDetection[];
  target: number | null;
  fps: number | null;
  video_fps: number | null;
  replay_progress: number | null;
  det_fps: number | null;
  latency_ms: number | null;
  system: DashboardSystemMetrics;
}

export type DashboardLogLevel = "debug" | "info" | "warn" | "error";
export type DashboardLogSource = "socket" | "control" | "recording" | "system";

export interface DashboardLogEntry {
  id: string;
  timestamp_iso: string;
  level: DashboardLogLevel;
  source: DashboardLogSource;
  message: string;
}

export type DashboardModel = "yolov6n" | "yolov8s" | "yolov8m";
export type DashboardTracker = "sort" | "ocsort" | "bytetrack";

export interface DashboardControlResponse {
  ok: boolean;
  error?: string;
  requested_model?: DashboardModel;
  requested_tracker?: DashboardTracker;
  requested_target?: number | null;
  action?: "replay" | "target";
}

export interface MetricsSnapshot {
  timestamp_iso: string;
  model: DashboardModel;
  video_fps_inst: number | null;
  video_fps_10s: number | null;
  det_fps_inst: number | null;
  det_fps_10s: number | null;
  latency_ms_inst: number | null;
  latency_p50_ms: number | null;
  latency_p95_ms: number | null;
  replay_progress: number | null;
  detections_now: number;
  detections_10s_avg: number | null;
  detections_10s_max: number | null;
  cpu_percent_inst: number | null;
  cpu_percent_10s_avg: number | null;
  mem_percent_inst: number | null;
  mem_percent_10s_avg: number | null;
  mem_used_mb_inst: number | null;
  temp_c_inst: number | null;
  temp_c_10s_avg: number | null;
}
