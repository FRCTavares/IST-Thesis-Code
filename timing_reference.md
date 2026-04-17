# Timing Reference

This is the canonical timing reference for thesis runtime and analysis.

## Freeze Status (Thesis Baseline)

- Timing schema v3 is frozen for the thesis baseline.
- Canonical timing names must not change unless metric semantics change.
- Remaining aliases are deprecated compatibility/history paths only.

| Canonical Metric | Exact Meaning | Units | Measured or Derived | Producer | Main Consumer |
| --- | --- | --- | --- | --- | --- |
| camera_input_fps | Camera publish FPS from /camera/fps. | Hz | Derived (publish cadence) | ros2_ws/src/thesis_bringup/thesis_bringup/nodes/camera_capture_node.py | ros2_ws/src/thesis_bringup/thesis_bringup/nodes/dashboard_bridge_node.py |
| det_out_fps | Detection output rate from /detections callback cadence. | Hz | Derived (publish cadence) | ros2_ws/src/thesis_bringup/thesis_bringup/nodes/dashboard_bridge_node.py | user-interface/src/components/dashboard/MetricsGrid.tsx |
| pre_ms | Host preprocessing duration from t_pre_start_ns to t_pre_end_ns. | ms | Measured | ros2_ws/src/thesis_bringup/thesis_bringup/nodes/perception_pipeline_node.py | tools/analyse_bag_timing.py |
| container_queue_ms | Wait before inference starts after preprocessing/request receive. | ms | Measured | ros2_ws/src/thesis_bringup/thesis_bringup/nodes/perception_pipeline_node.py | tools/check_live_timing_invariants.py |
| infer_ms | Inference compute stage duration. | ms | Measured | ros2_ws/src/thesis_bringup/thesis_bringup/nodes/perception_pipeline_node.py | tools/collect_live_timing_stats.py |
| zmq_roundtrip_ms | Request/reply transport roundtrip (legacy) or engine roundtrip proxy (single-process). | ms | Measured | ros2_ws/src/thesis_inference_client/thesis_inference_client/inference_client_node.py | tools/analyse_bag_timing.py |
| e2e_det_ms | End-to-end latency from camera callback seen to detection publish completion. | ms | Measured | ros2_ws/src/thesis_bringup/thesis_bringup/nodes/perception_pipeline_node.py | user-interface/src/features/dashboard/hooks/useDashboardMetrics.ts |
| pub_dt_ms | Detection publish cadence interval between consecutive /timing publishes. | ms | Measured interval (cadence-derived for rate) | ros2_ws/src/thesis_bringup/thesis_bringup/nodes/perception_pipeline_node.py | tools/validate_canonical_metrics.py |
| track_ms | Tracker backend compute duration. | ms | Measured | ros2_ws/src/thesis_tracker/thesis_tracker/tracker_node.py | tools/analyse_bag_tracking.py |
| e2e_target_ms | End-to-end latency from camera callback seen to target publish completion. | ms | Measured | ros2_ws/src/thesis_target_selector/thesis_target_selector/thesis_target_selector.py | tools/check_live_timing_invariants.py |

Clock-domain note:

- src_stamp_ns is source/sensor-domain metadata and is not directly comparable to host monotonic timing without synchronization.
- pub_dt_ms, camera_input_fps, and det_out_fps are cadence metrics; stage durations remain in explicit *_ms fields.
