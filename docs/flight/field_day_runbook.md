# Field-Day Runbook

Use this only as a short backup reference.

Canonical flight-day commands:

    docs/flight/README.md

## Start

From the Mac:

    ssh francisco@192.168.8.174

On the Pi:

    cd ~/Desktop/Thesis-Code || exit 1
    set +u
    export GIT_PAGER=cat
    export PAGER=cat
    source /opt/ros/jazzy/setup.bash
    source ros2_ws/install/setup.bash

Enter field mode:

    sudo tools/host/set_pi_network_mode.sh pixhawk

Check:

    sudo tools/host/set_pi_network_mode.sh status
    ping -c 3 -W 1 192.168.144.14
    systemctl is-active tailscaled

Require Pixhawk reachable and Tailscale inactive.

## Preflight

    tools/flight/field_preflight_check.sh

Passive MAVROS + recorder gate:

    tools/flight/field_preflight_check.sh --passive-live-gate

Do not fly if either fails.

## Manual moving-UAV TIM-MARS

Controller disabled:

    export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
    export TAG=dynamic_uav_tim_manual_r1
    ./tools/start_live_stack.sh --field-record --no-control --tag "$TAG"

Details:

    docs/flight/P050_DYNAMIC_UAV_TIM_TRIAL.md

## Controller compute-only ground test

No MAVROS command mirror:

    export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
    export TAG=controller_compute_ground_r1
    ./tools/start_live_stack.sh --field-record --tag "$TAG"

Inspect:

    timeout 20s ros2 topic echo /control_ref/cmd_vel
    timeout 20s ros2 topic echo /control_ref/diagnostics

## Restrained command-path test

Props removed or aircraft safely restrained.
Do not arm.

    export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
    export TAG=controller_command_path_ground_r1
    ./tools/start_live_stack.sh --field-record --control-mavros --tag "$TAG"

Inspect:

    timeout 20s ros2 topic echo /control_ref/cmd_vel
    timeout 20s ros2 topic echo /mavros/setpoint_velocity/cmd_vel
    timeout 20s ros2 topic echo /mavros/setpoint_raw/target_local
    timeout 12s ros2 topic echo /mavros/state --once

## Baseline closed-loop flight

Only after all physical gates pass:

    export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
    export TAG=flight1_baseline
    ./tools/start_live_stack.sh --field-record --control-mavros --tag "$TAG"

Baseline keeps yaw recovery OFF.

## Additional flights

Loss / reacquisition:

    export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
    export TAG=flight2_loss_reacquisition
    ./tools/start_live_stack.sh --field-record --control-mavros --tag "$TAG"

Distractor crossing:

    export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
    export TAG=flight3_distractor_crossing
    ./tools/start_live_stack.sh --field-record --control-mavros --tag "$TAG"

Yaw-recovery candidate, only if explicitly approved:

    export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
    export TAG=flight4_yaw_recovery_candidate
    ./tools/start_live_stack.sh --field-record --control-mavros --control-yaw-recovery --acknowledge-yaw-recovery-candidate --tag "$TAG"

## Operator events

Start:

    python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --condition baseline --scenario following

After target selection:

    read -r -p "Visible person description: " PERSON
    read -r -p "Track ID: " TRACK_ID
    python3 tools/live/operator_event.py target_selected --run-id "$RUN_ID" --track-id "$TRACK_ID" --intended-physical-person "$PERSON"

Before stopping:

    python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID" --end-reason nominal_complete

Then type:

    stop

## Verify retained evidence

    printf -v BAG "bags/live_camera/%s__video__%s" "$RUN_ID" "$TAG"
    export BAG

    python3 tools/live/verify_evidence_package.py --bag-dir "$BAG" --run-id "$RUN_ID" --field-record --expect-visual --expect-operator-events
    python3 tools/live/summarize_field_evidence.py --bag-dir "$BAG"
    python3 tools/live/assess_bag_topics.py "$BAG" --out "$BAG/per_topic_quality.json"

For controller trials:

    python3 tools/analysis/summarize_control_diagnostics.py "$BAG"

## Pixhawk DataFlash

    read -r -p "Exact DataFlash .bin path: " DATAFLASH
    python3 tools/live/archive_pixhawk_dataflash.py --run-id "$RUN_ID" --bag-dir "$BAG" --source-bin "$DATAFLASH"

## Finish

    sudo tools/host/set_pi_network_mode.sh unattended
    sudo tools/host/set_pi_network_mode.sh status

Do not use `--record-raw` for field flights.

H01/H02/H03 source captures are already complete.
