# Daily Plan - 2026-04-30 (Day 30) - Integration And Hardening

## Context Carry-Over

- Best current candidate:
  - Strict-latency detector candidate from Day 29 remains `yolov6n`.
  - ByteTrack remains the preferred candidate under noisy detector-output conditions, but today’s field work focused more on flight validation and system hardening than on a full ByteTrack-vs-OC-SORT comparison.
  - For live operation, tracker defaults were made more forgiving to reduce ID loss during short misses.

- Validation status so far:
  - `--record-video` flight bags are working.
  - Overlay rendering from bags is working.
  - Terminal target commands are working:
    - `ids`
    - `target <id>`
    - `clear-target`
  - Hailo direct inference was verified as actually using `/dev/hailo0`.
  - Two official flight bags were recorded and analysed.

- Remaining weakness:
  - ID stability remains fragile under target loss, occlusion, FOV exit/re-entry, and detector flicker.
  - Current bags are good for overlay review and tracker replay from recorded detections, but not ideal for rerunning new detectors because `/camera/image_raw` is not recorded.
  - Recording `/camera/image_raw` would be heavy and likely affect latency/storage, so it remains excluded from normal flight bags.
  - MAVROS over Ethernet/UDP still needs final confirmation and IMU-topic validation from the Pixhawk 6X.

## Primary Objective

Harden the live flight workflow enough for repeat field use: stable recording, Hailo verification, official flight bag capture, timing analysis, and practical tracker-parameter tuning.

## Today's Plan

- [x] Apply the next focused integration or cleanup step.
- [x] Re-run the checks that protect against regression.
- [x] Update documentation/notes where behaviour or commands changed.
- [x] Keep the decision trail explicit.
- [x] Fly and record official bags.
- [x] Verify whether Hailo acceleration is actually being used.
- [x] Analyse timing from official flight bags.
- [x] Adjust live tracker defaults to survive short target misses better.

## Evidence To Capture

### Updated baseline

- Hailo direct inference is confirmed as active:
  - `/dev/hailo0` exists.
  - `lspci` reports `Hailo-8 AI Processor [1e60:2864]`.
  - `hailortcli scan` finds device `0000:01:00.0`.
  - `hailortcli fw-control identify` reports:
    - firmware `4.23.0`
    - board name `Hailo-8`
    - architecture `HAILO8`
  - `sudo lsof /dev/hailo0` showed `perception_pipeline_node` using `/dev/hailo0`.
  - `perception_pipeline.log` reported `initialized Hailo direct backend`.
  - Live process launched with:
    - `inference_backend:=hailo_direct`
    - `allow_stub_fallback:=false`
  - No `stub` or `fallback` lines were found in the perception log.

- Tracker global defaults were changed to be more tolerant of short misses:

```bash
TRACKER_IOU_THRESHOLD=0.12
TRACKER_MAX_AGE=30
TRACKER_MIN_HITS=2
TRACKER_CENTRE_GATE=420.0
```

- Reason for tracker default change:
  - Previous `TRACKER_MAX_AGE=4` only allowed roughly `4 / 14 Hz = 0.29 s` of missed detections.
  - New `TRACKER_MAX_AGE=30` allows roughly 2 seconds of missed detections at the observed live tracking rate.
  - This is more appropriate for brief occlusion, short detector flicker, or small FOV exits during live testing.

- Preferred future flight command:

```bash
./tools/start_live_stack.sh \
  --profile performance \
  --record-video \
  --record-mavros \
  --bag-tag flightXX_description
```

- Rationale:
  - Flight 02 used `--profile performance`.
  - Flight 01 used `--profile daily`.
  - The performance profile showed better timing in the official flight analysis.

### Official flight bags

Recorded official bags:

```text
bags/live_camera/2026-04-30__12-29-33__video__oficial_flight_01
bags/live_camera/2026-04-30__12-42-17__video__oficial_flight_02
```

Timing reports generated:

```text
reports/timing/2026-04-30__12-29-33__video__oficial_flight_01__timing.md
reports/timing/2026-04-30__12-42-17__video__oficial_flight_02__timing.md
```

Timing figures generated:

```text
figures/timing/2026-04-30__12-29-33__video__oficial_flight_01/
figures/timing/2026-04-30__12-42-17__video__oficial_flight_02/
```

### Official flight timing comparison

Flight 01 used `--profile daily`; Flight 02 used `--profile performance`.

| Metric | Flight 01 daily | Flight 02 performance | Better |
|---|---:|---:|---|
| Duration | 408.892 s | 348.082 s | n/a |
| Full-bag `/detections` Hz | 16.307 Hz | 17.269 Hz | Flight 02 |
| Active-only `/detections` Hz | 21.282 Hz | 23.147 Hz | Flight 02 |
| Active `e2e_det_ms` p95 | 49.233 ms | 44.207 ms | Flight 02 |
| Active `e2e_det_ms` p99 | 57.329 ms | 51.748 ms | Flight 02 |
| Active `pub_dt_ms` p95 | 90.591 ms | 83.959 ms | Flight 02 |
| Active `pub_dt_ms` p99 | 98.238 ms | 97.683 ms | Similar |
| `track_ms` p95 | 25.432 ms | 20.928 ms | Flight 02 |
| `track_ms` p99 | 46.891 ms | 34.978 ms | Flight 02 |
| Gap removed | 130.819 s | 113.325 s | Flight 02 |

Interpretation:

- Both flights satisfied the active-window latency target.
- Active-window `e2e_det_ms` p95 stayed below 50 ms in both official flights.
- This is comfortably below the thesis target of p95 ≤ 200 ms and also below the stretch target of p95 ≤ 100 ms during active windows.
- The main issue is not raw inference compute time, but cadence continuity.
- Both bags had large gap-filtered removed time:
  - Flight 01: `130.819 s`
  - Flight 02: `113.325 s`
- Therefore, future analysis must report both:
  - full-bag timing
  - active-only/gap-filtered timing

Thesis-safe conclusion:

```text
The official flight bags show that the onboard perception pipeline sustained approximately 16 to 17 Hz over the full bags and over 21 Hz during active, gap-filtered windows. Active-window end-to-end detection latency remained below 50 ms at p95 in both flights, satisfying the closed-loop latency target. The main limitation was not inference compute time, but cadence discontinuity, so flight results should be evaluated using gap-aware timing metrics rather than only mean FPS.
```

### Commands used

```bash
cd "$THESIS_ROOT"

# Hailo verification
ls -l /dev/hailo* 2>/dev/null || true
lspci -nn | grep -i hailo || true
lsmod | grep -i hailo || true
hailortcli scan || true
hailortcli fw-control identify || true
sudo fuser -v /dev/hailo0 2>/dev/null || true
sudo lsof /dev/hailo0 2>/dev/null || true
pgrep -af "perception_pipeline_node|hailo|ros2 run thesis_bringup perception_pipeline_node" || true

LOG="$THESIS_ROOT/ros2_ws/log/live_stack/latest/perception_pipeline.log"
grep -Ei "hailo|hailort|hef|vdevice|device|backend|stub|fallback|error|exception" "$LOG" | tail -n 120 || true
grep -Ei "stub|fallback" "$LOG" || echo "[ok] no stub/fallback lines found"

# Render official videos
BAG1="$THESIS_ROOT/bags/live_camera/2026-04-30__12-29-33__video__oficial_flight_01"
BAG2="$THESIS_ROOT/bags/live_camera/2026-04-30__12-42-17__video__oficial_flight_02"

source /opt/ros/jazzy/setup.bash
source "$THESIS_ROOT/ros2_ws/install/setup.bash"

python3 tools/bag/render_bag_overlay_video.py "$BAG1" \
  --output-size 1280x720 \
  -o "$THESIS_ROOT/reports/videos/2026-04-30__12-29-33__video__oficial_flight_01__overlay_720p.mp4"

python3 tools/bag/render_bag_overlay_video.py "$BAG2" \
  --output-size 1280x720 \
  -o "$THESIS_ROOT/reports/videos/2026-04-30__12-42-17__video__oficial_flight_02__overlay_720p.mp4"

# Timing analysis
source /home/francisco/Desktop/Thesis-Code/.venv/bin/activate
source /opt/ros/jazzy/setup.bash
source "$THESIS_ROOT/ros2_ws/install/setup.bash"

export PYTHONPATH="$THESIS_ROOT/tools:$THESIS_ROOT:${PYTHONPATH:-}"
export MPLBACKEND=Agg

python3 tools/analysis/analyse_bag_timing.py "$BAG1"
python3 tools/analysis/analyse_bag_timing.py "$BAG2"

# Dependency repair for timing plots
pip install "matplotlib>=3.8,<3.10"
pip check

# Tracker-default validation
grep -n "TRACKER_IOU_THRESHOLD\|TRACKER_MAX_AGE\|TRACKER_MIN_HITS\|TRACKER_CENTRE_GATE" tools/lib/live_defaults.sh
bash -n tools/lib/live_defaults.sh
bash -n tools/start_live_stack.sh
```

### Repeated checks

- `bash -n tools/lib/live_defaults.sh`
- `bash -n tools/start_live_stack.sh`
- Hailo device visibility checked.
- Live perception process checked against `/dev/hailo0`.
- Timing analyser successfully generated reports for both official bags.
- `pip check` passed after installing `matplotlib`.

### Documentation touched

- Day log updated with:
  - official flight bag paths
  - Hailo verification
  - tracker default change
  - timing comparison between `daily` and `performance`
  - limitations of `/camera/dashboard` recording versus `/camera/image_raw`
  - explanation that 1080p render is only upscaling when the source is `640x360`

### Open issues

- Need to render and visually inspect official overlay videos if not already reviewed fully.
- Need target-lock quantitative analysis:
  - visible ratio
  - lost events
  - longest continuous lock
  - total lost time
  - ID changes
  - reacquisition events
- Need to decide whether to record a lightweight detector-input topic in future:
  - not `/camera/image_raw` by default
  - possible future `/camera/perception_640`
- MAVROS Ethernet/UDP link to Pixhawk 6X still needs final validation:
  - `eth0` was up but initially had no IPv4 address.
  - Need to set Pi Ethernet IP, for example `169.254.21.183/16`.
  - Need Pixhawk-side MAVLink UDP output to Pi port.
  - Need to confirm `/mavros/imu/data`, `/mavros/imu/data_raw`, and `/mavros/imu/mag`.
- Import path issue remains in moved analysis scripts:
  - `analyse_bag_timing.py` needed `PYTHONPATH="$THESIS_ROOT/tools:$THESIS_ROOT:${PYTHONPATH:-}"`.
  - Permanent fix should add repo/tool path injection inside moved scripts.

## End-Of-Day Notes

### What is now stable

- `--record-video` workflow is stable enough for field use.
- Official flight bags were recorded successfully.
- Hailo direct inference was confirmed with process-level evidence.
- Overlay renderer works with output size control and letterbox correction.
- Active-window latency is strong:
  - Flight 01 active p95 `e2e_det_ms`: `49.233 ms`
  - Flight 02 active p95 `e2e_det_ms`: `44.207 ms`
- The `performance` profile appears preferable for official flight tests.
- More forgiving tracker defaults are now global and better aligned with short detector misses.
- The system can sustain above 15 Hz over full official bags and above 21 Hz during active windows.

### What still feels risky

- Cadence continuity is still weak:
  - Flight 01 gap removed: `130.819 s`
  - Flight 02 gap removed: `113.325 s`
- ID stability is still not solved by tracker tuning alone.
- A larger `max_age` helps short gaps but can create stale/ghost tracks in multi-person scenes.
- Current official bags cannot fairly rerun new detectors because `/camera/image_raw` was not recorded.
- Recording `/camera/image_raw` directly would be too heavy for normal flight use.
- MAVROS Ethernet and IMU logging are not yet fully validated.
- The analysis scripts need import-path hardening after the `tools/` reorganisation.

### What Friday needs to close

1. Render and watch both official overlay videos carefully.
2. Build `tools/analysis/analyse_live_target_lock.py`.
3. Quantify:
   - target visible ratio
   - lost events
   - longest lock segment
   - reacquisition behaviour
   - ID changes
4. Fix import-path handling in moved analysis scripts.
5. Validate MAVROS Ethernet UDP connection and IMU topics from Pixhawk 6X.
6. Decide whether to add a lightweight detector-input recording option:
   - likely `/camera/perception_640`
   - not raw `/camera/image_raw` as default
7. Start the target-specific identity memory design document using the official flight failures as motivation.
8. Use `--profile performance` for the next official flight unless a controlled A/B test says otherwise.