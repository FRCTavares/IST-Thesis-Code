# Experiment Replay Tools

This folder contains replay helpers used to reproduce TIM-MARS evaluation runs.

These scripts are not generic utilities. They encode thesis-specific replay
contracts: bag naming, output folders, ROS topics, selected-target publication
modes, and report generation. Prefer using these scripts instead of manually
starting many ROS commands when reproducing TIM-MARS experiments.

## Tool classification

| Tool | Status | Purpose |
| --- | --- | --- |
| `run_one_memory_tim_replay.sh` | Core final workflow | Main memory-only TIM-MARS replay helper over existing tracks and target sources. |
| `run_deterministic_tracker_replay.py` | Core P0.18 workflow | Freezes one tracker and fixed-ID raw target deterministically from recorded image and detection evidence. |
| `run_one_clean_tim_replay.sh` | Core/support workflow | Replays an existing bag with detector/tracker outputs and reruns TIM-MARS. |
| `run_one_detector_tim_replay.sh` | Diagnostic full-pipeline workflow | Reruns detector, tracker, and TIM-MARS from image_raw source bags. |
| `publish_annotated_track_target.py` | Core final workflow | Publishes oracle-style `/target` from annotation CSV intervals and `/tracks`. |
| `publish_selected_track_target.py` | Core final workflow | Publishes `/target` from one fixed tracker ID. |
| `select_largest_track_id.py` | Support helper | Selects the largest usable track ID from a `/tracks` echo dump. |

## Deterministic tracker freezing

Use `run_deterministic_tracker_replay.py` before tracker-pairing
experiments. It processes detections in original rosbag source order,
writes one replacement `/tracks` and `/target` message per detection,
and does not run TIM-MARS during tracker freezing.

The default `largest_first_eligible` mode selects the largest eligible
track once and keeps that tracker ID fixed. If the selected ID disappears,
raw `/target` becomes invalid; the runner does not silently select another
person.

For DeepSORT, recorded image callbacks are forwarded in original source
order to reproduce the live node latest-image contract. Image-age
statistics and stale-image counts are stored in
`tracker_freeze_metadata.json`.

Generated tracker IDs must be validated against tracker-specific
annotations before track-ID correctness evaluation.

Determinism is defined over topic order, bag timestamps, and declared ROS
message fields. It is not defined as byte-for-byte identity of MCAP files or
raw CDR payloads because CDR alignment padding can contain non-semantic bytes.
The runner records a canonical generated-message SHA-256 digest in
`tracker_freeze_metadata.json`.

## Recommended final replay path

Use `run_one_memory_tim_replay.sh` when the goal is to evaluate TIM-MARS as a
selected-target memory layer over already-created tracker outputs. It avoids
changing tracker IDs by rerunning the detector/tracker pipeline.

Typical modes:

- `RAW_TARGET_MODE=source`: reuse `/target` already stored in the input bag.
- `RAW_TARGET_MODE=selected_id`: publish `/target` from a fixed tracker ID.
- `RAW_TARGET_MODE=annotation`: publish `/target` from annotation intervals.

`TIM_MIRROR_RAW_TARGET_SELECTION=false` means TIM-MARS starts from the selected
track ID and then recovers autonomously. This is the preferred mode for testing
the memory layer itself.

`TIM_MIRROR_RAW_TARGET_SELECTION=true` means TIM-MARS follows raw `/target`
reselection updates. Use this only when intentionally testing mirrored raw
selection behavior.

## Full-pipeline replay warning

`run_one_detector_tim_replay.sh` reruns detector and tracker from image data.
This can change tracker IDs compared with existing manual annotations. Use it
for diagnostics or when annotations/evaluation are compatible with regenerated
IDs.

## Controlled target publishers

`publish_annotated_track_target.py` is annotation-driven and follows the
physical target across tracker-ID fragmentation. It is an oracle-style
controlled stream, not a real raw selector baseline.

`publish_selected_track_target.py` publishes a target from one fixed tracker ID.
It is useful for controlled selected-ID replays and simple sanity checks.

## Replay provenance

The memory replay runner records both each effective value and its origin.

Origins distinguish:

- an explicit parent-shell environment value;
- a runner default;
- appearance-topic auto-detection from bag contents;
- a fallback used when no supported image topic is present.

`run_metadata.json` stores the original invocation, a fully resolved command
with effective environment assignments, and the value-source map.
`tim_mars_resolved_runtime.json` stores the same value-source map alongside
runtime overrides and experiment fields.

This prevents an inherited `RAW_TARGET_MODE`, output root, configuration path,
or appearance-topic override from silently changing the meaning of a run.

## Output policy

By default, replay outputs go under thesis-specific replay/report/log folders.
Most scripts allow environment variables to override output roots. Prefer
setting explicit output roots for final runs so reports and bags are easy to
trace back to the experiment.
