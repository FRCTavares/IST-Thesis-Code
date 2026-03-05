# Daily Log — 2026-02-27 — Benchmark Harness v0, Repo Cleanup, Smoke Test Baseline (Week 9, Day 4)

## Goal
Build a replayable benchmarking harness so the same detections stream can be replayed through different trackers and analysed into a markdown summary with plots.

**Target outcome:**
- Replayable eval mode (bag play + tracker + selector + record outputs)
- Standard tracker output contract
- Tracking metrics script v0
- Decide tracker candidates for A, B, C

---

## Context

| Key | Value |
|-----|-------|
| Hardware | Raspberry Pi 5 + AI HAT+ (Hailo) + Pixhawk 4 + F9P GNSS |
| Camera | Not available, tests use bag replay |
| Host OS | Ubuntu 24.04, ROS 2 Jazzy |
| Storage | MCAP |
| Repo | `~/Desktop/Thesis-Code` |
| Targets | Perception 15 FPS, control 30 Hz with prediction, latency budget 200 ms |

---

## Work Plan

### A) Create replayable evaluation mode (core)
- [x] Implemented replay runner launch file.
- Launch plays an input bag and records tracked outputs into a new MCAP bag directory.
- Outputs recorded: `/tracks`, `/target`, `/timing_tracker`.
- Naming: `YYYY-MM-DD__eval__<rawbag>__<tracker>__rN` (collision suffix enabled).
- **Deliverable:** `ros2_ws/src/thesis_bringup/launch/eval_replay.launch.py` ✓
- Notes:
  - `ros2 bag record` always prints "Press SPACE", ignore.
  - Recorder finalises cleanly on SIGINT, but for replay we will make shutdown automatic (future improvement).

### B) Define the tracker interface contract
- [x] Contract drafted and written into `thesis_tracker/README.md` (input `/detections`, outputs `/tracks` + `/timing_tracker` with `track_ms`).
- Contract v0:
  - Input: `/detections` (`vision_msgs/Detection2DArray`)
  - Output: `/tracks` (`thesis_msgs/Track2DArray`)
  - Output: `/timing_tracker` (`thesis_msgs/Timing`) with `track_ms` populated
- Notes:
  - `Timing.msg` has no header, do not assign `tmsg.header`.

### C) Implement metric extraction script v0
- [x] Implemented `tools/analyse_bag_tracking.py`.
- Reads `/target` + `/timing_tracker`, generates:
  - Target lock continuity (quality-gated)
  - Reacquisition events and timings
  - Debounced target switches (k frames)
  - `track_ms` stats + plots
- Outputs:
  - `reports/tracking/<eval_run>/summary.md`
  - `target_lock_timeseries.png`, `track_ms_cdf.png`, `reacq_hist.png`
- **Deliverable:** `tools/analyse_bag_tracking.py` ✓

### D) Choose tracker candidates
- [x] A: SORT (baseline, working)
- [x] B: OC-SORT (next, occlusion handling)
- [x] C: ByteTrack (shippable, predictable compute)
- Rationale to write into `Written Logs/.../artefacts.md` tomorrow.

---

## System organisation work (today)
- Reorganised workspace layout and outputs:
  - `bags/raw/`, `bags/eval/`, `reports/timing/`, `reports/tracking/`, `figures/timing/`
- Removed unwanted git repo in `hailo-rpi5-examples` (now plain folder).
- Created top-level Git repo for thesis code:
  - repo name: `Thesis-Code` (`FRCTavares/Thesis-Code`)
  - tag: `v0.1-smoke`
  - fixed `.gitignore` to exclude bags, reports, figures, ROS build artefacts, vendor payloads.
- Set `THESIS_ROOT` env var and updated scripts/launch defaults to use it.
- Fixed rclpy shutdown instability in `thesis_tracker` (tracker_node crash during eval shutdown).
- Added SSH key on Pi and switched remote to SSH.

---

## Results

### Deliverables checklist
- [x] `ros2_ws/src/thesis_bringup/launch/eval_replay.launch.py`
- [x] `tools/analyse_bag_tracking.py`
- [x] `tools/analyse_bag_timing.py` default outputs working under new folders
- [x] Folder structure + repo pushed + tag `v0.1-smoke`
- [x] Tracker contract in `thesis_tracker/README.md` ✓
- [x] Tracker candidates rationale in `artefacts.md` ✓

### Smoke test (end-to-end, verified)

Recorded a new raw bag using a safe recipe (no background job control):
- Raw bag: `bags/raw/2026-02-27__slice__smoke`
- Duration: 59.03 s
- Counts:
  - `/detections`: 1772
  - `/timing`: 1772
  - `/target`: 1772
  - `/tracks`: 1723

Timing analysis ran successfully:
- Report: `reports/timing/2026-02-27__slice__smoke__timing.md`
- Figures: `figures/timing/2026-02-27__slice__smoke/`

Eval replay ran successfully and produced:
- Eval bag: `bags/eval/2026-02-27__eval__2026-02-27__slice__smoke__sort`
- Counts:
  - `/target`: 14129
  - `/timing_tracker`: 5051
  - `/tracks`: 6774

Tracking analysis ran successfully:
- Report: `reports/tracking/2026-02-27__eval__2026-02-27__slice__smoke__sort/summary.md`

### Harness commands (final, verified)

```bash
export THESIS_ROOT="$HOME/Desktop/Thesis-Code"

# 1) Record raw bag (reliable)
source "$THESIS_ROOT/ros2_ws/install/setup.bash"
BAG="$THESIS_ROOT/bags/raw/$(date +%F)__slice__smoke"
timeout -s SIGINT 60s ros2 bag record --storage mcap -o "$BAG" \
  --topics /detections /timing /tracks /target
ros2 bag info "$BAG"

# 2) Timing analysis
python3 "$THESIS_ROOT/tools/analyse_bag_timing.py" "$BAG"

# 3) Replay eval
cd "$THESIS_ROOT/ros2_ws"
source install/setup.bash
ros2 launch thesis_bringup eval_replay.launch.py bag:="$BAG" tracker:=sort

# 4) Tracking analysis (newest eval bag)
cd "$THESIS_ROOT"
EVAL_BAG="$(ls -td "$THESIS_ROOT/bags/eval/"*__eval__"$(basename "$BAG")"__sort* | head -n 1)"
python3 tools/analyse_bag_tracking.py "$EVAL_BAG"
```

---

## Issues / Risks
- If you background `ros2 bag record` (`&`), it can be suspended (`Stopped (tty output)`) and never finalise. Use `timeout -s SIGINT` always.
- Inference long-run loop inside container still needs a clean "forever" command path; confirm mount path and script entrypoint for repeatability.
- `Timing` has no header — ensure tracker node does not assign one.

---

## Next steps (Day 28)

**Benchmark harness polish**
- [x] Tracker contract in `ros2_ws/src/thesis_tracker/README.md` ✓
- [x] Tracker candidates rationale in `artefacts.md` ✓
- [x] Add "fraction locked" and "total lost time" metrics to tracking analysis report ✓
- [x] Add automatic shutdown to eval replay when `ros2 bag play` exits ✓

**Trackers**
- [ ] Implement OC-SORT under `tracker:=ocsort` with same output contract.
- [ ] Implement ByteTrack under `tracker:=bytetrack` with same output contract.
- [ ] Add per-tracker YAML configs and load via launch.

**Comparison run**
- [ ] Run same raw bag through `sort`, `ocsort`, `bytetrack`, generate one comparison markdown table.

---

## Links
- Week summary: `../weekly.md`
- Week index: `../index.md`
- Artefacts: `../artefacts.md`
