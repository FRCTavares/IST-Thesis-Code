# Retained Flight Evidence

Use this file to check what must be saved after a physical trial.

Flight commands:

    docs/flight/README.md

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
- separate `visual_<RUN_ID>.mkv`
- `visual_evidence_status.json`

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

Neither `/camera/image_raw` nor `/camera/dashboard` should be stored in the structured field MCAP.

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

Retrieve the exact `.bin` belonging to the trial.

Do not automatically choose the newest file.

Archive it:

    read -r -p "Exact DataFlash .bin path: " DATAFLASH

    python3 tools/live/archive_pixhawk_dataflash.py --run-id "$RUN_ID" --bag-dir "$BAG" --source-bin "$DATAFLASH"

Then verify a controller trial:

    python3 tools/live/verify_evidence_package.py --bag-dir "$BAG" --run-id "$RUN_ID" --control-trial --field-record --expect-visual --expect-operator-events

Real Pixhawk DataFlash retrieval still requires physical validation.

## Final scientific completion

A physical trial is not scientifically complete until the required post-flight items also exist, including:

- physical-person annotation when required
- exact Pixhawk DataFlash for retained field/controller trials
- valid finalized runtime evidence

Runtime evidence and physical ground truth are separate.
