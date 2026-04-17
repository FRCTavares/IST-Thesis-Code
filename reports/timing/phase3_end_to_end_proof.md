# Phase 3 End-to-End Canonical Timing Proof (Replay)

Source bag:

- bags/live_camera/2026-03-29__control_validation_clean

Runtime proof captures from the same replay session:

- Producer message: reports/timing/phase3_replay_timing_msg.txt
- Bridge payload: reports/timing/phase3_replay_bridge_payload.json
- UI export proof row: reports/timing/phase3_ui_export_proof.csv
- Analysis report: reports/timing/phase3_replay_analysis.md

## Canonical key continuity

| Stage | Evidence | Canonical Keys Present |
| --- | --- | --- |
| Producer (/timing message) | reports/timing/phase3_replay_timing_msg.txt | pre_ms, container_queue_ms, infer_ms, e2e_det_ms, pub_dt_ms |
| Bridge payload (WebSocket) | reports/timing/phase3_replay_bridge_payload.json | camera_input_fps, det_out_fps, e2e_det_ms, pub_dt_ms, metrics_schema_version |
| UI/CSV export path | reports/timing/phase3_ui_export_proof.csv | metrics_schema_version, camera_input_fps_inst, det_out_fps_inst, e2e_det_ms_inst, pub_dt_ms_inst |
| Analysis report | reports/timing/phase3_replay_analysis.md | pre_ms, container_queue_ms, infer_ms, e2e_det_ms, pub_dt_ms |

## Captured values (same replay run)

- Producer (/timing sample):
  - container_queue_ms: 1.5865750312805176
  - infer_ms: 7.5451340675354
  - e2e_det_ms: 23.390125274658203
  - pub_dt_ms: 183.39688110351562

- Bridge payload (live WebSocket snapshot):
  - camera_input_fps: 51.76422882080078
  - det_out_fps: 10.997469652006512
  - e2e_det_ms: 24.69580841064453
  - pub_dt_ms: 59.05742263793945
  - metrics_schema_version: 3

- UI/CSV export proof row:
  - camera_input_fps_inst: 51.76422882080078
  - det_out_fps_inst: 10.997469652006512
  - e2e_det_ms_inst: 24.69580841064453
  - pub_dt_ms_inst: 59.05742263793945
  - metrics_schema_version: 3

- Analysis report (bag-wide stats):
  - container_queue_ms p50: 0.983
  - infer_ms p50: 6.459
  - e2e_det_ms p95: 45.772
  - pub_dt_ms p95: 166.357

Conclusion:

- Canonical cadence term pub_dt_ms is present and consistent across producer, bridge, UI/CSV export schema, and analysis report.
- No stage in this proof path requires det_interval_ms as canonical.
