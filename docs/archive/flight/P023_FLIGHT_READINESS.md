# P0.23 Flight-Readiness Gate

## Purpose

This document freezes the live profile and operational procedure used for
Issue #50. It separates software validation from camera, Pixhawk, ground-run,
and flight evidence.

The system must never arm automatically. MAVROS telemetry recording does not
grant control authority. Any wrong-target lock requires an immediate return to
manual control and termination of the autonomous test.

## Frozen software baseline

- Base repository commit before the P0.23 software gate:
  `dbeb678a895b76e6833bb697069bffd98426dd5f`
- Canonical source configuration:
  `ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml`
- Runtime-installed configuration:
  `ros2_ws/install/thesis_bringup/share/thesis_bringup/config/tim_mars_canonical.yaml`
- Canonical configuration SHA-256:
  `55332935fe859edff60bedf910f126487b5da6a8e13bbe5bb7662f2645359dbc`
- Startup profile: `safe-camera`
- Detector: YOLOv6n on Hailo
- Tracker: ByteTrack
- TIM mode: MARS
- Appearance extraction: enabled
- MARS model: `models/reid/mars-small128.pb`
- Appearance image topic: `/camera/dashboard`
- Appearance maximum image age: 250 ms
- Appearance recompute minimum interval: 250 ms
- Appearance cache lifetime: 750 ms
- Live source-observation and local-receive stale timeout: 0.90 s
- MAVROS control mirroring: disabled by default
- Controller target authority: `/target_memory_mars`
- Raw dashboard target: `/target` (diagnostic/recording only)
- Runtime detector and tracker switching: disabled

## Target-authority graph

The live flight profile uses one explicit authority chain:

1. The dashboard or runtime prompt sends an explicit target ID to
   `/target_memory_mars/select`, or sends clear to
   `/target_memory_mars/clear`.
2. `/target` remains the raw selected tracker observation used for telemetry,
   diagnosis, and comparison. It must not drive control.
3. `target_memory_mars_node` validates tracker continuity and publishes the
   controller-facing target on `/target_memory_mars`.
4. `control_ref_node` subscribes only to `/target_memory_mars` and publishes
   `/control_ref/cmd_vel`.
5. Every select, clear, model-switch attempt, or tracker-switch attempt first
   revokes the previous target authority. The frozen profile rejects runtime
   model and tracker switching.

`AUTO`, `null`, target ID `0`, and `clear-target` mean explicit clear. They do
not select tracker ID `0` and do not enable autonomous largest-track
selection. Explicit positive IDs are the only selection requests.

## Allowed flight-run overrides

The frozen identity and perception configuration must not be changed during
the retained runs.

Allowed operational changes are limited to:

- `--record`
- `--record-mavros`
- `--tag`
- `--bag-out-root`
- selecting or clearing the target through the dashboard API

The following are not allowed without reopening the configuration gate:

- detector replacement;
- tracker replacement;
- disabling or replacing MARS appearance;
- changing the canonical TIM configuration;
- changing identity-safety thresholds;
- changing control signs, gains, saturation, slew limits, or stale timeout;
- enabling MAVROS control mirroring for free flight without a separate
  supervised control-authority decision.
- enabling dashboard runtime detector or tracker reconfiguration.

## Exact build command

    cd ~/Desktop/Thesis-Code || exit 1
    export GIT_PAGER=cat
    export PAGER=cat
    tools/thesis_build.sh --packages-select thesis_bringup

## Exact ground-run commands

Run three complete ground scenarios:

    ./tools/start_live_stack.sh --record --record-mavros --tag p023_ground_r1

    ./tools/start_live_stack.sh --record --record-mavros --tag p023_ground_r2

    ./tools/start_live_stack.sh --record --record-mavros --tag p023_ground_r3

Each run must include:

1. selected person walking;
2. crossing with another person;
3. short occlusion;
4. leaving and re-entering the frame.

## Runtime prompt commands

- `status`: list tracked process IDs;
- `ids`: list visible tracker IDs;
- `target <id>`: select the active target;
- `clear-target`: clear the target;
- `stop`: stop the complete live stack.

Ctrl-C and SIGTERM also invoke the stack cleanup path.

## Annotation UI

    cd ~/Desktop/Thesis-Code || exit 1
    export GIT_PAGER=cat
    export PAGER=cat
    set +u
    source /opt/ros/jazzy/setup.bash
    source ros2_ws/install/setup.bash
    thesis_env/bin/python tools/bag_annotation_ui/tim_clean_ui.py --host 100.69.42.62 --port 8888

## Control-safety contract

The isolated control checks must demonstrate:

- centred target: zero yaw and near-zero forward command;
- target left: negative yaw;
- target right: positive yaw;
- target far: positive forward command;
- target near: negative forward command;
- stale, missing, future, duplicate, non-monotonic, or invalid source target:
  immediate zero command, even when the message arrived locally just now;
- raw `/target` messages never grant control authority;
- target select/clear resets control to zero until TIM-MARS publishes a new
  valid target;
- yaw and translational commands remain saturated;
- each command step respects the configured slew limit.

## Isolated target-authority ground check

Before promoting a flight candidate, run three isolated target-authority dry
runs from a clean committed checkout. The validator starts only the dashboard,
TIM-MARS, a MAVROS-disabled control node, and a small MCAP recorder in a
dedicated ROS domain. It does not start a camera, detector, tracker, MAVROS, or
aircraft.

Example:

    tools/live/validate_target_authority_ground_run.py \
      --output-dir bags/ground/p052_target_authority_<commit>/run_01 \
      --run-id p052_<commit>_run_01 \
      --ros-domain-id 82 \
      --api-port 18090 \
      --ws-port 18765

Use distinct domains and ports for each retained run. A passing summary must
cover raw-target bypass, explicit select and clear, ID reuse, rejected detector
and tracker switches, stale validated output, and TIM node restart. Retain each
`ground_check_summary.json`, `target_authority_events.jsonl`, process log set,
and `rosbag/` directory. Do not treat this isolated check as camera, Pixhawk,
hover, or flight evidence.

## Preflight checklist

### Repository and storage

- [ ] Working tree clean.
- [ ] Local HEAD equals `origin/main`.
- [ ] No root-level `log/`, `hailort.log`, or `.pytest_cache`.
- [ ] At least 40 GB free before retained flight recording.
- [ ] Raw/source/reference bags remain protected.

### Camera and inference

- [ ] `/dev/hailo0` present.
- [ ] `/dev/video0` present.
- [ ] `/dev/media0` present.
- [ ] `/dev/v4l-subdev2` present.
- [ ] Camera preflight succeeds.
- [ ] Hailo inference starts without fallback.
- [ ] Dashboard port 8765 is reachable.
- [ ] Web-video port 8080 is reachable.

### Pixhawk and safety

- [ ] Pixhawk device or configured network endpoint available.
- [ ] `/mavros/state` reports `connected: true`.
- [ ] Batteries charged and physically secured.
- [ ] Manual mode and pilot takeover verified.
- [ ] Stop command known to the operator and spotter.
- [ ] Test area clear.
- [ ] Spotter present for any tethered or low-hover test.
- [ ] Abort immediately on any wrong-target lock.
- [ ] No automatic arming.

## Ground-run evidence table

| Run | Bag path | Scenario complete | Topic rates | Latency | CPU/RAM/temp | Control fail-safe | Result |
|---|---|---|---|---|---|---|---|
| R1 | Pending | Pending | Pending | Pending | Pending | Pending | Pending |
| R2 | Pending | Pending | Pending | Pending | Pending | Pending | Pending |
| R3 | Pending | Pending | Pending | Pending | Pending | Pending | Pending |

## Held-out UAV-motion evidence

Prefer several short recordings. Preserve at least one successful small-person
UAV-motion bag with complete provenance.

Live measurements are qualitative systems evidence until compatible annotation
and an approved evaluation protocol exist.

## Current retained demonstration bags

- May:
  `bags/replay/p006b_hard_negative_03409564_2026_07_21/may`
- Seq01:
  `bags/replay/p006b_hard_negative_03409564_2026_07_21/seq01`
- Seq02 historical full-pipeline demonstration:
  `bags/source/official_flights/2026-06-19/seq02_target_reentry/full_pipeline/2026-06-19__12-52-30__video__2026-06-19__official__seq02__four_person_target_reentry__yolov8s_bytetrack_tim_mars`
- Seq03:
  `bags/replay/p006b_hard_negative_03409564_2026_07_21/seq03`
- Seq04:
  `bags/replay/p006b_hard_negative_03409564_2026_07_21/seq04`

The retained Seq02 bag is historical live-system footage and must not be
described as a current P006B or P007 result.
