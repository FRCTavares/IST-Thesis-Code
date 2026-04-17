# Timing Alias Sunset Plan

Scope: aliases only. Canonical names are defined in timing_reference.md and tools/timing_contract.py.

## Removable Now

| Alias | Where It Still Exists | Current Dependency | Exact Removal Condition |
| --- | --- | --- | --- |
| det_interval_warn_ms, det_interval_ms_inst, det_interval_p95_ms (UI snapshot aliases) | Removed in this phase from user-interface/src/types/dashboard.ts and user-interface/src/features/dashboard/hooks/useDashboardMetrics.ts | None | Already removed |
| video_fps_inst, video_fps_10s, det_fps_inst, det_fps_10s, latency_ms_inst, latency_p50_ms, latency_p95_ms (UI snapshot aliases) | Removed in this phase from user-interface/src/types/dashboard.ts and user-interface/src/features/dashboard/hooks/useDashboardMetrics.ts | None | Already removed |
| CSV alias columns (det_interval_*, video_fps_*, det_fps_*, latency_*) | Removed in this phase from user-interface/src/features/dashboard/utils/csv.ts | None | Already removed |
| Frontend fallback reads telemetry.det_fps / telemetry.video_fps / telemetry.latency_ms / telemetry.det_interval_ms | Removed in this phase from user-interface/src/features/dashboard/hooks/useDashboardMetrics.ts and dashboard components | None | Already removed |

## Removable After One Migration Cycle

| Alias | Where It Still Exists | Current Dependency | Exact Removal Condition |
| --- | --- | --- | --- |
| fps, video_fps, det_fps, latency_ms, det_interval_ms (bridge payload aliases) | ros2_ws/src/thesis_bringup/thesis_bringup/nodes/dashboard_bridge_node.py | Potential external dashboards/tools consuming old payload keys | Remove after one full thesis run cycle where logs show no external consumer requests for alias keys and all internal/partner dashboards use canonical keys only |
| metric_thresholds_ms.det_interval_ms (bridge alias threshold) | ros2_ws/src/thesis_bringup/thesis_bringup/nodes/dashboard_bridge_node.py | Same external payload compatibility risk | Remove with the same bridge alias-key removal cutover |
| lat_ms write in producer nodes | ros2_ws/src/thesis_bringup/thesis_bringup/nodes/perception_pipeline_node.py and ros2_ws/src/thesis_inference_client/thesis_inference_client/inference_client_node.py | Legacy readers of Timing.msg expecting lat_ms | Remove when timing consumers validate e2e_det_ms-only path across one migration cycle |

## Must Stay for Rosbag/History Compatibility (Until Next Message Schema Bump)

| Alias | Where It Still Exists | Current Dependency | Exact Removal Condition |
| --- | --- | --- | --- |
| pts_ns | ros2_ws/src/thesis_msgs/msg/Timing.msg | Historical bags and old tooling readers | Remove in next Timing.msg schema bump after archive converter script is available |
| t_pub_ns | ros2_ws/src/thesis_msgs/msg/Timing.msg | Historical transport-timestamp readers | Remove in next Timing.msg schema bump after converter and compatibility report |
| lat_ms | ros2_ws/src/thesis_msgs/msg/Timing.msg | Historical latency readers | Remove in next Timing.msg schema bump after converter |
| recv_ms | ros2_ws/src/thesis_msgs/msg/Timing.msg | Historical recv_ms readers | Remove in next Timing.msg schema bump after converter |
| json_ms | ros2_ws/src/thesis_msgs/msg/Timing.msg | Historical decode alias readers | Remove in next Timing.msg schema bump after converter |
| loop_ms | ros2_ws/src/thesis_msgs/msg/Timing.msg | Historical loop aggregate readers | Remove in next Timing.msg schema bump after converter |
| timing_contract read fallbacks for legacy aliases | tools/timing_contract.py | Historical bag/report parsing | Remove after backfilled reports confirm zero alias reads for one full migration cycle |
