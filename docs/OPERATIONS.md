# Operations

Last reviewed: 2026-10-13

## Purpose

Day-to-day operation of the live stack on the Raspberry Pi: start, select a
target, record, stop, and check what was recorded. Field/flight days have their
own procedure in [flight/field_day_runbook.md](flight/field_day_runbook.md).

## Start the stack

```bash
cd ~/Desktop/Thesis-Code
./tools/start_live_stack.sh --res vga
```

The launcher starts, in order: camera + Hailo perception, tracker, dashboard
bridge, TIM-MARS, `control_ref_node`, and (unless disabled) the web video server.
All runtime logs go in the runtime subfolder of `ros2_ws/log`.

Useful options (full list: `--help`, `--help-advanced`):

| Option | Effect |
| --- | --- |
| `--res vga\|hd\|fhd` or `--resolution WxH` | Camera capture resolution (default 640x480; the retained operating point is VGA) |
| `--tracker sort\|ocsort\|bytetrack\|deepsort` | Tracker backend (default `bytetrack`) |
| `--target-memory off\|mars` | TIM-MARS on (default) or off |
| `--no-control` | Do not start `control_ref_node` |
| `--control-mavros` | Mirror the controller output to MAVROS |
| `--no-dashboard`, `--dashboard-bind ADDR` | Dashboard bridge control; non-loopback bind requires `DASHBOARD_CONTROL_TOKEN` |
| `--tag NAME` | Tag appended to the recording folder name |

## Select a target

At the `live-stack>` prompt:

```text
ids            # list current tracker IDs
target <id>    # select the person TIM-MARS should follow
stop           # clean shutdown (finalises recordings)
```

Selection can also come from the dashboard. Only `/target_memory_mars` carries
control authority; the raw `/target` topic is telemetry.

## Record

| Flag | Records | Use for |
| --- | --- | --- |
| `--field-record` | Structured MCAP + separate MJPEG visual + managed MAVROS telemetry | The approved aircraft evidence profile |
| `--record-structured-visual` | Same as above without MAVROS | Ground development; **not** an approved aircraft launch command |
| `--source-record` | `/camera/image_raw` + MAVROS, tracker/TIM-MARS off | Capturing source footage for later replay |
| `--source-record-no-mavros` | `/camera/image_raw` + `/detections` | Source footage without field network changes |
| `--record-raw` | Adds a separate synchronized raw-image bag | Diagnostics; not part of the aircraft profile |
| `--record-mavros` | Lightweight MAVROS state/control topics | Low-level switch used by the profiles |

Recordings land in `bags/live_camera/<RUN_ID>__video[__<TAG>]/`. Source-first
recordings go to `bags/source_video/` and dataset-style ones to `bags/datasets/`.
The launcher refuses to record when free space is below
`RECORDING_MIN_FREE_GIB` (see `tools/lib/live_defaults.sh`). Keep failed and
aborted runs; never delete a bag to "tidy up" before checking it
([bags/README.md](../bags/README.md)).

## Check a recording

```bash
tools/flight/verify_field_run.sh "$RUN_ID" "$TAG"      # full retained-run checks
python3 tools/live/summarize_field_evidence.py --bag-dir "$BAG"
python3 tools/live/assess_bag_topics.py "$BAG" --out "$BAG/per_topic_quality.json"
python3 tools/analysis/summarize_control_diagnostics.py "$BAG"
```

What a complete package contains is listed in
[flight/retained_evidence_package.md](flight/retained_evidence_package.md).

## Latency and resource metrics

Timing schema v4 (`/timing`, `/timing_tracker`, `/timing_target`) is defined in
[RUNTIME_METRICS.md](RUNTIME_METRICS.md). Live checks:

```bash
python3 tools/analysis/check_live_timing_invariants.py
python3 tools/analysis/analyse_bag_timing.py <bag_dir>      # writes under analysis_out/timing/
```

`tools/experiments/sample_hardware_health.py` and `sample_process_groups.py`
sample CPU/memory/thermal state of a running stack.

## Replay a recording

`ros2_ws/src/thesis_bringup/launch/eval_replay.launch.py` plays a bag and runs
the tracker and dashboard bridge against it. Use it to inspect behaviour on a
saved run without the camera or Hailo.

## Network modes (Pi host)

```bash
sudo tools/host/set_pi_network_mode.sh status
sudo tools/host/set_pi_network_mode.sh pixhawk       # field: Pixhawk on eth0, Tailscale off
sudo tools/host/set_pi_network_mode.sh unattended    # bench: Tailscale/SSH reachable
```

Details and recovery: [debug/UNATTENDED_PI_OPERATION.md](debug/UNATTENDED_PI_OPERATION.md).

## Troubleshooting

| Symptom | Go to |
| --- | --- |
| `/detections` has no publisher, `hailortcli scan` empty, `HAILO_OUT_OF_PHYSICAL_DEVICES` | [debug/HAILO_RECOVERY.md](debug/HAILO_RECOVERY.md) |
| No `/camera/dashboard`, `/dev/video0` missing, `v4l2-ctl` hangs | [debug/LIVE_STACK_CAMERA_RECOVERY.md](debug/LIVE_STACK_CAMERA_RECOVERY.md) |
| Pi unreachable, wrong network mode | [debug/UNATTENDED_PI_OPERATION.md](debug/UNATTENDED_PI_OPERATION.md) |
| Dashboard access / token | [live/dashboard_trust_boundary.md](live/dashboard_trust_boundary.md) |

Prefer narrow diagnosis and targeted recovery over broad process or device
resets, and check the runtime logs under `ros2_ws/log` first.
