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

export interface DashboardResolution {
  width: number;
  height: number;
}

export interface HardNegativeCropQuality {
  crop_width_px?: number;
  crop_height_px?: number;
  clipping_fraction?: number;
  aspect_ratio?: number;
  max_iou_with_other?: number;
}

export interface HardNegativeMemorySnapshot {
  lifecycle_state?: string;
  source?: string;
  source_track_ids?: number[];
  selected_track_ids?: number[];
  observations?: number;
  first_frame_id?: number | null;
  last_frame_id?: number | null;
  first_timestamp_ns?: number | null;
  last_timestamp_ns?: number | null;
  age_frames?: number | null;
  expires_at_frame_id?: number | null;
  expired?: boolean;
  latest_bbox?: number[] | null;
  latest_confidence?: number;
  latest_crop_quality?: HardNegativeCropQuality | null;
  positive_similarity?: number;
  geometry_strength?: number;
  latest_iou?: number;
  latest_distance?: number;
  latest_scale?: number;
  latest_geometry_score?: number;
  appearance_source_frame_id?: number | null;
  appearance_source_crop_quality?: HardNegativeCropQuality | null;
  max_age_frames?: number;
  decay_policy?: string;
}

export interface HardNegativeMemoryEvent {
  action?: string;
  source?: string;
  source_track_id?: number | null;
  selected_track_id?: number | null;
  source_track_ids?: number[];
  selected_track_ids?: number[];
  observations?: number;
  positive_similarity?: number;
  geometry_strength?: number;
  prototype_similarity?: number;
  memory_size?: number;
  snapshot?: HardNegativeMemorySnapshot;
}

export interface TargetMemoryStatus {
  state?: string;
  control_mode?: string;
  target_track_id?: number | null;
  quality?: number;
  reason?: string;
  lat_ms?: number;
  frames_since_seen?: number;
  num_tracks?: number;
  reacquired?: boolean;
  hard_negative_memory_size?: number;
  hard_negative_entries?: HardNegativeMemorySnapshot[];
  hard_negative_pending_entries?: HardNegativeMemorySnapshot[];
  hard_negative_events?: HardNegativeMemoryEvent[];
  hard_negative_current_frame_id?: number | null;
  hard_negative_max_age_frames?: number;
  hard_negative_decay_policy?: string;
  best?: {
    track_id?: number;
    total?: number;
    iou?: number;
    distance?: number;
    scale?: number;
    confidence?: number;
    ambiguous?: boolean;
  } | null;
  [key: string]: unknown;
}

export interface DashboardTelemetry {
  tracks: DashboardTrack[];
  detections: DashboardDetection[];
  target: number | null;
  target_requested?: number | null;
  target_active?: number | null;
  target_memory?: TargetMemoryStatus | null;
  camera_input_fps?: number | null;
  det_out_fps?: number | null;
  e2e_det_ms?: number | null;
  pub_dt_ms?: number | null;
  metrics_schema_version?: number;
  metric_windows?: {
    det_out_fps_seconds?: number;
  };
  metric_thresholds_ms?: {
    e2e_det_ms?: number;
    pub_dt_ms?: number;
  };
  replay_progress: number | null;
  inference_resolution?: DashboardResolution;
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

export type DashboardModel = string;
export type DashboardTracker = "sort" | "ocsort" | "bytetrack" | "deepsort";

export interface DashboardSupportedModel {
  key: DashboardModel;
  hef_file: string;
  hef_path: string;
  available: boolean;
}

export interface DashboardControlResponse {
  ok: boolean;
  error?: string;
  requested_model?: DashboardModel;
  requested_tracker?: DashboardTracker;
  requested_target?: number | null;
  action?: "replay" | "target";
}

export interface DashboardModelsResponse {
  ok: boolean;
  error?: string;
  models?: DashboardSupportedModel[];
}

export interface MetricsSnapshot {
  timestamp_iso: string;
  model: DashboardModel;
  metrics_schema_version: number;
  fps_window_seconds: number;
  e2e_det_warn_ms: number;
  pub_dt_warn_ms: number;
  pub_dt_ms_inst: number | null;
  pub_dt_p95_ms: number | null;
  health_score: number | null;
  camera_input_fps_inst: number | null;
  camera_input_fps_roll: number | null;
  det_out_fps_inst: number | null;
  det_out_fps_roll: number | null;
  e2e_det_ms_inst: number | null;
  e2e_det_p50_ms: number | null;
  e2e_det_p95_ms: number | null;
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
