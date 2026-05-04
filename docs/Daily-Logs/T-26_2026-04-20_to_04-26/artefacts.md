# T-26 Artefacts (2026-04-20 to 2026-04-26)

## Planned Artefacts

- [x] Seqfix replicate timing JSON (`single_process_inline_owner_seqfix_r2`)
- [x] Queue-buffer ablation timing JSON (`q1` variant)
- [x] Queue-buffer + videoconvert-off timing JSON (`q1_vc0` variant)
- [x] Consolidated comparison table (legacy vs current vs candidates)
- [x] Keep/drop decision note for selected runtime baseline

## Produced This Cycle

- `artifacts/reports/timing/live_post_refactor/single_process_inline_owner_seqfix_r2.json`
- `artifacts/reports/timing/live_post_refactor/single_process_inline_owner_seqfix_q1_r1.json`
- `artifacts/reports/timing/live_post_refactor/single_process_inline_owner_seqfix_q1_vc0_r1.json`
- `artifacts/reports/timing/live_post_refactor/single_process_inline_owner_seqfix_q1_vc0_appsrccap_r1.json` (keep; promoted baseline)
- `artifacts/reports/timing/live_post_refactor/single_process_inline_owner_seqfix_q1_vc0_appsrccap_r2.json` (replicate; latency improved, detection-load shift due to out-of-frame interval)
- `artifacts/reports/timing/live_post_refactor/single_process_inline_owner_seqfix_q1_vc0_backendq_r1.json` (drop)
- `artifacts/reports/timing/live_post_refactor/single_process_inline_owner_seqfix_q1_vc0_ptsalign_r1.json` (drop)

## References

- `tools/start_live_stack.sh`
- `tools/collect_live_timing_stats.py`
- `tools/validate_canonical_metrics.py`
- `tools/check_live_timing_invariants.py`
- `artifacts/reports/timing/live_post_refactor/`
