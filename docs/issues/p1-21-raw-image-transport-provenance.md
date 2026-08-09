# P1.21 Raw-Image Transport, Dataset Recording, and Live-Run Provenance

GitHub Issue: #54
Branch: `issue-54-image-transport-bandwidth`
Baseline: `6231fdc1370b78a55ffeee9a403adbbddf4fb424` (main, unchanged since Issue
#32's last checkpoint)

## Objective

Make raw-image transport, dataset recording, and live-run provenance
explicit, bounded, and reproducible (Issue #54's own objective, quoted
verbatim). This issue does not perform bag deletion/retention (Issue #49's
exclusive scope) and does not modify the parked
`issue-58-lightweight-vs-integrated-tracking` or
`issue-32-runtime-resource-characterization` branches.

## Scope correction versus initial framing

An earlier planning pass for this work assumed a broad multi-architecture
image-transport-optimization study (QoS sweeps, compression, zero-copy,
composition). Reading the live Issue #54 body directly (not a summary)
shows its actual required work is narrower and more concrete: fix three
specific truthfulness/ownership gaps in the existing live launcher, define
a versioned provenance schema, and measure (not optimize) the raw-image
stream's onboard cost for Issue #32. No transport-architecture experiment
matrix is required by the live contract. This record follows the live
contract, not the broader framing.

## Architecture audit (source-verified, not assumed)

### Live image/data graph

The only camera path used in live operation is **integrated-camera**
mode; `--perception-mode single-process|legacy` is a hard error in
`tools/lib/live_cli.sh`. `tools/start_live_stack.sh:478` runs
`perception_camera_node` directly (`ros2 run thesis_bringup
perception_camera_node`); the older two-node path
(`camera_bringup.launch.py` + `camera_capture_node.py` +
`perception_pipeline_node.py` as a separate subscriber) is **not launched
by the live stack at all** -- `camera_bringup.launch.py` is referenced only
defensively in a `pkill` cleanup line (`start_live_stack.sh:197`), i.e. it
is dead code for live operation, not an alternate live path.

`PerceptionCameraNode` (`ros2_ws/src/thesis_bringup/thesis_bringup/
perception/perception_camera_node.py`) extends `PerceptionPipelineNode`
with `create_image_subscription=False`. It opens the camera itself via
OpenCV/V4L2 in a background thread (`_camera_loop`) and calls
`self.on_image(msg)` as a **direct in-process Python method call** to feed
the inherited Hailo detector pipeline -- the perception-critical path
never crosses DDS. Per frame, `_camera_loop` (lines 394-429) also:

- publishes unconditionally to `/camera/image_raw` (line 418) -- no
  parameter gates this; every frame is published regardless of any
  consumer;
- optionally publishes to `/camera/dashboard` (line 419), gated by
  `publish_dashboard_topic` (constructor default `False`, but the live
  launcher always passes `-p publish_dashboard_topic:=true`), throttled to
  `dashboard_fps` (default 10 Hz, live default 30 Hz via `CAMERA_DASHBOARD_
  FPS`).

Both publishers use the same QoS: `BEST_EFFORT`, `KEEP_LAST` depth 1,
`VOLATILE` (freshest-frame, no backlog -- appropriate for a live camera
stream). There is **no** `/camera/fps` publisher anywhere in this file.

Consumer graph (source-verified):

| Consumer | Topic used | Verified by |
|---|---|---|
| Detector/Hailo inference | in-process `on_image()` call | no DDS hop; not a topic at all |
| TIM-MARS appearance | `/camera/dashboard` (`TARGET_MEMORY_MARS_IMAGE_TOPIC` default in `tools/lib/live_defaults.sh:60`) | not `/camera/image_raw` |
| Dashboard bridge / web UI | none -- `dashboard_bridge_node.py` has no `sensor_msgs` import and no image subscription of any kind; video is served directly from `/camera/dashboard` by `web_video_server` (`VIDEO_URL` in `start_live_stack.sh:1023`) | grep-confirmed absence |
| `--record-raw` bag | `/camera/image_raw` (separate bag dir `${VIDEO_BAG_OUT_DIR}__image_raw`) | `start_live_stack.sh:1035-1082` |
| `--record-dataset` bag | **claims** `/camera/image_raw`, actually omits it (`DATASET_BAG_TOPICS`, `start_live_stack.sh:970-979`) | bug, see below |
| `--source-record` bag | `/camera/image_raw` (camera-only capture mode) | `start_live_stack.sh:1127-1153` |

**Conclusion for required-work item 1** ("define when raw images are
required"): under the current architecture, `/camera/image_raw` is not
required by the detector, the tracker, TIM-MARS, or the dashboard/UI --
all of those either never touch the image (detector: in-process call) or
consume the already-published `/camera/dashboard` stream. The **only**
genuine consumers are the three explicit recording paths above, and only
when the operator has asked for raw-image evidence.

### Confirmed bugs (source-verified, matching the issue's audit evidence)

1. **False "disabled" claim.** `start_live_stack.sh:479` logs
   `"full-rate raw image publishing is disabled in live operation"` on
   every run. This is false: nothing in `perception_camera_node.py` or the
   launch command gates `/camera/image_raw`; it publishes at full
   `CAMERA_WIDTH x CAMERA_HEIGHT @ CAMERA_FPS` unconditionally, every run,
   whether or not it is recorded.
2. **`--record-dataset` truthfulness.** `tools/lib/live_usage.sh:101` and
   `tools/lib/live_defaults.sh:75` both describe `--record-dataset` as
   recording "raw camera imagery ... for offline replay", but
   `DATASET_BAG_TOPICS` (`start_live_stack.sh:970-979`) never lists
   `/camera/image_raw`.
3. **`/camera/fps` has no live owner.** Listed in both `VIDEO_BAG_TOPICS`
   (`start_live_stack.sh:874`) and `DATASET_BAG_TOPICS` (`:971`), and
   subscribed to by `dashboard_bridge_node.py:312`
   (`self._fps_sub = self.create_subscription(Float32, self._fps_topic,
   self._on_fps, qos)`, feeding the dashboard's `camera_input_fps` display
   field) -- but `perception_camera_node.py` never publishes it. The only
   node in the repository that does publish `/camera/fps` is
   `video_file_publisher_node.py` (the bag-replay simulator, not part of
   the live camera path), which computes it from a rolling 3-second window
   throttled to a 200ms publish interval. The bag topic lists and the
   dashboard subscriber are copy-paste holdovers from that replay-node
   convention, not evidence of an intentional live design.

### Provenance/metadata audit

`write_video_bag_metadata()` (`start_live_stack.sh:295-329`) writes
`flight_metadata.txt` / `dataset_metadata.txt` / `raw_image_metadata.txt`
via a plain `>` redirect (not atomic) with: run id, bag names/tag, date,
thesis root, ROS domain/mode/backend, tracker type, camera capture/publish
geometry, control/freshness flags, a target-authority log *path* (not its
contents), and a bare topic-name list (no QoS). It is missing, relative to
Issue #54's required schema: git commit/dirty-state, the exact CLI
invocation, model/config SHA-256 hashes, the actual resolved ROS parameter
set, per-topic QoS, and a merged runtime-switch history.

A reusable atomic-write + hashing pattern already exists in
`tools/live/validate_target_authority_ground_run.py` (`write_json_atomic`
at lines 578-585: temp file + `os.replace`; `sha256_file` at 548-554) but
is only used by that isolated ground-check harness, not by the live
launcher's actual recording paths. `dashboard_bridge_node.py` already
maintains a durable, fsync'd JSONL runtime-switch log
(`_record_target_authority_event`, lines 770-816, written to
`target_authority_events.jsonl` per `TARGET_AUTHORITY_EVENT_LOG` in
`start_live_stack.sh:43`) covering target-authority selection/clear
events; this is real switch history but is never merged into the run
metadata file, only pointed at by path.

## Required-work checklist and decisions (frozen before implementation)

1. **Define when raw images are required.** Answered above: recording
   paths only. No perception/TIM/UI consumer needs `/camera/image_raw`.
2. **Make raw-image publication configurable, with documented
   consequences.** Add a `publish_image_raw` bool parameter (default
   `false`) to `PerceptionCameraNode`, gating the existing unconditional
   publish call. Wire it through the live launcher so it is force-enabled
   exactly when a raw-image-consuming recording mode is requested
   (`--record-raw`, `--record-dataset`, `--source-record`) and left off
   otherwise. Fix the false "disabled" log line to reflect the resolved
   state. Document rate/resolution/QoS and the measured bandwidth/CPU cost
   (item 9) in `--help-advanced`.
3. **Keep the frozen flight profile explicit.** Satisfied by (2): the
   default profile (no recording flags) now genuinely disables the
   stream instead of merely claiming to.
4. **Make `--record-dataset` truthful.** Its own default-config comment
   states the intended contract ("records raw camera imagery plus
   perception/TIM telemetry"); fix the implementation to match the
   promise rather than watering the promise down: add `/camera/image_raw`
   to `DATASET_BAG_TOPICS` and force `publish_image_raw=true` whenever
   `ENABLE_DATASET_BAG=1`.
5. **Define the canonical camera-cadence metric.** Implement a real
   `/camera/fps` publisher in `PerceptionCameraNode`, reusing the
   rolling-window pattern already validated in
   `video_file_publisher_node.py`, rather than removing the topic from the
   bag lists and the dashboard (which would silently regress an existing,
   documented dashboard field).
6. **Version a live-run metadata schema.** New schema v1 (git commit +
   dirty flag, exact argv, scenario/date, hardware/software versions,
   model/config SHA-256, resolved ROS parameters, topic/QoS inventory,
   selected target, runtime switch history merged from
   `target_authority_events.jsonl`).
7. **Write metadata atomically and validate before promotion.** Reuse the
   `write_json_atomic`/`sha256_file` pattern from
   `tools/live/validate_target_authority_ground_run.py`; write beside
   every retained bag directory (flight/dataset/raw-image).
8. **Tests.** Launcher topic-list tests, CLI help/behavior consistency
   tests, schema completeness tests, hash-verification tests, `/camera/fps`
   publisher tests.
9. **Measure onboard cost, feed Issue #32.** Analytical payload bandwidth
   vs. measured DDS/`ros2 topic bw`/`hz` traffic vs. CPU/RSS delta with
   `publish_image_raw` on vs. off, at the live default resolution/rate.

## Baseline vs. candidate (frozen before measurement)

- **Baseline:** `perception_camera_node` as currently deployed --
  `/camera/image_raw` published unconditionally at
  `CAMERA_WIDTH=640 x CAMERA_HEIGHT=480 @ CAMERA_FPS=30.0`, `bgr8`
  (3 bytes/px). Analytical payload only (not yet measured DDS traffic):
  `640 x 480 x 3 x 30 = 27,648,000 B/s (~26.37 MiB/s)` -- reported here as
  an explicitly analytical upper bound, not a measured bandwidth claim.
- **Candidate:** identical node, `publish_image_raw=false` by default
  (no recording flags active). No perception, tracking, TIM, or dashboard
  behavior change is possible from this switch, because none of those
  consumers subscribe to `/camera/image_raw` (source-verified above) --
  this is a pure transport-cost change, not a perception-semantics change,
  so Stage 6's correctness-freeze concern does not apply to this specific
  change.
- Measurement matrix (item 9): `publish_image_raw=true` vs. `false`,
  same camera hardware, same duration, same default resolution/FPS,
  reporting analytical payload bandwidth, measured `ros2 topic bw/hz`,
  and CPU/RSS delta for the `perception_camera` process. Kept to this one
  on/off comparison; no QoS/compression/resolution sweep, because the live
  contract does not ask for a transport-optimization study.

## Known platform issue encountered during item 9 measurement

While measuring raw-image transport cost (`tools/experiments/
measure_p054_raw_image_transport_cost.sh`), the TEVS camera's I2C path
wedged (`i2c_designware ...: timeout in disabling adapter`, kernel log),
leaving `perception_camera_node` stuck in an unkillable `D` state. This is
a **pre-existing, previously documented platform condition**
(`docs/debug/LIVE_STACK_CAMERA_RECOVERY.md`, "Kernel hints" /
"`v4l2-ctl` or camera process in `D` state: reboot"), not a fault
introduced by this issue's code changes -- the same failure mode is
documented from incidents predating this branch, with no code-level
causal mechanism connecting `publish_image_raw` toggling to an I2C
adapter timeout. Recovered per that document's Step 1 (`sudo reboot`);
measurement resumed after the documented post-recovery health checks
passed.

The first measurement attempt, before recovery, also carried two
methodology bugs in the measurement script itself (fixed before rerun,
unrelated to the hardware fault): `ros2 topic` calls ran in a shell that
never joined the live stack's `ROS_DOMAIN_ID=42`, and the process-match
pattern assumed `ros2 run`'s original argv survives its exec into the
resolved entry point (it does not). Both were caught before any invalid
numbers were reported as evidence and are corrected in the committed
script.

## Issue #32 integration

Item 9's output (measured bandwidth, CPU/RSS delta, QoS, resolution/FPS,
provenance) is designed to be joined into #32's runtime characterization
by architecture/topic key, closing the "raw-image transport/bandwidth
claim (Issue #54 scope)" gap explicitly listed in #32's claim-boundary
section. This issue does not itself claim #32 completion and does not
modify the parked #32 branch.

## Acceptance criteria mapping

| # | Criterion (verbatim) | Satisfied by |
|---|---|---|
| 1 | Documentation, CLI help, launched publishers, and recorded topics agree | items 2, 4, 5 |
| 2 | No promoted dataset is missing the image stream it claims to contain | item 4 |
| 3 | Every retained live run passes a machine-readable provenance validator | items 6, 7 |
| 4 | Raw-image bandwidth and compute cost are measured on the Pi | item 9 |
| 5 | Focused tests, build, and `git diff --check` pass | item 8 + validation stage |
