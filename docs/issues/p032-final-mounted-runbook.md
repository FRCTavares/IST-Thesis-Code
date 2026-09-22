# #32 final mounted run — execute only after #50

This is the ready-to-run resource checklist, subordinate to the frozen
contract in `p1-14-final-runtime-characterization.md`. **Do not execute until
#50 has recorded baseline or yaw recovery as the retained controller policy.**
VGA 640x480 is fixed by closed #64. The final run is stationary, disarmed,
props off or safely restrained, with the final mounted Pi/camera/Hailo/Pixhawk,
qualified supervision, and the same field-record/UI load as the final stack.
No tracker, model, TIM-MARS or controller retuning.

## Branch selection and startup

Complete the physical network, FCU, passive recorder and controller gates in
`docs/flight/README.md` first. Confirm free disk, clean commit, exact model
and configuration hashes, no root `log/` or `hailort.log`. In Pi Terminal A:

```bash
cd ~/Desktop/Thesis-Code || exit 1
set +u
export GIT_PAGER=cat PAGER=cat GH_PAGER=cat
export THESIS_ROOT="$PWD"
export COLCON_LOG_PATH="$THESIS_ROOT/ros2_ws/log/colcon"
export HAILORT_LOGGER_PATH="$THESIS_ROOT/ros2_ws/log/hailort"
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
git rev-parse HEAD
git status --short
df -h . /dev/shm
export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
export TAG=p032_final_mounted_vga
```

Select exactly **one** command, matching the written #50 retain decision.

**A — baseline hover/zero retained:**

```bash
./tools/start_live_stack.sh --res vga --field-record --control-mavros --tag "$TAG"
```

**B — bounded yaw recovery retained:**

```bash
./tools/start_live_stack.sh --res vga --field-record --control-mavros --control-yaw-recovery --acknowledge-yaw-recovery-candidate --tag "$TAG"
```

The aircraft remains disarmed. Do not use `--record-raw`. The candidate branch
remains prohibited unless #50's physical retain criteria actually passed.
Keep a safely positioned, visible intended person moving in the camera view
during the active window so that selected-target, controller and appearance
cadence can be characterized. No aircraft motion is permitted.

In Terminal B, enter the same repository and ROS environment without creating
a second RUN_ID. Copy the exact RUN_ID displayed in Terminal A:

```bash
cd ~/Desktop/Thesis-Code || exit 1
set +u
export GIT_PAGER=cat PAGER=cat GH_PAGER=cat
source /opt/ros/jazzy/setup.bash
source ros2_ws/install/setup.bash
export TAG=p032_final_mounted_vga
read -r -p "Exact RUN_ID from Terminal A: " RUN_ID; export RUN_ID
```

Start the retained event log **before** target selection. Run only the command
matching the #50 policy:

**A — baseline:**

```bash
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --trial-id "$TAG" --condition baseline --scenario p032_final_mounted_vga
```

**B — retained yaw recovery:**

```bash
python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --trial-id "$TAG" --condition candidate --scenario p032_final_mounted_vga --recovery-enabled
```

Select the intended physical person in Terminal A with `ids` then
`target <id>`; record its actual integer track ID and a specific physical
description in Terminal B:

```bash
python3 tools/live/operator_event.py target_selected --run-id "$RUN_ID" --track-id "$TRACK_ID" --intended-physical-person "$PERSON"
```

Confirm the selected-person transaction in the run log. A target absent for
the whole active window cannot support a validated-target cadence claim;
retain that run and repeat only under the frozen protocol if needed.

## Bounded measurement

In Terminal B, wait for healthy detector, tracker, TIM-MARS, controller,
MAVROS and recorder publication. Attach to the exact run, never `latest`:

```bash
RUN_DIR="ros2_ws/log/live_stack/$RUN_ID"
test -f "$RUN_DIR/pids.txt" || { echo "Exact PID file missing" >&2; exit 1; }
cat "$RUN_DIR/pids.txt"
python3 tools/experiments/measure_p032_live_resources.py \
  --run-dir "$RUN_DIR" \
  --architecture-groups detector,tracker,tim,controller \
  --duration-s 1260 --warm-up-s 60
```

The sampler starts after first samples, bounds a nominal 21 min interval, and
reports the 60 s warm-up separately from the 20 min active population. Let it
finish; keep the stack running meanwhile. Require `p032_resources/coverage.json`
and `analysis.json` integrity to pass with every requested PID root present
through the full interval. No active-only statistic may hide a stall.

Before stopping, record the actual outcome while the event log remains live:

```bash
python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID" --end-reason nominal_complete
python3 tools/live/operator_event.py trial_verdict --run-id "$RUN_ID" --verdict accepted --integrity-reason "field observations recorded; package and resource coverage pending post-run verification"
```

If interrupted or unsafe, record the actual abort/end reason and a rejected
verdict using the Friday sheet. Stop the stack normally in Terminal A and wait
for finalization. The final scientific acceptance is decided only after all
post-run integrity and coverage checks.

## Exact post-run checks

Back in Terminal B, with the exact RUN_ID and TAG:

```bash
printf -v BAG "bags/live_camera/%s__video__%s" "$RUN_ID" "$TAG"
test -d "$BAG" || { echo "Exact bag missing" >&2; exit 1; }
python3 tools/live/verify_evidence_package.py --bag-dir "$BAG" --run-id "$RUN_ID" --control-trial --field-record --expect-visual --expect-operator-events
python3 tools/live/summarize_field_evidence.py --bag-dir "$BAG"
python3 tools/live/assess_bag_topics.py "$BAG" --out "$BAG/per_topic_quality.json"
python3 tools/analysis/summarize_control_diagnostics.py "$BAG" --out "$BAG/control_diagnostics_summary.json"
python3 tools/analysis/analyse_bag_timing.py "$BAG" --out "$BAG/timing_full_horizon.md" --figdir "$BAG/timing_figures" --gap-ms 1260000
python3 tools/analysis/analyse_tim_reid_workload.py "$BAG" --json-out "$BAG/tim_reid_workload.json" --markdown-out "$BAG/tim_reid_workload.md" --require-live-wall-time
test -f "$RUN_DIR/p032_resources/analysis.json" || { echo "Resource analysis missing" >&2; exit 1; }
test ! -e "$BAG/p032_resources" || { echo "Existing resource copy; inspect before retry" >&2; exit 1; }
cp -a "$RUN_DIR/p032_resources" "$BAG/p032_resources"
sha256sum "$BAG"/*.mcap "$BAG/run_metadata.json" "$BAG/p032_resources/analysis.json" "$BAG/p032_resources/provenance.json" | tee "$BAG/p032_input_hashes.sha256"
```

Archive the **human-selected exact** Pixhawk DataFlash, even though this is a
disarmed mounted run, then rerun the package verifier. Never choose latest:

```bash
read -r -p "Exact DataFlash .bin path: " DATAFLASH
python3 tools/live/archive_pixhawk_dataflash.py --run-id "$RUN_ID" --bag-dir "$BAG" --source-bin "$DATAFLASH"
python3 tools/live/verify_evidence_package.py --bag-dir "$BAG" --run-id "$RUN_ID" --control-trial --field-record --expect-visual --expect-operator-events
```

Retain exact run metadata, resolved controller parameters, invocation, Git SHA,
model/config hashes, topic/QoS inventory, package/transport/visual status,
resource provenance and raw samples, complete timing, per-topic cadence/gaps,
controller diagnostics, and native DataFlash. The status-topic workload
analyzer supplies selective appearance calls, requested/returned embeddings,
cache hits/misses/expiry, invocation rate and backend time. The resource
analyzer supplies process-tree CPU/RSS, memory, temperature, ARM clock and
throttling. Report Hailo contention or electrical power only if directly
measured; otherwise write `unavailable`. Recorder/UI overhead is outside the
core CPU/RSS sum and must be described separately from that sum; the retained
field profile documents its active load. Carry forward the existing measured
#54 raw-image transport cost without enabling raw recording here.

Use `docs/results/live/templates/p032_final_runtime.md` for the thesis table.
Require complete interval integrity, final validated-target rate >=10 Hz
(>=15 Hz desired), p95 camera-to-validated-target <=200 ms and investigation
of nonzero throttling or resource-root loss. Keep any failed run; do not treat
tooling tests or an earlier #64 run as final #32 evidence.
