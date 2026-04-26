# Daily Log — 2026-03-17 (Day 17) — Timing Ablation and Startup Script Hardening

## Overview

**Focus:** Improve timing observability and stabilize operational startup modes for repeatable profiling.

---

## Goals for Today

### 1. Improve Timing Validation and Reporting
- [x] Add live invariant checker for /timing, /timing_tracker, /timing_target
- [x] Add live percentile collector for ablation runs
- [x] Run first ablation set and summarize bottlenecks

### 2. Harden Startup Script Modes
- [x] Add optional startup flags (tracker selection, dashboard/web-video toggles, rosbag toggle)
- [x] Ensure no-dashboard mode disables dashboard transmission path
- [x] Keep one-command startup as default workflow

### 3. Close Timing Gaps in Target Path
- [x] Fix context fallback so e2e_target_ms is populated when available
- [x] Confirm frame propagation and invariants with live runs

---

## Work Completed

### Timing Validation and Ablation
- Added `tools/check_live_timing_invariants.py` for ordering/sanity checks with pass/fail reporting.
- Added `tools/collect_live_timing_stats.py` for p50/p95/p99, Hz, and frame continuity extraction.
- Ran baseline and ablation runs (R1-R5) and produced quantitative bottleneck summary.
- Confirmed dominant latency contributors are preprocessing and host-container roundtrip.

### Startup Script Enhancements
- Extended `tools/start_live_stack.sh` with optional flags for tracker/dashboard/web-video/rosbag modes.
- Fixed no-dashboard mode so dashboard transmission path is disabled.
- Preserved one-command operation while adding explicit run-mode controls.

### Target Timing Path Improvement
- Added fallback frame context recovery in target selector from /timing cache.
- Restored reliable e2e_target_ms population when host context is available.
- Verified live timing invariants with no failures in the sampled runs.

---

## Deliverables Produced

- [x] Timing invariant checker script
- [x] Live timing stats collector script
- [x] Updated startup script with optional run modes
- [x] Bottleneck analysis report for March 17

---

## Notes and Issues

**Primary findings:**
- Preprocessing and ZMQ roundtrip dominate latency; inference is comparatively small.
- Tracker stage is non-negligible in live mode and requires finer split for optimization.
- Dashboard and rosbag increase p95 latency and reduce throughput.

**Outstanding technical follow-up:**
- Split `pre_ms` into sub-stages.
- Split tracker callback into compute/build/publish sub-stages.

---

## End of Day Review

**Completed:**
- [x] Timing instrumentation validation and first ablation matrix
- [x] Startup script hardening and mode controls
- [x] Bottleneck report and daily log update

**Time spent:** 8-10 hours

**Confidence level:** high

**Outcome:** Clear, data-backed latency priorities established for next optimization steps.

---

## Timing Ablation Summary Link

Detailed summary report:
- `reports/timing/2026-03-17__live-bottlenecks-summary.md`

Key outcome snapshot:
- Dominant costs are host preprocessing and host-container roundtrip.
- Hailo inference is not the primary bottleneck.
- Tracker-stage callback cost is non-negligible in live runs.
- Dashboard and rosbag add measurable p95 latency and throughput overhead.

Immediate priorities:
1. Split `pre_ms` into finer stages (`img_convert_ms`, `resize_ms`, `colour_convert_ms`, `payload_pack_ms`).
2. Split tracker callback timing into `track_compute_ms`, `track_msg_build_ms`, and `track_pub_ms`.
3. Keep lean mode free from dashboard/web video/rosbag when measuring baseline performance.
