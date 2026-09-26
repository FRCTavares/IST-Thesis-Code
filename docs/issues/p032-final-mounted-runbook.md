# #32 final mounted run

Run **only after #50 records the retained controller policy**.
VGA 640x480. Aircraft remains disarmed and stationary for the complete run.
No arming or flight is part of this characterization.

First pass all physical/network gates in:

    docs/flight/field_day_runbook.md

## 1. Start

    cd ~/Desktop/Thesis-Code || exit 1
    set +u
    export GIT_PAGER=cat PAGER=cat GH_PAGER=cat
    source /opt/ros/jazzy/setup.bash
    source ros2_ws/install/setup.bash
    export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
    export TAG=p032_final_mounted_vga

If #50 retained baseline:

    ./tools/start_live_stack.sh --res vga --field-record --control-mavros --tag "$TAG"

If #50 retained yaw recovery:

    ./tools/start_live_stack.sh --res vga --field-record --control-mavros --control-yaw-recovery --acknowledge-yaw-recovery-candidate --tag "$TAG"

Never select candidate unless #50 promoted it.

## 2. Event + target

Terminal B:

    read -r -p "RUN_ID from A: " RUN_ID; export RUN_ID
    export TAG=p032_final_mounted_vga
    read -r -p "Condition baseline/candidate: " CONDITION
    python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --trial-id "$TAG" --condition "$CONDITION" --scenario p032_final_mounted_vga

For candidate add `--recovery-enabled` to that command.

Select intended person in A (`ids`, `target <id>`), then:

    read -r -p "Physical person: " PERSON
    read -r -p "Track ID: " TRACK_ID
    python3 tools/live/operator_event.py target_selected --run-id "$RUN_ID" --trial-id "$TAG" --track-id "$TRACK_ID" --intended-physical-person "$PERSON"

Keep the intended person present and exercise representative in-frame motion so
the retained controller path is active rather than a stale/zero-only workload.
The aircraft itself remains disarmed and stationary.

## 3. Measure

    RUN_DIR="ros2_ws/log/live_stack/$RUN_ID"
    python3 tools/experiments/measure_p032_live_resources.py --run-dir "$RUN_DIR" --architecture-groups detector,tracker,tim,controller --duration-s 1260 --warm-up-s 60

Require the full 60 s warm-up + 1200 s active interval. Do not shorten the
measurement by selecting only active bursts or by removing stalls afterward.

## 4. Finish

    python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID" --trial-id "$TAG" --end-reason nominal_complete
    python3 tools/live/operator_event.py trial_verdict --run-id "$RUN_ID" --trial-id "$TAG" --verdict accepted --integrity-reason "measurement complete; final checks pending"

`stop` in Terminal A.

Then:

    tools/flight/verify_field_run.sh "$RUN_ID" "$TAG" --control-trial --disarmed-runtime-characterization
    printf -v BAG "bags/live_camera/%s__video__%s" "$RUN_ID" "$TAG"
    python3 tools/analysis/analyse_bag_timing.py "$BAG" --out "$BAG/timing_full_horizon.md" --figdir "$BAG/timing_figures" --gap-ms 1260000
    python3 tools/analysis/analyse_tim_reid_workload.py "$BAG" --json-out "$BAG/tim_reid_workload.json" --markdown-out "$BAG/tim_reid_workload.md" --require-live-wall-time
    cp -a "$RUN_DIR/p032_resources" "$BAG/p032_resources"

The explicit `--disarmed-runtime-characterization` scope is fail-closed. It is
accepted only for `p032_final_mounted_vga` when the retained MCAP contains
`/mavros/state`; every retained state sample whose bag timestamp falls
inside the exact `trial_start` to `trial_end` interval must report
`connected=true` and `armed=false`. Startup and shutdown state transitions
outside that interval remain retained but do not invalidate this experiment.

For this disarmed runtime/resource experiment, physical-v2 target annotation
and native Pixhawk DataFlash are **not applicable** to the #32 claim. Do not
attach an older or unrelated `.bin` to make the evidence package look complete.
The retained MAVROS state/telemetry, controller diagnostics, MCAP, visual,
operator events, provenance and resource measurements remain required.

## 5. Accept

Require:

- complete 20 min active interval;
- no retained `/mavros/state` sample inside the trial interval reports
  disconnected or armed;
- validated-target rate >=10 Hz;
- p95 camera-to-validated-target <=200 ms;
- no unexplained resource-root loss;
- zero unacceptable recorder transport loss;
- investigate any throttling;
- Hailo utilization and electrical power are reported unavailable if no direct,
  reproducible measurement exists.

Keep failed runs.

Fill:

    docs/results/live/templates/p032_final_runtime.md
