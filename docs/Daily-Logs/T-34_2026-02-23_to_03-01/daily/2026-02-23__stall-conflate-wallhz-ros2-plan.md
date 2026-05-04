# Daily Log — 2026-02-23 — Stall Root-Cause, CONFLATE Fix, Wall Hz vs PTS Hz & ROS 2 Transition Plan

## Goal
- Confirm that observed Hz dips were caused by MP4 clip-boundary looping, not by the tracker or ZMQ stack.
- Separate publisher stalls (`pub_dt_ms`) from server frame cadence (`pts_dt_ms`) and subscriber latency (`lat_ms`) using explicit per-field instrumentation.
- Fix loop timing instrumentation and a duplicated `t_pub` delta bug in the client.
- Validate stable 30 Hz baseline using an extended MP4 (`example_640_x10.mp4` via `ffmpeg -stream_loop`).
- Freeze SORT baseline parameters after a long, clean run with no anomalous spikes.
- Define the full onboard pipeline architecture and plan the transition from standalone tester to ROS 2 node graph.

**Done today:** Stall root-cause confirmed (MP4 EOS artefact). Instrumentation corrected. Real-time baseline methodology locked (sync on → 30 Hz); throughput mode validated (sync off). `CONFLATE=1` debugged and confirmed working. SORT params frozen. ROS 2 node graph defined.

---

## Context

| Key | Value |
|-----|-------|
| Hardware | Raspberry Pi 5 + AI HAT+ (Hailo) + Pixhawk 4 (ArduPilot) + F9P GNSS *(camera not connected)* |
| Host OS | Ubuntu 24.04, ROS 2 Jazzy, Docker |
| Repo / compose | `~/pi-ai-kit-ubuntu` → `docker-compose.yaml` |
| Container | `pi-ai-kit-ubuntu-hailo-ubuntu-pi-1` |
| Network mode | `host` — client connects to `127.0.0.1:5555` |
| Test input | `/root/hailo-rpi5-examples/resources/example_640_x10.mp4` (extended clip) |
| ZMQ topic | `b"dets"` |
| Payload | `seq`, `frame_id`, `pts_ns`, `t_pub`, `dets[]` (normalised xywh) |
| Tracker | SORT (Kalman + Hungarian IoU matching with gating) |
| Baseline params | `--iou 0.18 --max_age 4 --min_hits 3 --min_score 0.35 --print_every 60` |

---

## Work Done

### A) Runtime diagnosis and stall root-cause

- Observed large `recv_ms` spikes (~540 ms) appearing periodically in per-stage timing output, correlating with the Hz dips first seen on 02-22.
- Wrote a standalone ZMQ probe script to monitor `t_pub` deltas directly, flagging any inter-publish gap > 80 ms.
- Confirmed publisher-side stalls of ~180 ms and ~540 ms that aligned precisely with the MP4 clip boundary (EOS → rewind).
- Disabled `HAILO_LOOP_VIDEO` to observe clean EOS behaviour; verified the stalls disappeared on a single-pass run.
- Created an extended test clip using `ffmpeg -stream_loop 9` to produce `example_640_x10.mp4`, removing clip-boundary events from the test window.
- Re-ran the full client with the extended clip: stable 30 Hz throughout, no >500 ms spikes observed.
- **Conclusion:** stalls were MP4 loop boundary artefacts in the GStreamer pipeline. The SORT tracker, JSON parsing, and ZMQ transport are not the cause.

### B) Instrumentation corrections

- Fixed a bug where `t_pub` delta was being computed twice in the same loop iteration (duplicate assignment).
- Fixed `loop_q` measurement so it now captures the full per-frame wall-clock iteration time, from `recv` entry to end of JSONL write.
- Added `pub_dt_ms` (delta between successive `t_pub` values) as a dedicated metric alongside `pts_dt_ms`.
- Clarified the three distinct timing signals and their meaning:
  - `pts_dt_ms` — server-side GStreamer frame cadence (from `pts_ns`).
  - `pub_dt_ms` — publish cadence (from `t_pub`); reveals publisher-level stalls.
  - `lat_ms` — pub→sub one-way latency; reveals network/socket delays only.
- Added `pub_dt_ms` field to JSONL record output for offline analysis.

### F) ZMQ backlog control: CONFLATE vs drain-to-latest

- Tried `zmq.CONFLATE=1` on the SUB socket to ensure the client always processes the latest message.
- Initially got persistent receive timeouts after setting `CONFLATE`.
- **Root cause:** the client was calling `s.recv()` but then unpacking the result as multipart `(topic, payload)`. `CONFLATE` buffers a single atomic message — mixing `recv()` with topic-frame expectations breaks the receive path silently.
- Fixed: standardised the receive path to `recv_multipart()` for all topic-framed messages (where PUB sends `[topic, payload]`), and `recv()` only for single-frame payloads. Both paths now work correctly whether or not `CONFLATE` is set.
- After the fix, `CONFLATE=1` works reliably: always processes the latest available frame, never accumulates a backlog, drain loop becomes unnecessary.
- Both patterns are now validated:
  - **CONFLATE=1** — preferred for "control-style" latest-state consumption; lowest code complexity.
  - **Drain-to-latest loop** — fallback if `CONFLATE` proves unstable on a given ZMQ version or platform.
- Updated baseline recommendation: use `CONFLATE` by default; keep drain-to-latest as a documented fallback.

### C) SORT baseline lock

- Confirmed frozen parameters after extended-clip run:

  | Parameter | Value |
  |-----------|-------|
  | `iou` | `0.18` |
  | `max_age` | `4` |
  | `min_hits` | `3` |
  | `min_score` | `0.35` |

- Observed during stable run:
  - `match_ms` typically 0.1–0.3 ms (< 0.5 ms p95).
  - Confirmed track count stable; no ID explosion under moderate detection load.
  - Drain count consistently 0 — no backlog accumulation.
  - Confirmed track count tracks detection count (± 1–2) steadily.

### D) JSONL record mode

- Implemented and validated JSONL logging; each frame record includes:
  - `pubsub_ms`, `pub_dt_ms`, `pts_dt_ms`
  - per-stage timing (`recv_ms`, `json_ms`, `track_ms`, `loop_ms`) when `--timing` is active
  - `n_dets`, `n_tracks`, `n_confirmed_now`, `match_ms`, `drained`
- Verified that file write (line-buffered, 1 MB buffer) does not measurably affect loop timing.
- JSONL output is ready for offline latency plots and track ID stability metrics.

### E) Pipeline architecture definition (Pi-only baseline)

- Defined the full onboard perception-to-control pipeline:

  ```
  Camera → Preprocess → Hailo Inference (Docker) → ZMQ
       → inference_client_node (ROS 2)
       → tracker_node (SORT)
       → target_selector_node
       → controller_node
       → MAVROS → Pixhawk
  ```

- Confirmed Docker inference service remains a standalone boundary component; it publishes raw detections only and is unaware of tracking or control.
- Defined required ROS 2 message types:
  - `vision_msgs/Detection2DArray` — raw detections from inference client.
  - Custom `Track2DArray` — tracked objects with persistent IDs, bbox, and confidence.
  - Custom `TargetState` — single selected target with position, ID, and quality estimate.
- Defined "done baseline" criteria:
  - Real-time detection at ≥ 25 Hz from Hailo.
  - Stable track IDs across frames (SORT, no ID explosion).
  - Single target state published per frame.
  - Measurable end-to-end latency (camera → `TargetState`) < 100 ms.
  - Command output reachable through MAVROS.

### G) Patch notes

- Patched `gstreamer_app.py::on_eos()` so `HAILO_LOOP_VIDEO=0` exits cleanly with no rewind stall. This is the chosen fix for EOS artefacts.
- Suppressed pipeline string printing where possible (note: some prints may still originate from other modules or GStreamer debug output).
- Updated client metrics: fixed `t_pub` delta duplication, fixed loop timing span to cover full iteration, added `pub_dt_ms`, clarified signal meanings (`pts_dt_ms` vs `pub_dt_ms` vs `lat_ms`).
- Standardised ZMQ receive path to `recv_multipart()` for topic-framed messages throughout client.

---

## Results

### Extended-clip baseline run (`example_640_x10.mp4`, sync enabled)

> **Note:** figures below are from a run with GStreamer clock sync **enabled** (no `--disable-sync`). This is the real-time reference baseline.

- Wall RX rate: `~30 Hz` stable throughout — no periodic dips.
- `pub_dt_ms` avg: `~33 ms` (consistent with 30 Hz publish cadence).
- `pts_dt_ms` avg: `~33.33 ms` (GStreamer clock locked at 30 FPS) — matches wall rate as expected with sync.
- No `recv_ms` spikes > 50 ms observed.
- Pub→sub latency: avg `~3–4 ms`, p95 `~8–10 ms`, max `~15 ms`.
- SORT `match_ms` avg/p95: `~0.15 ms / ~0.45 ms`.
- Pi temp range: `~52 °C` to `~56 °C` under sustained load.
- Drain count: `0` consistently — client keeps up with publisher.

### Throughput run (`example_640_x10.mp4`, `--disable-sync`)

> **Note:** with `--disable-sync`, GStreamer runs unconstrained — `wall_hz` can far exceed the 30 FPS video timestamp cadence. Do **not** interpret `wall_hz` as "real-time FPS" here.

- `wall_hz` (client loop rate): exceeds 30 Hz — pipeline throughput, not real-time cadence.
- `pub_dt_ms` avg: lower than 33 ms — reflects burst pacing, not sensor rate.
- `pts_dt_ms` avg: still `~33.33 ms` — GStreamer PTS advances at source rate regardless of sync setting; use this as the true frame cadence reference.
- `pts_hz` ≠ `wall_hz` when sync is disabled; `pts_hz` ≈ 30 Hz always (source rate), `wall_hz` reflects decode + infer throughput.
- Use `--disable-sync` only for max-throughput benchmarking; use sync-enabled for all real-time latency and Hz validation.

### Stall attribution summary
| Signal | Short clip (loop) | Extended clip |
|--------|-----------------|---------------|
| `pub_dt_ms` max | ~540 ms | ~40 ms |
| `recv_ms` max | ~540 ms | ~18 ms |
| `lat_ms` max | ~25 ms | ~15 ms |
| Root cause | MP4 EOS rewind | — (none) |

**Causality confirmed:** spikes track `pub_dt_ms`, not `lat_ms` or `track_ms`. Stalls originate at the publisher boundary, not in SORT, JSON, or ZMQ transport.

### Per-stage timing p95 (extended clip, `--timing`)
| Stage | p95 ms |
|-------|--------|
| `recv` | `~4` |
| `json` | `~0.3` |
| `track` | `~0.4` |
| `loop` | `~5` |

---

## Blockers / Issues
- Short MP4 + `HAILO_LOOP_VIDEO=1` will always produce publisher stalls at clip boundaries. **Chosen fix:** patch `on_eos()` to exit cleanly (`HAILO_LOOP_VIDEO=0`) and use the extended clip (`example_640_x10.mp4`) or live camera for all baseline runs. Do not rely on GStreamer loop for sustained testing.
- Camera (CSI ribbon) still not connected — real-time feed validation deferred.
- `hailodevicestats` still unsupported on AI HAT+; temperature monitoring remains Pi sysfs only.

---

## Lessons Learned
- MP4 looping artefacts can closely mimic real-time network or compute stalls — always attribute stalls to a specific signal before drawing conclusions.
- Separating `pub_dt_ms` (publisher cadence) from `lat_ms` (transport) from `pts_dt_ms` (source cadence) is essential for honest latency measurement.
- **Throughput vs real-time confusion:** with `--disable-sync`, `wall_hz` (client loop rate) can exceed the video timestamp cadence (`pts_hz ≈ 30 Hz`). Always label results as "throughput" or "real-time" explicitly, and use `pts_dt_ms` (not `wall_hz`) as the source cadence ground truth. Use sync-enabled runs for real-time 30 Hz validation.
- `zmq.CONFLATE=1` requires the receive path to be fully consistent — mixing `recv()` and `recv_multipart()` on a topic-framed socket silently breaks message delivery. Standardise on `recv_multipart()` for all topic-framed sockets.
- Avoid premature algorithm switching (e.g. ByteTrack) before runtime stability is proven and attributed; instrument first, optimise later.
- A standalone probe script (single-purpose, no tracker) is a fast, reliable way to isolate ZMQ-level behaviour from application-level behaviour.

---

## Next Actions

### ROS 2 node graph
- [ ] Wrap current ZMQ client into `inference_client_node` (ROS 2, publishes `Detection2DArray`).
- [ ] Define custom `Track2DArray` and `TargetState` message packages.
- [ ] Implement `tracker_node` (wraps SORT, subscribes detections, publishes `Track2DArray`).
- [ ] Implement minimal `target_selector_node` (subscribes `Track2DArray`, publishes `TargetState`).
- [ ] Create single launch file running: Docker inference service + `inference_client_node` + `tracker_node` + `target_selector_node`.
- [ ] Add `rosbag2` recording of perception topics and timing fields for offline validation.

### After ROS graph baseline works
- [ ] Begin ByteTrack integration as a drop-in replacement for SORT in `tracker_node`.

---

## Plan for 2026-02-24 — First ROS 2 Slice

**Goal:** turn the working standalone pipeline into the first functional ROS 2 node graph without changing the service boundary.

### 1) `inference_client_node`
- Wrap the ZMQ SUB + JSON parsing into a minimal ROS 2 node.
- Keep existing filtering (`min_score`) as-is.
- Publish `vision_msgs/Detection2DArray` (or a custom `Det2DArray` if full field control is needed).
- `CONFLATE=1` on the ZMQ socket; ROS subscriber QoS depth = 1.

### 2) `thesis_msgs` package — define now, not later
Create a small custom message package:
```
thesis_msgs/msg/Track2D.msg
  uint32 id
  float32[4] bbox        # [cx, cy, w, h] normalised
  float32 score
  string label
  uint32 age
  uint32 hits
  builtin_interfaces/Time last_update
  float32[2] velocity    # optional

thesis_msgs/msg/Track2DArray.msg
  std_msgs/Header header
  Track2D[] tracks

thesis_msgs/msg/TargetState.msg
  std_msgs/Header header
  uint32 id
  float32[2] center      # normalised [cx, cy]
  float32[4] bbox
  float32 confidence
  float32 quality        # optional
```

### 3) `tracker_node`
- Subscribe to detections topic.
- Run SORT (current code, zero changes).
- Publish `Track2DArray`.

### 4) Recording and validation
- Record a `rosbag2` bag containing: `/detections`, `/tracks`, `/timing`.
- Add a per-N-messages diagnostic print (rate + end-to-end latency), mirroring the `client_tester` print style.

### 5) Backlog policy for ROS
- ZMQ SUB: `CONFLATE=1`.
- ROS subscriber QoS: `depth=1` (keep-last).
- `target_selector` and `controller` always consume the latest state; never drain a backlog.

---

## Key Commands

```bash
# Create extended test clip (10× loop, no re-encode)
ffmpeg -stream_loop 9 -i example_640.mp4 -c copy example_640_x10.mp4

# Container: run service with extended clip
export HAILO_VIDEO_SINK=fakesink
export HAILO_LOOP_VIDEO=0
export HAILO_VIDEO_SOURCE=/root/hailo-rpi5-examples/resources/example_640_x10.mp4
cd /root/thesis_service
./run_detection_zmq.sh

# Host: standalone ZMQ pub-dt probe (t_pub stall detector)
python3 - <<'PY'
import zmq, json, time
ctx = zmq.Context.instance()
s = ctx.socket(zmq.SUB)
s.setsockopt(zmq.SUBSCRIBE, b"dets")
s.setsockopt(zmq.RCVTIMEO, 3000)
s.connect("tcp://127.0.0.1:5555")
last_t = None
while True:
    try:
        _, payload = s.recv_multipart()
        msg = json.loads(payload)
        t = msg.get("t_pub", 0)
        if last_t and t:
            dt = (t - last_t) / 1e6
            if dt > 80:
                print(f"STALL pub_dt_ms={dt:.1f}")
        last_t = t
    except zmq.error.Again:
        print("timeout")
PY

# Host: run client tester with extended clip baseline
./client_tester.py --addr tcp://127.0.0.1:5555 --topic dets --w 640 --h 640 \
  --iou 0.18 --max_age 4 --min_hits 3 --min_score 0.35 --print_every 60 \
  --gc_disable --timing \
  --record run_$(date +%Y%m%d_%H%M%S).jsonl
```

---

## Environment Snapshot

| Component | Version / Value |
|-----------|----------------|
| Kernel | `6.8.0-1047-raspi` |
| Hailo driver | `hailo_pci 4.20.0` |
| Hailo firmware | `hailo8_fw 4.20.0` |
| HailoRT (container) | `4.20.0` |
| tappas-core (container) | `3.31.0+1-1` |
| Apps Infra | `25.7.0` |
| Container name | `pi-ai-kit-ubuntu-hailo-ubuntu-pi-1` |
| Network mode | `host` (client: `127.0.0.1:5555`) |
| Test input | `example_640_x10.mp4` (10× `ffmpeg -stream_loop`) |
| Service output | ZMQ dets JSON payload |
| Tracking | SORT (Kalman + Hungarian IoU matching with gating) — parameters frozen |
| ZMQ backlog control | `CONFLATE=1` (working) OR drain-to-latest fallback |
