# Thesis Plan: RGB-Only Onboard Person Perception for Target-Relative Micro-UAV Control (until 31 Oct)

## Goal

Enable a micro-UAV to maintain a target-relative position to a selected person using fully onboard, RGB-only perception with robust tracking of small and distant people in real time, outdoors.

## Main Thesis Question (Frozen)

How can an onboard RGB-only perception pipeline for a micro-UAV be improved to maintain robust selected-target tracking of small and distant people in real time under strict embedded compute and latency constraints?

**Primary demo goal (practical):**

- Track multiple people, select one target, and keep stable target lock while controlling yaw + lateral + forward to keep the target centred and at a desired distance.

**System feasibility targets:**

- Sustained 15 FPS onboard (minimum acceptable: 10 FPS)
- End-to-end perception latency: report mean, p50, p95, p99
  - Target: p95 ≤ 200 ms
  - Stretch: p95 ≤ 100 ms
- Identity stability across occlusions and ambiguous associations
- Reacquisition after temporary loss: ≤ 1.0 s in controlled tests

**Operating scenario assumptions:**

- Outdoor tennis court, sunlight conditions
- Typical target distance: 10 m (stretch: 15–20 m)
- Target size guideline: aim for ≥ 20 px height at typical range (below this triggers "tiny-person" handling)

---

## Platform Setup

### Hardware

- Flight controller: Pixhawk 4 (ArduPilot)
- GNSS: u-blox F9P
- Compute: Raspberry Pi 5
- Accelerator: Raspberry Pi AI HAT+ (Hailo)
- Camera: candidate selection
  - **Primary:** Raspberry Pi Camera 3 (recommended default)
  - **Alternative:** Raspberry Pi GS camera (if motion blur and rolling shutter become limiting)
- Test battery: Tattu LiPo 6S 4500 mAh XT90 (validate before flight)

### Software

- Host OS: Ubuntu 24.04 (Pi 5)
- ROS 2: Jazzy
- Autopilot bridge: MAVROS2
- Hailo runtime: containerised inference service
- Logging: rosbag2 (MCAP)
- Timing analysis: offline scripts producing thesis figures and percentile tables

---

## System Architecture

### Host (ROS 2 Jazzy)

Responsibilities:

- Camera capture and preprocessing (resize, timestamps)
- Online tracking and association logic
- Multi-target management + target selection + reacquisition policy
- Control output generation (MAVROS setpoints)
- Logging and timing instrumentation (rosbag2)

### Container (Hailo Inference Service)

Responsibilities:

- Load HEF once at startup
- Run inference and return detections
- Provide consistent and reproducible Hailo environment

### Communication Contract

Request (host to container):

- `timestamp_ns`, `width`, `height`, `encoding`, image bytes

Response (container to host):

- `timestamp_ns`
- `infer_ms`
- detections: bbox (x1, y1, x2, y2), score, class_id
- optional (for novelty experiments): lightweight appearance cue for selected-target identity support

Transport:

- ZeroMQ over localhost, fixed queue sizes, explicit drop policy

---

## Baseline Pipeline (first milestone)

Baseline behaviour:

- Person-only detector on Hailo (HEF)
- Online tracker baseline and comparisons:
  - Baseline: SORT
  - Stronger baselines: ByteTrack, OC-SORT
- Target selection:
  - Initial selection: largest bbox
  - Maintain lock while visible
- Queue discipline: fixed size queues, no backlog, drop oldest when busy

Baseline outputs per frame:

| Topic | Contents |
|-------|----------|
| `/detections` | bbox, score |
| `/tracks` | `track_id`, bbox, score, age, `last_seen` |
| `/target` | `target_track_id`, `target_bbox_cx/cy` (normalised), `target_bbox_area` or (w,h), `target_visible`, `reacquired` |
| `/timing` | `pub_dt_ms`, `e2e_det_ms`, `pre_ms`, `zmq_roundtrip_ms`, `infer_ms`, per-stage timing |
| `/timing_tracker` | `track_ms` (measured on host) |

Baseline acceptance targets:

- Live camera: 15 FPS sustained (minimum 10)
- No unbounded latency growth over long runs
- Stable lock in simple scenes
- Reacquire within 1 s after short occlusions in controlled tests

---

## Deliverable 1: Contribution A (Primary Algorithmic Novelty)

**Title:** tiny-person-aware detector/tracker improvement for selected-target onboard perception.

**Goal:** improve selected-target robustness for small and distant people while keeping runtime bounded.

**Core design scope:**

- improve detection/association behaviour in tiny and far target conditions
- define risk-aware triggers from size, confidence, and continuity signals
- preserve selected-target continuity in ambiguity windows

**Report:**

- recall by target-size bins
- lock continuity for far/tiny segments
- selected-target ID switches and reacquisition time
- latency impact under the same runtime budget

---

## Deliverable 2: Contribution C (Primary Systems Novelty)

**Title:** control-safe, latency-bounded perception-to-control integration.

**Goal:** couple identity confidence to control validity so uncertain reassociation does not propagate unsafe or overconfident control actions.

**Core design scope:**

- propagate identity confidence into control validity state
- enforce deterministic stale and lost transitions
- apply safer control behaviour in uncertain identity windows
- preserve responsiveness when identity confidence is strong

**Report:**

- behaviour under confidence transitions (including command burst checks)
- stale and lost transition determinism
- responsiveness during confident target lock
- control safety impact under ambiguity and reacquisition events

---

## Deliverable 3: Latency-Bounded ROS 2 Pipeline for Closed Loop Operation

**Goal:** predictable behaviour suitable for control.

**Design choices:**

- Fixed queues at each stage
- Frame-drop policy to avoid backlog
- Full timestamping and timing diagnostics
- Report distributions, not just averages

**Report:**

- FPS sustained over long runs
- End-to-end latency: mean, p50, p95, p99
- Per-stage breakdown and bottleneck identification
- Long-run stability: gap-filtered analysis and restart-gap accounting

## Stretch Deliverable: Contribution B (Optional)

**Title:** target-specific appearance support for ambiguity resolution and reacquisition.

**Scope rule:** implement after Contribution A and Contribution C are stable and instrumented.

**Goal:** strengthen identity continuity in ambiguity windows without breaking onboard runtime constraints.

**Report (if implemented):**

- selected-target ID switch and reacquisition changes
- ambiguity-trigger duty cycle
- latency tail impact

---

## Target-Relative Control Interface (MAVROS)

Control uses image-space target error from selected person track.

Perception to control outputs:

- `ex = (cx - 0.5)`, `ey = (cy - 0.5)` in normalised image coords
- range proxy: bbox area or height
- target confidence, age, `last_seen`
- `target_lost` flag and `reacquired` flag

Control objectives:

- **Yaw:** centre target horizontally (`ex` → 0)
- **Lateral:** reduce `ex` and stabilise lateral offset (optional if stable)
- **Forward:** hold distance using bbox proxy
- **Fail-safe when target lost:** hover and hold attitude; optional yaw scan to reacquire

Control rate:

- Desired 30 Hz control loop with prediction when perception updates are slower

---

## Evaluation Protocol

### Offline

- VisDrone MOT for repeatability
- Fixed config, fixed thresholds per experiment

### Onboard

- Tennis court tests with rosbag2 logging
- Controlled occlusion tests
- Flight validation when perception stability is proven

### Metrics

| Category | Metrics |
|----------|---------|
| Perception | precision, recall, AP (person) |
| Tracking | IDF1, ID switches, fragmentation |
| System | FPS, latency percentiles, per-stage timing |
| Control-relevant | target lock duration, time-to-reacquire, image error stats (mean/var of `ex`, `ey`), stability under load |

### Novelty-Critical Success Criteria (Frozen)

For Contribution A:

- stronger recall in small/far size bins
- longer selected-target lock continuity in distant segments
- fewer lock drops under tiny-person conditions
- acceptable latency increase

For Contribution C:

- identity uncertainty causes safer control behaviour
- stale and lost transitions are clean and deterministic
- no command bursts during confidence transitions
- control remains responsive when identity confidence is strong

For combined A + C:

- better selected-target persistence without breaking onboard runtime constraints

For Contribution B:

- better ambiguity-window continuity/reacquisition without dominating runtime budget

---

## Working Snapshot (for every result)

Always log:

- kernel, `hailo_pci`, firmware, HailoRT versions
- camera model + mode, resolution, framerate
- HEF, input res, batch size, thresholds
- measured FPS and latency percentiles
- commit hash
- control loop rate and gains (when enabled)

---

## Definition of Done

- Fully onboard ROS 2 perception stack + Hailo inference service
- Multi-person tracking + stable target selection and reacquisition
- Closed-loop target-relative control in outdoor tennis court scenario using MAVROS
- Quantified tradeoffs:
  - baseline tracker vs Contribution A
  - Contribution A vs Contribution A + Contribution C
  - secondary support extension: Contribution A + Contribution C + Contribution B
  - Full-Scene ReID Baseline as literature comparator where feasible
  - Detector-Feature Reuse Path as high-risk reference only
  - Target-Memory Appearance Path as secondary support mechanism
- Real-world validation on thesis drone with logs and a small annotated subset
