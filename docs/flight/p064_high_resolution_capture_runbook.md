# Issue #64 — High-Resolution Appearance-Source Evaluation

## 0. Experimental Status and Decision Logic

The Issue #64 question is:

> What is the lowest source resolution that materially improves identity
> robustness while the complete onboard pipeline still satisfies the
> real-time system requirements?

The detector is not a resolution variable in this experiment. YOLOv6n Hailo
inference remains fixed at 640x640. Source resolution changes the image retained
for source-coordinate tracking and TIM-MARS appearance crops.

### Stage A live-feasibility smoke — 27 August 2026

| source | detections | tracker | TIM output | detector p95 | appearance image age p50 / p95 | stale-image skips | result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 640x480 VGA | 27.05 Hz | 27.32 Hz | 27.02 Hz | 22.7 ms | 31 / 195 ms | 18/957 (1.9%) | PASS |
| 1280x720 HD | 27.36 Hz | 27.33 Hz | 27.96 Hz | 42.3 ms | 58 / 256 ms | 52/987 (5.3%) | PASS |
| 1920x1080 FHD | 26.10 Hz | 28.40 Hz | 28.40 Hz | 56.3 ms | 265 / 989 ms | 480/937 (51.2%) | FAIL freshness |

All three runs remained free of thermal throttling. The FHD failure is an
appearance-image freshness failure in the current live architecture, not a
Hailo detector-throughput failure.

The HD full-run status trace was initially all LOST because the selected
ByteTrack ID had already become stale. After selecting the current physical
target, an 8 s check produced 162/162 LOCKED status samples, 19 backend calls,
19 valid embeddings, and a clean encoding-eligible crop. The timing and image
freshness measurements from the HD run remain valid.

Do not use the current `e2e_target_ms` field as latency evidence. It is
zero/unpopulated for nearly all live samples in this path.

### Camera restart incident

An FHD-to-HD restart attempt at 12:37:48 on 27 August 2026 produced:

- DesignWare I2C timeout;
- TEVS register reads returning `ret=-110`;
- `rp1-cfe` reporting `stream on failed in subdev`;
- a kernel Oops in `csi2_stop_channel`;
- V4L2 processes stuck in D state at `vb2_fop_release`.

A reboot restored the camera. Clean-boot HD then ran normally with no camera
failure signatures. Treat this as a camera mode-transition/restart incident,
not as evidence that HD itself is computationally infeasible.

Avoid unnecessary active stream probes and unnecessary resolution-mode
start/stop cycles. Never use `--camera-preflight-stream-probe-on` on this TEVS
path.

### Recording-path result

The raw-only `--source-record-no-mavros` diagnostic retained 463 genuine
1920x1080 frames over 31.374 s, or 14.725 Hz, while writing about 2.7 GiB.
This is a storage-bandwidth result, not the live-pipeline feasibility metric.
Do not spend effort forcing uncompressed FHD rosbag recording to 30 FPS unless
a later experiment specifically requires it.

### Gate 2 identity rule

Only live-viable source resolutions proceed to the identity-benefit test.
FHD is therefore excluded under the current architecture.

The controlled identity comparison must isolate spatial resolution. VGA is
640x480 (4:3), while HD is 1280x720 (16:9), so independent VGA and HD captures
would confound resolution with framing, field of view and aspect ratio.

Use one native 1280x720 master and compare:

- native 1280x720 appearance imagery;
- a deterministic 640x360 downsample of exactly the same frames.

The two conditions must retain identical timestamps, scene content, field of
view, physical-reference annotations, detector/tracker candidate evidence and
evaluation window. Existing Issue #64 replay provenance and tracker-evidence
digest guards remain authoritative.

The native-HD acquisition bag must contain both `/camera/image_raw` and
`/detections`. Detector evidence is recorded once from the live Hailo path.
`run_deterministic_tracker_replay.py` then generates one frozen ByteTrack
`/tracks` stream while preserving the source image and detection messages.
Both TIM-MARS resolution conditions consume that exact same frozen candidate
stream; only the appearance-image pixels differ.

For native-HD evidence acquisition on the Raspberry Pi, the source bag must
be recorded to RAM-backed `/dev/shm` via `SOURCE_RECORD_ROOT` and copied to
`bags/source_video/` only after the recorder has stopped. The microSD-backed
source path produced repeated approximately 0.6--1.0 s synchronized
image/detection stalls during the 27 August smoke despite approximately 27 Hz
average cadence, so that storage path is not acceptable for final Gate-2
acquisition.

The validated Issue #64 recorder configuration uses the MCAP `fastwrite`
storage preset and a 512 MiB rosbag cache. A 27 August HD validation smoke
showed startup transients during the first approximately 2 s, followed by a
clean steady-state interval. After a predeclared 3.0 s warm-up, the retained
29.933 s interval contained exactly 899 `/camera/image_raw` messages and 899
`/detections` messages at 30.000 Hz, with exact timestamp pairing, a maximum
inter-message gap of 33.924 ms on both topics, and zero gaps greater than or
equal to 67 ms. Final Gate-2 acquisition must therefore discard the first
3.0 s and must pass the same retained-window checks before annotation or
identity evaluation.

The 640x360 condition is an aspect-matched resolution control; it is not
evidence of a native TEVS 640x360 camera mode.

### Predeclared Gate-2 materiality criterion

Freeze this rule before generating or inspecting either comparative TIM-MARS
output.

The v2 evaluator's target-present denominator is:

`correct_target_output_duration_s + wrong_person_output_duration_s +
identity_unresolved_duration_s + lost_or_suppressed_duration_s`.

It excludes target-absent, reference-unavailable, and reference-gap duration.
The primary metrics are those four controller-facing duration buckets plus the
safety subset `target_absent_with_output_duration_s`; localization is
secondary and cosine similarity is not a primary result.

Native HD first must not increase wrong-person duration or absent-with-output
duration beyond the evaluator's `1e-6 s` reconciliation tolerance. Subject to
that safety gate, native HD is materially better if either:

- correct-target fraction increases by at least 5 percentage points, or
  lost-or-suppressed fraction decreases by at least 5 percentage points, using
  the frozen target-present denominator; or
- the human-annotated hard exit/re-entry becomes a correct reacquisition within
  1.0 s without a safety regression.

### Canonical Gate-2 R3 checkpoint — 27 August 2026

The retained master is
`bags/source_video/2026-08-27__16-34-50__source__p064_gate2_hd_master_r3__image_raw_detections`;
its MCAP SHA-256 is
`5580e25f4fef27d3d01c47cfd1e176c56b43449831b62285b6eae2a33aaed34b`.
It contains native 1280x720 images and live Hailo detections at fixed 640x640
inference.

The exact source-header evaluation window is
`[3.000000000, 30.900267443] s`, with absolute origin
`1787844897072285865 ns` and final detection
`1787844927972553308 ns`. There are 837 retained detection timestamps and
837 exact source-image matches at 30 Hz, maximum gap 34.106 ms, and zero gaps
at least 67 ms. The single later image at `30.933606996 s` is a shutdown-edge
surplus and is excluded.

ByteTrack `/tracks` is frozen once with candidate digest
`615ed6abf0083f8cbe86a47257fdc71f4c62c2e16fa314997c57ed34a1a99578`.
Native 1280x720 and deterministic 640x360 appearance bags are prepared with an
identical 923-frame header-timestamp digest. The 837-frame seedless CVAT package
is at `artifacts/reports/p064_gate2_hd_master_r3_cvat/`; archive SHA-256 is
`5ef0a238b52ddc0294db9efe937f36f366809a04dd5391e179271e8d32ce123e`.
Corrected human roles `target` and `phys_d001` cover all 837 frames. The
canonical reference is
`docs/data/physical_target_references/p064_gate2_hd_master_r3.json` with
SHA-256 `0d9f4148f67b610d5cd012db4d3613f6fc559aec63c2ae705adc50595e8db147`;
the selected initial transport ID is 2.

### Corrected Gate-2 controlled R3 result -- 27 August 2026

The audit defects are resolved.

Human frames 93--96 are now encoded as
`present_reference_unavailable`, and the deterministic tracker replay parses
the versioned `;frame=<n>;` source-coordinate contract instead of emitting
numeric `frame_id=0`. The corrected tracker candidate-stream SHA-256 is
`615ed6abf0083f8cbe86a47257fdc71f4c62c2e16fa314997c57ed34a1a99578`.

The promoted canonical physical reference is
`docs/data/physical_target_references/p064_gate2_hd_master_r3.json`, SHA-256
`0d9f4148f67b610d5cd012db4d3613f6fc559aec63c2ae705adc50595e8db147`.
It contains 833 scored target/distractor frames plus four
`present_reference_unavailable` frames.

The corrected native 1280x720 and deterministic 640x360 TIM replays use the
same detector/tracker evidence. Their generated TIM semantic digests differ
(`9178c9985d96ee42ea3af8934ca462a731ea41b562a9dbe03a3fd2f053d86e7c`
versus
`03532a5a3d0e94703212616c2e9e0d222da2ab2ebcca1fa6e4e227a1c39544ad`),
showing that the appearance-pixel condition reaches the algorithm. Their v2
physical-target reports are nevertheless byte-identical:

- correct-target output: 18.600459426 s;
- wrong-person output: 0 s;
- lost/suppressed: 9.100239419 s;
- target-absent duration: 0 s;
- reference-unavailable: 0.133160003 s;
- reference gap: 0.066408595 s;
- total evaluated duration: 27.900267443 s.

The controlled R3 native-HD resolution benefit is therefore **NO MATERIAL
BENEFIT**: 0 percentage-point controller-facing improvement over the exact
640x360 control. Additional repeated HD Stage-B runtime characterization is
not justified by R3.

The earlier zero-difference replay produced with `frame_id=0` and the original
frames-93--96 physical-reference state is retained only as superseded audit
history and must not be cited as the accepted result.

This conclusion remains bounded by target scale. R3 target height is
534.64--561.11 px (median 549.72 px, 76.35% of image height), so it does not
represent the distant/small-person geometry expected from the aircraft.

**Issue #64 is therefore PAUSED, not closed, pending one representative
drone-POV / flight-geometry capture.**

The completed R3 experiment remains frozen on YOLOv6n so its controlled
resolution comparison is not changed retrospectively. The future
representative drone capture uses YOLOv8s + ByteTrack + TIM-MARS, matching the
established June live-system path, while detector inference remains 640x640.

## 1. Preflight

    cd /home/francisco/Desktop/Thesis-Code || exit 1

    export GIT_PAGER=cat
    export PAGER=cat
    export COLCON_LOG_PATH="$PWD/ros2_ws/log/colcon"
    export HAILORT_LOGGER_PATH="$PWD/ros2_ws/log/hailort"

    git status --branch --short
    git rev-parse HEAD
    df -h /
    ls -l /dev/video0 /dev/hailo0
    ls -l /dev/media* 2>/dev/null

Prefer at least 100 GiB free.

## 2. Camera Safety Before Gate 2 Capture

For Gate 2 the native master is HD, not FHD.

Do not run a separate active camera stream probe before the real capture.
Start the required capture mode directly and verify geometry from ROS messages
while that mode is already running. This avoids an unnecessary TEVS
stop/restart cycle.

The required native source geometry is:

- source image: 1280x720;
- Hailo detector input: 640x640;
- positive source timestamps;
- no fallback to 640x480.

If the camera does not produce frames, or the kernel reports `ret=-110`,
`stream on failed`, or an Oops, invalidate the attempt and recover the camera
before collecting evidence.

## 3. Controlled HD Ground Master

Capture the Gate 2 source master only when the target and at least one
physically distinct distractor are available.

Start:

    cd /home/francisco/Desktop/Thesis-Code || exit 1

    export COLCON_LOG_PATH="$PWD/ros2_ws/log/colcon"
    export HAILORT_LOGGER_PATH="$PWD/ros2_ws/log/hailort"
    export RAW_RECORDING_MIN_FREE_GIB=100

    ./tools/start_live_stack.sh --res hd --source-record-no-mavros --tag p064_hd_ground_master

The master should contain a short controlled identity-challenge sequence with:

- target and distractor initially separated;
- approach and crossing;
- partial occlusion if practical;
- target moving farther from the camera;
- target exit;
- a short absence;
- target re-entry.

Keep lighting, clothing and camera placement fixed for the attempt. Prefer
multiple short attempts over one unnecessarily long recording.

Finish with:

    stop

Do not simultaneously record another full-resolution dashboard stream. The
controlled detector/tracker/TIM matrix is generated later from the single
native source master.

## 4. Verify the HD Master

    source /opt/ros/jazzy/setup.bash
    source ros2_ws/install/setup.bash

    LATEST_SOURCE_BAG="$(
        find bags/source_video \
            -mindepth 1 \
            -maxdepth 1 \
            -type d \
            -name '*p064_hd_ground_master*__image_raw' \
            -printf '%T@ %p\n' |
        sort -nr |
        head -n 1 |
        cut -d' ' -f2-
    )"

    echo "$LATEST_SOURCE_BAG"
    du -sh "$LATEST_SOURCE_BAG"
    ros2 bag info "$LATEST_SOURCE_BAG"

Required topic:

- `/camera/image_raw`

Verify the actual native dimensions and positive timestamps using the existing
bag-inspection tooling before deriving any lower-resolution control.

The master is valid for Gate 2 only if every retained source image is genuine
1280x720 imagery. Do not use interpolation or an upsampled source as
high-resolution evidence.

## 5. Representative Drone-POV Capture — Next Action

Do not perform more controlled-R3 or repeated Stage-B work. The only remaining
Issue #64 evidence is one representative small-target drone-POV sequence.

The field command is intentionally one line:

    cd ~/Desktop/Thesis-Code || exit 1
    tools/record_p064_drone_sequence.sh small_target_r1

The helper automatically uses:

- native 1280x720 HD source imagery;
- YOLOv8s Hailo detection with detector inference still fixed at 640x640;
- ByteTrack;
- canonical TIM-MARS;
- `/camera/image_raw` plus `/detections`;
- RAM-backed recording under `/dev/shm`;
- MCAP `fastwrite` plus the existing 512 MiB rosbag cache;
- no MAVROS and no network-mode change;
- logs under `ros2_ws/log/`.

It never requests `--camera-preflight-stream-probe-on`.

At the `live-stack>` prompt, perform one short sequence:

1. target clearly visible with at least one distractor;
2. begin with a larger or medium target;
3. increase realistic drone following distance until the target is genuinely
   small in the image;
4. include a crossing or partial occlusion;
5. include target exit/disappearance;
6. include re-entry while the distractor is visible;
7. continue for a few seconds after reacquisition;
8. type `stop`.

After `stop`, the helper copies the completed RAM-backed bag into
`bags/source_video/` and prints its final path. The RAM copy is deliberately
retained until validation succeeds.

Prefer several short attempts rather than one long recording. The existing
3.0 s startup warm-up rule still applies when selecting the retained
evaluation window.

## Final rule

Current evidence establishes:

- VGA is live-feasible;
- HD is live-feasible;
- FHD fails the current appearance-freshness screen;
- close-range R3 shows no material native-HD identity benefit over the exact
  640x360 control;
- R3 is not representative of small-person airborne geometry.

No general source-resolution recommendation is made until the representative
drone-POV sequence is evaluated.
