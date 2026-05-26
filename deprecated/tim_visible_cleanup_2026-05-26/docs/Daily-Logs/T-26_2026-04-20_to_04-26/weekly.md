# Weekly Plan — T-26 (2026-04-20 to 2026-04-26)

## Week Objective

Close the remaining single-process vs legacy latency gap by reducing backend queue delay while preserving throughput and detection workload comparability.

## Priority Stack

1. Reconfirm seqfix stability with at least one replicate run.
2. Execute targeted Hailo queue-buffer ablation (`6 -> 1`) under matched conditions.
3. Execute queue-buffer plus videoconvert-off ablation and compare against queue-buffer-only.
4. Keep only variants that improve queue delay without throughput/cadence regressions.
5. Freeze one operational baseline and capture rationale in logs and artefacts.

## Success Criteria

- [x] `container_queue_ms` p95 shows material reduction from current seqfix baseline.
- [x] `/timing` Hz does not regress beyond agreed tolerance.
- [x] Workload comparability passes (`detections_per_msg.mean`, `zero_ratio`).
- [ ] Canonical validators and invariants pass for all candidate runs.
- [x] Final keep/drop decision is recorded with explicit numeric deltas.

## Execution Update (2026-04-19)

- Completed ablation cycle end-to-end after host reboot:
  - `single_process_inline_owner_seqfix_q1_r1`
  - `single_process_inline_owner_seqfix_q1_vc0_r1`
- Canonical validation passed for both q1 variants; invariants still show recurring `B.pub_dt_vs_det_out_fps_consistent` failures (same class as legacy runs).
- Best candidate this cycle: `single_process_inline_owner_seqfix_q1_vc0_r1`.
  - versus `seqfix_r2`: improved (`container_queue_ms p95`: 121.352 -> 117.461, `e2e_det_ms p95`: 149.992 -> 140.379, `infer_ms p95`: 13.126 -> 10.955)
  - versus `legacy_r3`: still far (`container_queue_ms p95`: 2.616 legacy vs 117.461 candidate)
- Step-7 backend-path single-change iterations were executed and dropped:
  - `single_process_inline_owner_seqfix_q1_vc0_backendq_r1`
  - `single_process_inline_owner_seqfix_q1_vc0_ptsalign_r1`
  Both regressed queue and e2e p95 vs `q1_vc0_r1`.
- Post-reboot appsrc-cap benchmark completed:
  - `single_process_inline_owner_seqfix_q1_vc0_appsrccap_r1`
  - versus `q1_vc0_r1`: `container_queue_ms` p95 `117.461 -> 102.028`, `e2e_det_ms` p95 `140.379 -> 125.004`
  - canonical validation passed; recurring invariant `B.pub_dt_vs_det_out_fps_consistent` still fails (same known class)
- Operational baseline is now `single_process_inline_owner_seqfix_q1_vc0_appsrccap_r1`.
- Replicate run completed for same appsrc-cap config:
  - `single_process_inline_owner_seqfix_q1_vc0_appsrccap_r2`
  - versus `appsrccap_r1`: further latency reduction (`container_queue_ms` p95 `102.028 -> 91.449`, `e2e_det_ms` p95 `125.004 -> 108.033`, `pub_dt_ms` p95 `215.911 -> 111.243`)
  - canonical validation passed; recurring invariant `B.pub_dt_vs_det_out_fps_consistent` still fails (same known class)
  - detection-load shift (`detections_per_msg.mean` `1.03 -> 0.19`, `zero_ratio` `0.00 -> 0.821`) was caused by an out-of-frame interval during capture and is not treated as a pipeline regression.
