# Daily Log — 2026-02-26 — Bag Timing Reports, Long-Run Validation, Looping Service + Clean Shutdown Fixes (Week 2, Day 3)

## Goal
- Compute quantitative timing stats from yesterday's MCAP bags:
  - mean, p50, p95, p99, min, max for each field (matches script output)
  - achieved Hz per topic derived from bag counts and duration
  - Active window definition: first to last `/timing` message (bag timestamps)
- Produce 1–2 clean plots (or tables) suitable for thesis:
  - histogram or CDF for `lat_ms` and `loop_ms`
  - optional time-series of `pub_dt_ms` for stability visualisation
- Reduce post-EOS log spam in `inference_client_node` (throttle timeout warnings).
- Document the ROS 2 slice (topics, message contracts, run commands, known failure modes) in README.

**Done today:**
- Implemented offline bag timing analysis (`tools/analyse_bag_timing.py`) and generated thesis-ready markdown reports plus plots for both 02-25 bags.
- Added `pub_dt_ms` time-series plot option and bag-tagged figure naming in reports.
- Ran a long-run recording across multiple EOS restarts: `2026-02-26__slice__longrun` (464.7 s total).
- Implemented gap-aware "active-only" stats using `pub_dt_ms <= gap_ms`, plus exact active-only topic Hz and segment-summed active duration.
- Added a looping inference service (`run_detection_zmq_forever.sh`) and made `inference_client_node` restart-safe (reset `last_t_pub_ns` after consecutive timeouts) while throttling timeout warnings.
- Fixed `tracker_node` Ctrl-C crash by switching to an executor-based shutdown pattern — now clean teardown.

---

## Context

| Key | Value |
|-----|-------|
| Hardware | Raspberry Pi 5 + AI HAT+ (Hailo) + Pixhawk 4 (ArduPilot) + F9P GNSS *(camera not connected)* |
| Host OS | Ubuntu 24.04, ROS 2 Jazzy, Docker |
| Bags | `~/Desktop/Thesis/artifacts/bags/raw/2026-02-25__slice__secondary` and `...-12_01_25` |
| Storage format | MCAP |
| Topics | `/detections`, `/tracks`, `/target`, `/timing` |
| Active stream window | Until server EOS (~110 s per run) |
| Long-run bag | `~/Desktop/Thesis/artifacts/bags/raw/2026-02-26__slice__longrun` (464.707 s total) |
| Looping service | `~/Desktop/Thesis/infer_service/run_detection_zmq_forever.sh` (shared into container at `/root/thesis_service/`) |
| Gap filter | `gap_ms=100` — used to exclude restart gaps from active-only stats |
| ROS graph | `inference_client_node` → `tracker_node` → `target_selector_node` |

---

## Work Plan

### A) Bag selection + integrity check
- [x] Primary bag: `2026-02-25__slice__primary`
- [x] Secondary bag: `2026-02-25__slice__secondary`
- Notes: *(fill)*

### B) Offline metrics extraction (timing)
- [x] Created `~/Desktop/Thesis/tools/analyse_bag_timing.py`.
- [x] Reports written:
  - `~/Desktop/Thesis/artifacts/reports/timing/2026-02-26__timing_summary.md` (primary)
  - `~/Desktop/Thesis/artifacts/reports/timing/2026-02-26__timing_summary_secondary.md` (secondary)
- [x] Compute per-field stats: mean, p50, p95, p99, min, max.
- [x] Computed achieved Hz from bag: `count / duration`.
- [x] Results exported as markdown table (see Results below).
- Notes: *(fill)*

### C) Plots (minimum 2)
- [x] `artifacts/figures/timing/lat_ms_hist.png`, `artifacts/figures/timing/lat_ms_cdf.png`
- [x] `artifacts/figures/timing/loop_ms_hist.png`, `artifacts/figures/timing/loop_ms_cdf.png`
- [x] `artifacts/figures/timing/pub_dt_ms_timeseries.png`
- [x] Bag-tagged copies saved for both runs:
  - `lat_ms_*_2026-02-25__slice__primary.png`
  - `lat_ms_*_2026-02-25__slice__secondary.png`
  - (and equivalents for `loop_ms`, `pub_dt_ms`)
- Notes: *(fill)*

### D) Robustness polish — throttle post-EOS timeout logs
- [x] Throttled ZMQ recv timeout warnings to once every `timeout_log_every` consecutive timeouts (default 10); counter resets on successful recv.
- [x] Rebuilt: `colcon build --packages-select thesis_inference_client` (and full slice build).
- [x] Confirmed: during EOS period warnings are reduced; during active window normal info logs remain.
- Notes: *(fill)*

### E) Documentation — README
- [ ] README paste pending (snippet prepared).
  - [ ] Include `run_detection_zmq_forever.sh` command.
  - [ ] Include bagging protocol + SIGINT metadata note.
  - [ ] Mention active-only analysis approach with `gap_ms`.
- Notes: *(fill)*

### F) Long-run validation (looping service + gap-filtered metrics)
- [x] Created `run_detection_zmq_forever.sh` to automatically restart inference after EOS.
- [x] Recorded long-run MCAP bag with detached recorder; stopped cleanly with SIGINT (metadata written).
- [x] Updated analysis script to produce gap-filtered active-only stats and exact active-only Hz per topic.
- [x] Fixed `tracker_node` Ctrl-C crash — switched to executor-based shutdown pattern.
- [x] Made `inference_client_node` restart-safe: `last_t_pub_ns` reset after consecutive timeouts.
- Notes: *(fill)*

#### Record recipe (use every time)
```bash
# Always use MCAP storage and stop with SIGINT to ensure metadata is written
ros2 bag record --storage mcap --topics /detections /tracks /target /timing &
# ... wait ...
kill -SIGINT $!
ros2 bag info <bag_dir>   # verify metadata exists before moving on
```

---

## Results

### Bag-derived rates (primary bag)
| Topic | Count | Duration (s) | Rate (Hz) |
|-------|-------|-------------|-----------|
| `/detections` | 3 295 | 109.833 | 30.000 |
| `/timing` | 3 296 | 109.833 | 30.009 |
| `/tracks` | 3 282 | 109.833 | 29.882 |
| `/target` | 3 290 | 109.833 | 29.955 |

### Timing stats (primary bag — n=3 296 active frames)
| Field | mean | p50 | p95 | p99 | min | max |
|-------|------|-----|-----|-----|-----|-----|
| `lat_ms` | 1.552 | 1.160 | 3.835 | 5.548 | 0.271 | 12.774 |
| `recv_ms` | 28.052 | 27.994 | 32.537 | 35.270 | 0.014 | 248.999 |
| `json_ms` | 0.110 | 0.084 | 0.120 | 0.910 | 0.059 | 3.261 |
| `track_ms` | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| `loop_ms` | 28.644 | 28.590 | 33.121 | 35.740 | 0.346 | 249.583 |
| `pub_dt_ms` | 33.327 | 33.331 | 36.734 | 37.905 | 0.407 | 252.836 |

p95 `loop_ms` is ~33 ms and p99 ~36 ms, consistent with sustained 30 Hz.

Secondary bag matches primary — see `artifacts/reports/timing/2026-02-26__timing_summary_secondary.md` for full table.

### Long-run bag results (`2026-02-26__slice__longrun`)

Total window: 464.707 s, n(`/timing`) = 13 625.
`pub_dt_ms` max includes restart gaps (2 613.964 ms) — expected with looping service.

**Active-only (gap-filtered, `pub_dt_ms` ≤ 100 ms):**

| | Value |
|-|-------|
| Active duration | 453.065 s |
| Gap events (`pub_dt_ms` > 100 ms) | *(fill — gap count from script)* |
| Total removed gap time | 464.707 − 453.065 = 11.642 s |

| Topic | Active-only Rate (Hz) |
|-------|-----------------------|
| `/detections` | 30.035 |
| `/timing` | 30.055 |
| `/tracks` | 30.022 |
| `/target` | 30.022 |

Active-only timing: p95 `loop_ms` 33.355 ms, p99 36.064 ms; `lat_ms` mean 1.541 ms, p99 5.345 ms.

### Plots produced
- [x] `artifacts/figures/timing/lat_ms_hist.png`, `artifacts/figures/timing/lat_ms_cdf.png`
- [x] `artifacts/figures/timing/loop_ms_hist.png`, `artifacts/figures/timing/loop_ms_cdf.png`
- [x] `artifacts/figures/timing/pub_dt_ms_timeseries.png`
- [x] Bag-tagged copies saved for both runs.

---

## Blockers / Issues

- `ros2 topic hz` does not accept multiple topics in one command — must run one topic at a time.
- Detached recorder ran without finalising metadata until `SIGINT`; fixed by always stopping with `SIGINT` (ensures `metadata.yaml` is written). See record recipe in section F.

---

## Next Actions (carry to 02-27)

- [ ] Wire tracker runtime into timing breakdown: populate `track_ms` in `tracker_node` (measure `perf_counter_ns()` around `self.tracker.update()`); publish on `/timing_tracker`; optionally merge with `/timing` offline by `frame_id`.
- [ ] Start camera-on dry-run checklist: device bring-up, image format, FPS lock, and bagging protocol.
- [ ] Decide how to handle loop gaps in online monitoring: simple `stream_alive` boolean in `/timing` or a state machine.
- [ ] Update README with looping service, bagging protocol, and active-only analysis approach (finish outstanding checkbox).

---

## Key Commands

```bash
# Inspect bags
cd ~/Desktop/Thesis/bags
ros2 bag info 2026-02-25__slice__secondary
ros2 bag info 2026-02-25__slice__primary

# Run offline metrics script
cd ~/Desktop/Thesis
python3 tools/analyse_bag_timing.py \
  artifacts/bags/raw/2026-02-25__slice__primary

# Suppress FastDDS SHM warning for future recordings
export RMW_FASTRTPS_USE_SHM=0

# Re-run slice if a fresh bag is needed
cd ~/Desktop/Thesis/ros2_ws
source install/setup.bash
ros2 launch thesis_bringup first_ros2_slice.launch.py
```

---

## Scope Boundary (what NOT to do today)

- No ByteTrack integration
- No MAVROS / Pixhawk commands
- No camera bring-up (CSI ribbon still not connected)
- No SORT parameter changes
- No new ROS nodes — polish and measure only

---

## Environment Snapshot

| Component | Version / Value |
|-----------|----------------|
| Kernel | `6.8.0-1047-raspi` |
| Hailo driver | `hailo_pci 4.20.0` (DKMS) |
| Hailo firmware | `hailo8_fw 4.20.0` |
| HailoRT (container) | `4.20.0-1` |
| tappas-core (container) | `3.31.0+1-1` |
| ROS 2 distro | Jazzy |
| Container name | `pi-ai-kit-ubuntu-hailo-ubuntu-pi-1` |
| Network mode | `host` (`127.0.0.1:5555`) |
| Postprocess SO | `/usr/lib/aarch64-linux-gnu/hailo/tappas/post_processes/libyolo_hailortpp_post.so` (`filter`) |
| HEF | `/root/thesis_service/resources/hefs/yolov6n_hailo8.hef` |
| Test clip | `example_640_x10_safe.mp4` |
| Primary bag | `2026-02-25__slice__primary` (109.836 s, 9.5 MiB MCAP) |
