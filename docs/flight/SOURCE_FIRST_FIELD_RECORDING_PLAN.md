# Source-First Field Recording Plan

## Objective

Record three reusable source datasets and one representative live-system run.
The source datasets are the primary experimental evidence: the detector,
ByteTrack, and TIM-MARS will be run over them offline. The live-system run is
retained only as evidence that the complete stack operates onboard with
Pixhawk telemetry.

Do not use `--record-raw` during this session.

## Recording order

1. Source S01: target motion and camera/UAV motion, no distractor.
2. Source S02: appearance-critical crossing with a similar distractor.
3. Source S03: occlusion, full absence, and re-entry.
4. Live V01: one representative full-stack run without raw imagery.

Run every command from the Pi's local terminal. Connecting the Pixhawk over
Ethernet requires the `ISR Aero.Next GCS` router and Pixhawk network mode;
Tailscale must not be used.

## One-time preflight

```bash
cd ~/Desktop/Thesis-Code || exit 1
date -Iseconds
git status --short
git rev-parse --short HEAD
df -h /
ls -l /dev/video0 /dev/media0 /dev/hailo0
sudo ./tools/host/set_pi_network_mode.sh pixhawk
nmcli -t -f ACTIVE,SSID dev wifi | rg '^yes:'
systemctl is-active tailscaled
```

Required results:

- the Git worktree is clean;
- at least 40 GiB is free;
- the camera, media, and Hailo devices exist;
- the active Wi-Fi is `ISR Aero.Next GCS`;
- `tailscaled` reports `inactive`;
- batteries, manual takeover, test area, and spotter are ready;
- the aircraft is never armed automatically.

If any requirement fails, do not start a retained recording.

## Source S01 — motion baseline

Purpose: isolate scale, viewpoint, and camera-motion effects without identity
ambiguity.

- Use one selected person and no distractor.
- Keep the person visible throughout.
- Include lateral walking, approach/retreat, and safe pilot-controlled camera
  yaw/translation.
- Aim for 60–90 seconds after the stream has stabilised.

```bash
./tools/start_live_stack.sh --source-record --tag field_s01_motion
```

When the scenario is complete, type `stop` at the `live-stack>` prompt and wait
for all recorders to finish.

## Source S02 — appearance-critical crossing

Purpose: test identity preservation when geometry becomes ambiguous.

- Use the target and one similarly dressed distractor.
- Start with clear separation.
- Cross near the centre twice, including one close or partial overlap.
- Keep both people visible except for the brief crossing overlap.
- Aim for 60–90 seconds.

```bash
./tools/start_live_stack.sh --source-record --tag field_s02_crossing
```

Type `stop` and wait for clean shutdown.

## Source S03 — occlusion and re-entry

Purpose: test target absence, distractor rejection, and correct reacquisition.

- Begin with the target clearly visible.
- Occlude the target, then remove the target completely for 5–8 seconds.
- Keep the distractor visible while the target is absent.
- Re-enter from the opposite side and remain visible long enough to confirm the
  identity.
- Repeat once if field time and safety allow.
- Aim for 75–120 seconds.

```bash
./tools/start_live_stack.sh --source-record --tag field_s03_occlusion_reentry
```

Type `stop` and wait for clean shutdown.

## Verify every source recording immediately

Run this after each source scenario:

```bash
source /opt/ros/jazzy/setup.bash
LATEST_SOURCE_BAG="$(ls -1dt bags/source_video/* | head -1)"
LATEST_MAVROS_BAG="$(ls -1dt bags/mavros/* | head -1)"
echo "$LATEST_SOURCE_BAG"
ros2 bag info "$LATEST_SOURCE_BAG"
echo "$LATEST_MAVROS_BAG"
ros2 bag info "$LATEST_MAVROS_BAG"
```

Before continuing, confirm:

- `/camera/image_raw` exists and has a non-zero message count;
- bag duration matches the performed scenario;
- the source frame count divided by duration is preferably at least 20 FPS;
- MAVROS contains `/mavros/state` and IMU data;
- no recorder or camera error appeared during shutdown.

If the image rate is poor or a required topic is absent, repeat that scenario
before moving on.

## Live V01 — complete onboard stack

Purpose: retain one representative systems run with detector, ByteTrack,
TIM-MARS, timing, control output, and Pixhawk telemetry. Raw imagery is
deliberately omitted.

Use the appearance-critical crossing with one short partial occlusion. Keep the
run simple enough to operate safely and interpret later.

```bash
./tools/start_live_stack.sh --field-record --tag field_v01_live_validation
```

At the `live-stack>` prompt:

```text
ids
target <TARGET_ID>
status
```

After 60–90 seconds, type:

```text
clear-target
stop
```

Abort immediately on a wrong-target lock. Control mirroring remains disabled;
this recording does not authorise autonomous arming or flight.

## Verify the live recording

```bash
source /opt/ros/jazzy/setup.bash
LATEST_LIVE_BAG="$(ls -1dt bags/live_camera/* | head -1)"
LATEST_MAVROS_BAG="$(ls -1dt bags/mavros/* | head -1)"
echo "$LATEST_LIVE_BAG"
ros2 bag info "$LATEST_LIVE_BAG"
echo "$LATEST_MAVROS_BAG"
ros2 bag info "$LATEST_MAVROS_BAG"
```

Confirm that the live bag contains detections, tracks, `/target`,
`/target_memory_mars`, TIM status, timing, and control topics. Confirm that the
MAVROS bag contains state and IMU telemetry.

## End-of-session record

Fill this table before leaving the field:

| Run | Tag | Source/live bag path | MAVROS bag path | Duration | Image/topic check | Result/notes |
| --- | --- | --- | --- | ---: | --- | --- |
| S01 | `field_s01_motion` |  |  |  |  |  |
| S02 | `field_s02_crossing` |  |  |  |  |  |
| S03 | `field_s03_occlusion_reentry` |  |  |  |  |  |
| V01 | `field_v01_live_validation` |  |  |  |  |  |

Also record the Git commit printed during preflight and any aborted attempts.
Do not rename, edit, or delete retained source bags in the field. Copy and
checksum them after returning; perform detector/tracker/TIM-MARS replay and
annotation work offline.

## Quick failure rules

- No AERONEXT connection or Tailscale still active: stop.
- Less than 40 GiB free: stop.
- Camera, Hailo, raw-image recorder, or MAVROS error: stop and diagnose.
- Wrong-target lock: clear the target, return to manual control, and stop.
- Never power off the Pi until `stop` has completed and bag metadata is written.
