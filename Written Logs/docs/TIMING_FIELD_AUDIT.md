# Timing Field Audit (Phase 2)

This table is the canonical timing-name audit across runtime production, dashboard forwarding, analysis exports, plots, and validators.

Legend:

- Measured: directly measured from timestamp differences.
- Derived: computed from publish cadence or aggregated values.
- Domain: where timestamps/cadence are measured (host monotonic, container monotonic, cross-process, or publish-cadence derived).

| Old Name | Canonical Name | Exact Meaning | Domain | Producer File | Consumer Files | Measured or Derived | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| pre_ms | pre_ms | Host-side preprocessing duration from pre-start to pre-end. | Host monotonic (same process) | ros2_ws/src/thesis_bringup/thesis_bringup/nodes/perception_pipeline_node.py; ros2_ws/src/thesis_inference_client/thesis_inference_client/inference_client_node.py | tools/collect_live_timing_stats.py; tools/analyse_bag_timing.py; tools/check_live_timing_invariants.py; tools/validate_canonical_metrics.py | Measured | Keep |
| q_wait_ms | container_queue_ms | Wait before inference starts after preprocessing/request receive. | Container monotonic (single/legacy dependent) | ros2_ws/src/thesis_bringup/thesis_bringup/nodes/perception_pipeline_node.py; ros2_ws/src/thesis_inference_client/thesis_inference_client/inference_client_node.py | tools/collect_live_timing_stats.py; tools/analyse_bag_timing.py; tools/check_live_timing_invariants.py; tools/validate_canonical_metrics.py | Measured | Keep canonical, deprecate q_wait_ms alias |
| recv_ms | zmq_roundtrip_ms | End-to-end request/reply transport wait (legacy) or engine roundtrip proxy (single-process). | Cross-process in legacy; host-local proxy in single-process | ros2_ws/src/thesis_inference_client/thesis_inference_client/inference_client_node.py; ros2_ws/src/thesis_bringup/thesis_bringup/nodes/perception_pipeline_node.py | tools/collect_live_timing_stats.py; tools/analyse_bag_timing.py; tools/check_live_timing_invariants.py; tools/validate_canonical_metrics.py | Measured | Keep canonical, deprecate recv_ms alias |
| json_ms | decode_ms | Host decode time from detector response payload into detections. | Host monotonic | ros2_ws/src/thesis_inference_client/thesis_inference_client/inference_client_node.py | tools/timing_contract.py (fallback reads for legacy only) | Measured | Deprecate alias-only metric in thesis outputs |
| infer_ms | infer_ms | Container inference compute stage duration. | Container monotonic | ros2_ws/src/thesis_bringup/thesis_bringup/nodes/perception_pipeline_node.py; ros2_ws/src/thesis_inference_client/thesis_inference_client/inference_client_node.py | tools/collect_live_timing_stats.py; tools/analyse_bag_timing.py; tools/check_live_timing_invariants.py; tools/validate_canonical_metrics.py | Measured | Keep |
| lat_ms; latency_ms | e2e_det_ms | Detection end-to-end latency from camera callback seen to detection publish completion. | Host monotonic | ros2_ws/src/thesis_bringup/thesis_bringup/nodes/perception_pipeline_node.py; ros2_ws/src/thesis_inference_client/thesis_inference_client/inference_client_node.py | ros2_ws/src/thesis_bringup/thesis_bringup/nodes/dashboard_bridge_node.py; user-interface/src/features/dashboard/hooks/useDashboardMetrics.ts; user-interface/src/components/dashboard/MetricsGrid.tsx; tools/collect_live_timing_stats.py; tools/analyse_bag_timing.py; tools/check_live_timing_invariants.py; tools/validate_canonical_metrics.py | Measured | Keep canonical, deprecate aliases |
| det_interval_ms | pub_dt_ms | Detection publish interval between consecutive /timing messages (cadence interval). | Publish-cadence derived from host monotonic timestamps | ros2_ws/src/thesis_bringup/thesis_bringup/nodes/perception_pipeline_node.py; ros2_ws/src/thesis_inference_client/thesis_inference_client/inference_client_node.py | ros2_ws/src/thesis_bringup/thesis_bringup/nodes/dashboard_bridge_node.py (compat alias only); tools/timing_contract.py (fallback mapping); tools/validate_canonical_metrics.py (legacy wording in error text) | Measured (interval); derived for rate | Keep canonical pub_dt_ms; det_interval_ms alias pending bridge sunset |
| det_fps | det_out_fps | Detection output message rate from /detections callback arrivals. | Publish-cadence derived (host monotonic) | ros2_ws/src/thesis_bringup/thesis_bringup/nodes/dashboard_bridge_node.py | user-interface/src/features/dashboard/hooks/useDashboardMetrics.ts; user-interface/src/components/dashboard/PerformanceChart.tsx; user-interface/src/components/dashboard/TrackingMetricsGrid.tsx; tools/check_live_timing_invariants.py (consistency check) | Derived | Keep canonical, deprecate det_fps alias |
| fps; video_fps | camera_input_fps | Camera publish FPS from /camera/fps topic. | Publish-cadence derived by camera node | ros2_ws/src/thesis_bringup/thesis_bringup/nodes/camera_capture_node.py (source topic); ros2_ws/src/thesis_bringup/thesis_bringup/nodes/dashboard_bridge_node.py (forwarding key) | user-interface/src/features/dashboard/hooks/useDashboardMetrics.ts; user-interface/src/components/dashboard/PerformanceChart.tsx; user-interface/src/components/dashboard/PerceptionTrackingPanel.tsx | Derived | Keep canonical, deprecate aliases |
| track_ms | track_ms | Tracker backend update compute time. | Host monotonic (tracker callback) | ros2_ws/src/thesis_tracker/thesis_tracker/tracker_node.py; ros2_ws/src/thesis_tracker/thesis_tracker/thesis_tracker.py | tools/collect_live_timing_stats.py; tools/analyse_bag_timing.py; tools/analyse_bag_tracking.py; tools/check_live_timing_invariants.py; tools/validate_canonical_metrics.py | Measured | Keep |
| e2e_target_ms | e2e_target_ms | Target selector end-to-end latency from camera callback seen to target publish completion. | Host monotonic | ros2_ws/src/thesis_target_selector/thesis_target_selector/thesis_target_selector.py | tools/collect_live_timing_stats.py; tools/analyse_bag_timing.py; tools/check_live_timing_invariants.py; tools/validate_canonical_metrics.py | Measured | Keep |
| pts_ns | src_stamp_ns | Original image timestamp copied from source message header. | Sensor/source clock domain | ros2_ws/src/thesis_bringup/thesis_bringup/nodes/perception_pipeline_node.py; ros2_ws/src/thesis_inference_client/thesis_inference_client/inference_client_node.py | ros2_ws/src/thesis_target_selector/thesis_target_selector/thesis_target_selector.py | Measured metadata | Keep src_stamp_ns, deprecate pts_ns alias |
| t_pub_ns | t_zmq_send_start_ns | Legacy alias for host send start timestamp in legacy path. | Host monotonic | ros2_ws/src/thesis_inference_client/thesis_inference_client/inference_client_node.py; ros2_ws/src/thesis_bringup/thesis_bringup/nodes/perception_pipeline_node.py (compat write) | tools/check_live_timing_invariants.py | Measured metadata | Deprecate alias |
| loop_ms | (delete; no canonical replacement) | Ambiguous aggregate loop timing that overlaps explicit stage metrics and causes double-count interpretation. | Mixed | ros2_ws/src/thesis_bringup/thesis_bringup/nodes/perception_pipeline_node.py | Legacy bag readers only | Derived aggregate | Delete candidate in next schema bump |

## Duplicate/Overlap Flags

1. lat_ms and latency_ms duplicate e2e_det_ms.
2. det_interval_ms duplicates pub_dt_ms.
3. det_fps duplicates det_out_fps.
4. fps and video_fps duplicate camera_input_fps.
5. recv_ms overlaps zmq_roundtrip_ms.
6. json_ms overlaps decode_ms.
7. q_wait_ms overlaps container_queue_ms.
8. pts_ns duplicates src_stamp_ns.
9. t_pub_ns overlaps t_zmq_send_start_ns semantics.
10. loop_ms overlaps explicit per-stage metrics and should be deleted.

## Removal Candidates (Next Schema Bump)

- Remove write-path aliases: lat_ms, recv_ms, json_ms, q_wait_ms, det_interval_ms, det_fps, fps, video_fps, latency_ms.
- Remove legacy message aliases: pts_ns, t_pub_ns, loop_ms.
- Keep legacy read fallback temporarily in tools/timing_contract.py until one thesis reporting cycle shows zero alias hits.
