# #32 final mounted run

Run **only after #50 records the retained controller policy**.
VGA 640x480. Aircraft disarmed, stationary, props off/restrained.

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
    read -r -p "Condition baseline/candidate: " CONDITION
    python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --trial-id "$TAG" --condition "$CONDITION" --scenario p032_final_mounted_vga

For candidate add `--recovery-enabled` to that command.

Select intended person in A (`ids`, `target <id>`), then:

    read -r -p "Physical person: " PERSON
    read -r -p "Track ID: " TRACK_ID
    python3 tools/live/operator_event.py target_selected --run-id "$RUN_ID" --track-id "$TRACK_ID" --intended-physical-person "$PERSON"

## 3. Measure

    RUN_DIR="ros2_ws/log/live_stack/$RUN_ID"
    python3 tools/experiments/measure_p032_live_resources.py --run-dir "$RUN_DIR" --architecture-groups detector,tracker,tim,controller --duration-s 1260 --warm-up-s 60

Require full 60 s warm-up + 1200 s active interval.

## 4. Finish

    python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID" --end-reason nominal_complete
    python3 tools/live/operator_event.py trial_verdict --run-id "$RUN_ID" --verdict accepted --integrity-reason "measurement complete; final checks pending"

`stop` in Terminal A.

    tools/flight/verify_field_run.sh "$RUN_ID" "$TAG" --control-trial
    printf -v BAG "bags/live_camera/%s__video__%s" "$RUN_ID" "$TAG"
    python3 tools/analysis/analyse_bag_timing.py "$BAG" --out "$BAG/timing_full_horizon.md" --figdir "$BAG/timing_figures" --gap-ms 1260000
    python3 tools/analysis/analyse_tim_reid_workload.py "$BAG" --json-out "$BAG/tim_reid_workload.json" --markdown-out "$BAG/tim_reid_workload.md" --require-live-wall-time
    cp -a "$RUN_DIR/p032_resources" "$BAG/p032_resources"

Archive exact DataFlash:

    read -r -p "Exact DataFlash .bin: " DATAFLASH
    python3 tools/live/archive_pixhawk_dataflash.py --run-id "$RUN_ID" --bag-dir "$BAG" --source-bin "$DATAFLASH"
    python3 tools/live/verify_evidence_package.py --bag-dir "$BAG" --run-id "$RUN_ID" --control-trial --field-record --expect-visual --expect-operator-events

## 5. Accept

Require:

- complete 20 min active interval;
- validated-target rate ≥10 Hz;
- p95 camera→validated-target ≤200 ms;
- no unexplained resource-root loss;
- investigate any throttling.

Keep failed runs.

Fill:

    docs/results/live/templates/p032_final_runtime.md
