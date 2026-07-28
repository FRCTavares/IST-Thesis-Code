import type { DashboardTelemetry } from "@/types/dashboard";

export function buildMockTelemetry(seed: number): DashboardTelemetry {
  const phase = seed / 10;
  const detectionCount = Math.floor((Math.sin(phase) + 1.2) * 2);
  const cameraInputFps = 25 + Math.sin(phase * 0.7);
  const detOutFps = 8 + Math.cos(phase * 0.8) * 2;
  const e2eDetMs = 80 + Math.sin(phase * 0.5) * 12;
  const pubDtMs = detOutFps > 0 ? 1000 / detOutFps : null;
  const lifecycleFrame = 200 + seed;

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
    target_memory: {
      state: "LOCKED",
      control_mode: "FULL",
      target_track_id: 1,
      quality: 0.91,
      reason: "trusted_locked_continuity",
      lat_ms: 2.4,
      hard_negative_memory_size: 1,
      hard_negative_current_frame_id: lifecycleFrame,
      hard_negative_max_age_frames: 0,
      hard_negative_decay_policy: "none_until_expiry",
      hard_negative_events: [],
      hard_negative_entries: [
        {
          lifecycle_state: "committed",
          source: "trusted_locked_distractor",
          source_track_ids: [4, 7],
          selected_track_ids: [1],
          observations: 3,
          first_frame_id: lifecycleFrame - 80,
          last_frame_id: lifecycleFrame - 12,
          age_frames: 12,
          expires_at_frame_id: null,
          expired: false,
          latest_confidence: 0.88,
          latest_crop_quality: {
            crop_width_px: 74,
            crop_height_px: 152,
            clipping_fraction: 0,
            aspect_ratio: 0.49,
            max_iou_with_other: 0.18,
          },
          positive_similarity: 0.73,
          geometry_strength: 0.82,
          latest_iou: 0.21,
          latest_distance: 0.67,
          latest_scale: 0.91,
          latest_geometry_score: 0.79,
          appearance_source_frame_id: lifecycleFrame - 13,
          max_age_frames: 0,
          decay_policy: "none_until_expiry",
        },
      ],
      hard_negative_pending_entries: [
        {
          lifecycle_state: "pending",
          source: "trusted_locked_distractor",
          source_track_ids: [9],
          selected_track_ids: [1],
          observations: 1,
          first_frame_id: lifecycleFrame,
          last_frame_id: lifecycleFrame,
          age_frames: 0,
          expires_at_frame_id: null,
          expired: false,
          latest_confidence: 0.81,
          latest_crop_quality: {
            crop_width_px: 66,
            crop_height_px: 146,
            clipping_fraction: 0,
            aspect_ratio: 0.45,
            max_iou_with_other: 0.22,
          },
          positive_similarity: 0.71,
          geometry_strength: 0.77,
          latest_geometry_score: 0.75,
          appearance_source_frame_id: lifecycleFrame,
          max_age_frames: 0,
          decay_policy: "none_until_expiry",
        },
      ],
    },
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
