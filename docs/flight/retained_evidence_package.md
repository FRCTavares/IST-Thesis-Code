# Retained Flight Evidence

Use this file to check what must be saved after a physical trial.

Flight commands:

    docs/flight/field_day_runbook.md

## Canonical trial directory

Field trials are stored under:

    bags/live_camera/<RUN_ID>__video[__<TAG>]/

Do not delete failed or incomplete runs.

## Required runtime evidence

Every retained field trial should contain:

- finalized structured MCAP + `metadata.yaml`
- `run_metadata.json`
- `flight_metadata.txt`
- `target_authority_events.jsonl`
- `bag_integrity.json`
- `recorder_transport_status.json`
- `evidence_package_status.json`
- `run_logs/archive_manifest.json`
- `run_logs/recorder_finalize_outcome.txt`
- `run_logs/rosbag.log`
- `run_logs/dashboard_bridge.log`
- `run_logs/target_memory_mars.log`
- `run_logs/operator_events.jsonl`
- `run_logs/controller_process_loss.txt` for the mandatory process-loss gate (exact before/after timestamps; optional for other runs)
- separate `visual_<RUN_ID>.mkv`
- `visual_evidence_status.json` (packet PTS, actual gaps, original finalized
  file mtime for new runs)
- postflight `visual_packet_receipt_bounds.json` and
  `visual_packet_receipt_bounds.csv` when physical attribution is attempted;
  these bound ffmpeg receipt conditionally, not camera capture

When the controller runs, also require:

- `/control_ref/cmd_vel`
- `/control_ref/diagnostics`
- `run_logs/control.log`

The controller publishes one diagnostics message for each command with the same timestamp.

## Visual evidence

Field flights use:

- structured non-image MCAP
- separate 640x480 MJPEG visual file

Do not add:

    --record-raw

to normal field flights.

Neither `/camera/image_raw` nor `/camera/dashboard` should be stored in the structured field MCAP. The separate MKV strips the dashboard image's ROS camera-source stamp. Its packet PTS and original file mtime can conditionally bound ffmpeg receipt, but cannot alone prove physical-person identity at a controller command. See `docs/flight/postflight_analysis.md`; unresolved source-time attribution blocks yaw-recovery promotion.

## Retained MAVROS topics

The reduced retained set is:

    /mavros/state
    /mavros/imu/data_raw
    /mavros/rc/in
    /mavros/battery
    /mavros/local_position/pose
    /mavros/local_position/velocity_local
    /mavros/setpoint_raw/target_local
    /mavros/statustext/recv

When MAVROS control mirroring is enabled, also retain:

    /mavros/setpoint_velocity/cmd_vel

The removed duplicate/nonessential streams are intentionally not retained.

## Verify a completed trial

Set the exact bag:

    printf -v BAG "bags/live_camera/%s__video__%s" "$RUN_ID" "$TAG"
    export BAG
    echo "$BAG"

Check the evidence package:

    python3 tools/live/verify_evidence_package.py --bag-dir "$BAG" --run-id "$RUN_ID" --field-record --expect-visual --expect-operator-events

Summarize it:

    python3 tools/live/summarize_field_evidence.py --bag-dir "$BAG"

Generate per-topic cadence/gap evidence:

    python3 tools/live/assess_bag_topics.py "$BAG" --out "$BAG/per_topic_quality.json"

For controller trials:

    python3 tools/analysis/summarize_control_diagnostics.py "$BAG"

## Current recorder acceptance

The current retained-evidence verifier treats nonzero or unavailable rosbag transport-loss evidence as incomplete runtime evidence.

A failed run is still kept.

`assess_bag_topics.py` additionally reports per-topic:

- count
- duration
- average rate
- p50 / p95 / p99 gap
- maximum gap
- timestamp monotonicity
- missing/empty required topics
- command/diagnostics pairing
- controller/MAVROS mirror pairing when present

It does not invent scientific rate or gap thresholds.

## Source-only recording

The H01/H02/H03-style source recorder uses a dedicated matched raw-image QoS contract:

    RELIABLE
    VOLATILE
    KEEP_LAST
    depth 5

This applies only to source recording.

The general live QoS configuration is unchanged.

The final non-held wrapper validation retained approximately:

    /camera/image_raw   30.016 Hz
    /detections         30.000 Hz
    raw max gap         45.2 ms
    transport loss      0 observed

H01/H02/H03 source capture is already complete.

## Controller interpretation

Do not confuse commands with aircraft response.

A published command does not prove the Pixhawk executed it.

For controller flights compare:

    /control_ref/cmd_vel
    /control_ref/diagnostics
    /mavros/setpoint_velocity/cmd_vel
    /mavros/setpoint_raw/target_local
    /mavros/local_position/pose
    /mavros/local_position/velocity_local

Also retain the native Pixhawk DataFlash log.

TIM-MARS `LOCKED` is not physical ground truth. Final physical-person correctness comes from the post-flight physical annotation.

## Pixhawk DataFlash

The native MAVROS `log_transfer` path was validated on the real Pixhawk while
disarmed on 25 September 2026: a 21-entry catalogue was received completely,
explicit log ID 15 was downloaded as 708747 bytes, `LOG_REQUEST_END` succeeded,
and the downloaded and archived copies had the same SHA-256.

The final B-C-B association workflow is fail-closed:

1. before each flight, with MAVROS connected and the aircraft disarmed, verify
   `LOG_DISARMED=0`, `LOG_FILE_DSRMROT=1`, and `LOG_BACKEND_TYPE=1`;
2. capture an explicit pre-flight catalogue;
3. after landing/disarming, capture an explicit post-flight catalogue;
4. compare the catalogues and require exactly one newly observed log ID;
5. download that explicit ID with its reported size after the scientific
   recorder has stopped;
6. archive the resulting `.bin` into the exact retained run.

The FCU catalogue timestamps observed during hardware validation were unusable
(epoch-like or unavailable), so timestamps are not an association key. Never
substitute the highest ID, newest timestamp or filesystem age when catalogue
comparison is ambiguous.

Catalogue and comparison:

    python3 tools/live/retrieve_pixhawk_dataflash.py catalogue --output "$DATAFLASH_DIR/before.json"

    python3 tools/live/retrieve_pixhawk_dataflash.py catalogue --output "$DATAFLASH_DIR/after.json"

    python3 tools/live/retrieve_pixhawk_dataflash.py compare --before "$DATAFLASH_DIR/before.json" --after "$DATAFLASH_DIR/after.json" --output "$DATAFLASH_DIR/association.json"

After the scientific recorder has stopped, restart MAVROS only with the
validated `udp://:14550@`, target-system `10`, target-component `1`
contract. Confirm `/mavros/state` reports connected and disarmed, then
download the explicit ID and size reported by `association.json`:

    python3 tools/live/retrieve_pixhawk_dataflash.py download --log-id "$LOG_ID" --expected-size "$LOG_SIZE" --output "$DATAFLASH"

Then archive it:

    python3 tools/live/archive_pixhawk_dataflash.py --run-id "$RUN_ID" --bag-dir "$BAG" --source-bin "$DATAFLASH" --provenance-dir "$DATAFLASH_DIR"

Then verify a controller trial:

    python3 tools/live/verify_evidence_package.py --bag-dir "$BAG" --run-id "$RUN_ID" --control-trial --field-record --expect-visual --expect-operator-events

## Final scientific completion

A physical trial is not scientifically complete until the required post-flight items also exist, including:

- physical-person annotation when required
- exact Pixhawk DataFlash for retained field/controller trials
- valid finalized runtime evidence

Runtime evidence and physical ground truth are separate.
