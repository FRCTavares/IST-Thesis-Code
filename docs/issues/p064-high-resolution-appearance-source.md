# Issue #64 — High-Resolution Appearance-Source Evaluation

This document places the current live resolution qualification before the
historical experiments and frozen R3 evidence. The later FHD preparation
sections are retained for provenance, not active deployment selection.

## Current VGA-versus-HD live qualification — predeclared 18 September 2026

The verified live default remains **VGA 640x480**. FHD failed the Stage-A live
appearance-freshness check (480/937 stale skips, 51.2%) and is outside the
current deployable envelope. The 15 September FHD master, conversion tooling
and prepared CVAT package below remain development/archive evidence. No FHD
human-geometry gate or comparative TIM-MARS outcome has been inspected; the
older FHD plan below is retained as history and is not the active deployment
study. Detector Hailo inference remains fixed at 640x640 for both live modes.

This qualification asks whether HD 1280x720 is sufficiently live-feasible to
merit a representative small/distant identity-benefit test. It is development
evidence, not the final sustained #32 characterization and not a default
resolution change. Use the normal integrated live launcher with the same
YOLOv8s HEF, frozen tracker/TIM parameters, dashboard/recording profile and
camera FPS in both modes. Keep MAVROS mirroring and aircraft control off. The
camera's native capture geometry and `/camera/dashboard` geometry must be
verified for each run; do not infer source geometry from 640x640 inference.
Avoid unnecessary camera mode transitions and the active preflight stream probe
because of the documented TEVS restart incident.

### Frozen minimal live matrix

| Configuration | VGA | HD | Purpose |
| --- | --- | --- | --- |
| ByteTrack + TIM-MARS | two runs | two runs | Primary selected-person live path, appearance freshness and validated-target timing. |
| ByteTrack raw | one run | one run | Tracker-only reference and source-resolution cost without TIM-MARS. |
| DeepSORT raw | one run | one run | Integrated appearance-tracker reference retained in #58. |

Run the four VGA cells as one resolution block, then the four HD cells after a
clean camera transition. Within each block the fixed order is TIM run 1, raw
ByteTrack, raw DeepSORT, TIM run 2. Each run has a 60 s warm-up followed by 180 s
of active observation; retain all startup and active traces, and calculate
warm-up and steady-state populations separately. A failed launch remains a
recorded attempt and cannot be silently replaced. Repeat only for a declared
camera fault or invalid collection, retaining the failed attempt and reason.
The two TIM runs test short-run repeatability; samples within one run are not
independent repetitions. Keep scene, lighting and people as comparable as
practical, but do not use this live matrix to infer identity benefit from
unmatched human motion.

Use `--res vga` or `--res hd` with `--record-structured-visual --no-control`
and the default dashboard publisher load. Set `--tracker bytetrack --target-memory mars` for TIM cells, `--tracker bytetrack --target-memory off`
for raw ByteTrack and `--tracker deepsort --target-memory off` for raw DeepSORT.
Do not pass `--control-mavros`, `--field-record`, `--record-raw`, or the active
camera preflight stream probe. In a second shell, resolve the launched run's
`ros2_ws/log/live_stack/latest` symlink to its exact run directory and attach:

    python3 tools/experiments/measure_p032_live_resources.py \
      --run-dir ros2_ws/log/live_stack/<run-id> \
      --architecture-groups detector,tracker,tim \
      --duration-s 240 --warm-up-s 60

Use `detector,tracker` for raw tracker cells. Start the attachment after the
stack reaches healthy publication; stop the stack normally after the helper
finishes and the structured recorder finalizes. If visual recording itself
changes the measured behavior, retain that observation as the configured
qualification load rather than changing only one resolution's recorder profile.

Capture native structured timing/status and process-tree CPU/RSS plus hardware
health with explicit bounds. The controller is absent under `--no-control`.
Keep the same recorder and dashboard load across cells and record their enabled
states. Retain exact invocation, model/config hashes,
OS/Hailo versions, source geometry, run IDs, raw samples, sampler integrity and
thermal flags. The resource totals exclude dashboard and recorders. Do not
interpret this short qualification as final mounted-system resource evidence.

For every cell report detector and tracker publication rates, p50/p95/p99 and
maximum interarrival gaps, detector `e2e_det_ms` p95, tracker `track_ms` p95,
CPU/RSS and temperature/ARM-frequency/throttle traces, memory availability,
root losses, and camera/ROS errors. For TIM cells additionally report validated
`/target_memory_mars` output rate, `e2e_validated_target_ms` p95, TIM processing
p95, appearance-image age p50/p95/p99, stale-image skip numerator/denominator,
backend calls/valid embeddings and status coverage. Use host-monotonic causal
Timing-v4 deltas for latency; source-header time is metadata and must not be
subtracted from host-monotonic time without verified clock comparability. Raw
tracker cells have tracker-stage timing only: no TIM-MARS validated-authority
latency or controller-authority acceptance metric is assigned to them.

HD passes this **runtime gate** only if every valid HD cell has its required
roots and complete measurement intervals, no sustained camera/ROS failure, no
unexplained thermal throttling, detector and tracker effective rates at least
15 Hz, and no steady-state publication gap of 0.5 s or longer. Both HD TIM
runs must also reach at least 15 Hz validated-target output, p95
`e2e_validated_target_ms` at most 200 ms, and stale appearance-image skips at
most 10% of eligible attempts. This 10% development ceiling separates the
previous HD 5.3% observation from the FHD 51.2% failure; the full age
distribution remains reported against the configured 250 ms image-age limit.
Investigate any memory decline, root loss, or service error before accepting a
run. Report matched VGA results and resource increases even if HD passes; do
not invent a CPU/RSS threshold or hide long gaps in active-only averages.

If HD fails, retain VGA and report the failure. If HD passes, **do not promote
it from runtime evidence alone**. The existing R3 target occupied about 550 px
of a 720 px image and showed no material native-HD benefit. Promotion still
requires a representative native-HD small/distant sequence and a matched
appearance-pixel comparison under the existing physical-target safety and
materiality contract, with common detector/tracker evidence. A positive
identity result must not alter completed H01–H03 evaluation or frozen models.
Until that evidence and a documented retain/reject decision, VGA remains the
live default and #64 stays open.

## 0. Experimental Status and Decision Logic

The Issue #64 question is:

> What is the lowest source resolution that materially improves identity
> robustness while the complete onboard pipeline still satisfies the
> real-time system requirements?

For the historical R3 controlled experiment below, the detector was not a
resolution variable: YOLOv6n Hailo inference remained fixed at 640x640. That
statement applies to the frozen R3 evidence only. The active 18 September
VGA-versus-HD live qualification above uses the current YOLOv8s Hailo path while
still keeping detector inference fixed at 640x640. Source resolution changes the
camera/source imagery available to tracking and appearance processing, not the
detector input geometry.

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

## 5. Archived FHD representative-study preparation — acquired 15 September 2026

The required field acquisition has now been performed as a direct native-FHD
development master rather than as a second ROS source bag:

    bags/development/fhd_appearance/20260915T152745Z_fhd_drone_pov_15sep_1920x1080_mjpeg.mkv

Retained capture properties:

- source: `/dev/video0`, native 1920x1080 UYVY422;
- retained encoding: MJPEG;
- decoded frames: 2208;
- decoded duration: 85.809 s;
- effective decoded cadence: approximately 25.73 fps;
- file size: 1,004,727,994 bytes;
- full decode-to-null validation: PASS;
- SHA-256:
  `17c6e654903274afcc2b7e2479554bec99ae8fd08a516c14c290049bc81eee4e`.

The master has an independently stored Mac copy whose SHA-256 matches the Pi
source byte-for-byte. The original master must remain unchanged.

This capture is development-only appearance-resolution evidence. It is separate
from the Stage-7 H01/H02/H03 640x480 prospective held-out set and must not be
used to change the frozen TIM-MARS algorithm, tracker, thresholds, models or
held-out evaluation semantics.

### Archived matched-comparison plan — superseded before outcome inspection

The acquisition gate was closed, but this FHD comparison was superseded before
human-geometry or comparative TIM-MARS outcome inspection because FHD had
already failed the live appearance-freshness gate and is no longer an active
deployment candidate. The following steps are retained only as provenance of the
predeclared plan; they are **not instructions to execute this study now**.

The superseded plan was:

1. review the retained frames and quantify whether the target reaches the
   intended representative small-person drone-POV geometry;
2. preserve the FHD master unchanged;
3. derive the lower-resolution HD control from the exact same retained source
   frames rather than recording another scene;
4. keep detector inference fixed at 640x640;
5. use the existing matched appearance-resolution methodology so only source
   appearance density changes;
6. annotate/evaluate the matched conditions under the existing physical-target
   contract;
7. report both identity-performance and runtime/appearance-freshness effects.

### Predeclared representative-geometry gate — 17 September 2026

This gate is frozen before inspecting any comparative TIM-MARS outcome and
before using detector/tracker output to judge target scale.

Target-scale authority is the human-reviewed physical target annotation, not a
detector or tracker box. The primary measure is target bounding-box height in
native 1920x1080 source-image pixels; normalised height
(`bbox_height / 1080`) is retained alongside it.

The repository's retained VisDrone UAV evidence covers human-ground-truth target
heights from 66 to 132 px and is already described as partial small/distant
coverage. Separately, the external-sequence selector labels a sequence
`small_target` when its median target height is below 60 px. The latter is a
stronger diagnostic category, not a universal minimum-detectable-size threshold
and not a mandatory gate for this experiment.

For this bounded Issue #64 study, the 15 September capture is considered to
reach representative small/distant drone-POV geometry only if the
human-reviewed physical target has a bounding-box height of at most 132 px for
at least five consecutive target-visible annotated frames. The five-frame
persistence requirement prevents a single annotation or motion outlier from
satisfying the gate and reuses the existing repository convention for a
meaningful consecutive observation run.

The geometry report must be produced before comparative TIM-MARS evaluation and
must include, over human-reviewed target-visible frames:

- minimum, p10, median, p90 and maximum target height in native FHD pixels;
- the corresponding normalised-height statistics;
- frame count and fraction at or below 132 px;
- longest consecutive run at or below 132 px;
- frame count and fraction below 60 px, with the median-<60-px
  `small_target` diagnostic reported separately.

This is an Issue #64 representativeness gate, not a claimed universal detector,
tracker or ReID operating threshold. If no five-frame run at or below 132 px
exists, stop the matched-resolution study and report the capture as
non-representative rather than inspecting comparative TIM-MARS performance.

### Frozen matched-resolution decision contract

Subject to the geometry gate passing, the remaining comparison is frozen as:

- native appearance condition: 1920x1080 FHD;
- lower-resolution condition: deterministic 1280x720 complete-FOV downsample
  from the exact same retained source frames using `INTER_AREA`;
- detector: YOLOv8s Hailo inference, fixed at 640x640, generated once;
- tracker: ByteTrack, frozen once from that single detector stream;
- identical source timestamps, scene, FOV, physical target, evaluation window,
  detector evidence, tracker candidates, canonical TIM-MARS configuration and
  appearance model across both conditions;
- only the source pixels available to the TIM-MARS appearance crop differ.

The existing Gate-2 materiality rule remains authoritative. The FHD condition
must first not increase wrong-person duration or target-absent-with-output
duration beyond the evaluator's `1e-6 s` reconciliation tolerance. Subject to
that safety gate, FHD is materially better only if either the correct-target
fraction increases by at least 5 percentage points, the lost/suppressed
fraction decreases by at least 5 percentage points, or a human-annotated hard
exit/re-entry becomes a correct reacquisition within 1.0 s without a safety
regression.

No result from this development-only study may modify the completed H01/H02/H03
prospective evidence, frozen TIM-MARS thresholds, detector model, tracker
configuration or evaluation semantics.

If the target never becomes sufficiently small under the frozen gate above, the
capture must be reported as non-representative rather than used to force a
resolution conclusion.

### Human-reference preparation checkpoint — 17 September 2026

The exact-FHD annotation package has been prepared from the frozen 2208-frame
source bag at:

    artifacts/reports/p064_fhd_drone_pov_15sep_cvat/

It contains all 2208 source frames at native 1920x1080 geometry in the ordered
lossless-PNG CVAT archive, with exact source timestamps preserved by the frame
manifest. The allowed physical roles are `target`, `phys_d001` and
`phys_d002`, corresponding to the three-person 15 September session coding
`sep15_p001`, `sep15_p002` and `sep15_p003`; semantic required-role intervals
remain for human review.

Package identities:

- CVAT image archive SHA-256: `7865c8d8a2e5db33ab9552035edc6e7cce60750d6b2369a2c1c0898fd4e2ab53`;
- frame manifest SHA-256: `a0c522c7a61c5743433639293cefa8d0692875ffdee906b58ef46f660868be80`;
- preparation-config SHA-256: `33e08aa81e358948153fda000c1bdd8976913ee6e2ef55a1d26a7e60f266287e`.

The generated conversion configuration remains deliberately
`human_review_required` with an empty `semantic_intervals` list. No geometry
gate outcome, detector result, tracker result or comparative TIM-MARS result
has been inspected yet.

## Current decision rule

The 15 September FHD master and prepared CVAT materials remain archived
preparation, with no claimed geometry or TIM-MARS outcome. FHD is excluded from
active deployment consideration by its measured live freshness failure. The
active VGA-versus-HD live qualification above precedes any further native-HD
small/distant identity test. VGA remains the verified default until both the
runtime gate and representative identity-benefit gate support promotion.
