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

Only if native HD produces a material controller-facing identity improvement
should the stronger repeated Stage-B live characterization be run for the
VGA/HD operating range.

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

## 5. UAV / Flight Capture Is Deferred

Do not perform a high-bandwidth dual full-resolution flight recording merely
because HD passed the Stage-A live smoke.

First complete the controlled Gate 2 identity comparison. If HD does not
materially improve identity robustness, no additional high-resolution flight
capture is justified for Issue #64.

If HD does materially improve identity robustness, define the minimum flight
evidence needed while respecting the existing flight-readiness procedure and
the measured raw-recording bandwidth limits.

## Final rule

The current evidence supports VGA and HD as live-feasible Stage-A candidates
and rejects FHD under the current appearance-image transport architecture.

The next scientific question is not whether HD can run. It is whether native
HD appearance information materially improves identity robustness over the
aspect-matched lower-resolution control.

Do not make a final source-resolution recommendation until that controlled
identity comparison is complete.
