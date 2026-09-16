# Flight Day

Last reviewed: 2026-09-16

This is the canonical command sheet for the remaining physical flight work.

H01/H02/H03 source captures are already complete and are not part of this procedure.

## Order

1. Connect GCS + Pixhawk.
2. Run field preflight.
3. Run passive MAVROS recording gate.
4. Run controller compute-only ground gate.
5. Run restrained / props-off MAVROS command-path gate.
6. Confirm RC takeover, PreArm/failsafe state and pilot go/no-go.
7. Run baseline closed-loop flight.
8. Only after a clean baseline, run additional trials.

Do not add `--record-raw` to field flights.
Do not use yaw recovery unless explicitly testing the separate candidate condition.

## 1. Connect from Mac

Join:

    ISR Aero.Next GCS

Then:

    ssh francisco@192.168.8.174

On the Pi:

    cd ~/Desktop/Thesis-Code || exit 1
    set +u
    export GIT_PAGER=cat
    export PAGER=cat
    source /opt/ros/jazzy/setup.bash
    source ros2_ws/install/setup.bash

Check repository:

    git --no-pager log -1 --oneline
    git status --short

Do not pull, install or rebuild at the field.

## 2. Enter field network mode

Power/connect Pixhawk Ethernet first.

    sudo tools/host/set_pi_network_mode.sh pixhawk

SSH may briefly disconnect. Reconnect:

    ssh francisco@192.168.8.174

Then:

    cd ~/Desktop/Thesis-Code || exit 1
    set +u
    source /opt/ros/jazzy/setup.bash
    source ros2_ws/install/setup.bash

Check:

    sudo tools/host/set_pi_network_mode.sh status
    nmcli -g GENERAL.CONNECTION,IP4.ADDRESS device show wlan0
    nmcli -g GENERAL.CONNECTION,IP4.ADDRESS device show eth0
    ip route show default
    ip route show default dev eth0
    ping -c 3 -W 1 192.168.144.14
    systemctl is-active tailscaled

Require:

- field mode = `pixhawk`
- Wi-Fi = `ISR Aero.Next GCS`
- Pi Wi-Fi = `192.168.8.174/24`
- Ethernet = `pixhawk-apm`
- Pi Ethernet = `192.168.144.183/24`
- Pixhawk `192.168.144.14` reachable
- no default route on `eth0`
- Tailscale inactive

## 3. Field preflight

    tools/flight/field_preflight_check.sh

Do not continue on failure.

## 4. Passive MAVROS + recorder gate

Aircraft disarmed and stationary.

    tools/flight/field_preflight_check.sh --passive-live-gate

Require the command to pass.

This is the required real-hardware recheck of the reduced MAVROS retained-topic set.

If it fails, keep the evidence and diagnose before flight.

## 5. Manual moving-UAV TIM-MARS trial

Controller disabled. Pilot owns all aircraft motion.

Terminal A:

    export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
    export TAG=dynamic_uav_tim_manual_r1
    echo "$RUN_ID"
    ./tools/start_live_stack.sh --field-record --no-control --tag "$TAG"

Terminal B:

    read -r -p "RUN_ID: " RUN_ID
    export RUN_ID
    python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --condition baseline --scenario dynamic_uav_tim_manual

After selecting the target in Terminal A with `ids` and `target <id>`:

    read -r -p "Visible person description: " PERSON
    read -r -p "Track ID: " TRACK_ID
    python3 tools/live/operator_event.py target_selected --run-id "$RUN_ID" --track-id "$TRACK_ID" --intended-physical-person "$PERSON"

Perform:

- stable hover reference
- lateral translation
- range/scale change
- yaw/viewpoint change
- simultaneous UAV + target motion
- distractor crossing
- brief loss/return if safe
- final stable hover

Before stopping:

    python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID" --end-reason nominal_complete

At Terminal A:

    stop

## 6. Controller compute-only ground gate

Aircraft disarmed and stationary.
No MAVROS command mirror.

Terminal A:

    export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
    export TAG=controller_compute_ground_r1
    echo "$RUN_ID"
    ./tools/start_live_stack.sh --field-record --tag "$TAG"

After selecting the intended target:

Terminal B:

    timeout 20s ros2 topic echo /control_ref/cmd_vel
    timeout 20s ros2 topic echo /control_ref/diagnostics

Require:

- centred target -> near-zero yaw
- target left -> `yaw_z < 0`
- target right -> `yaw_z > 0`
- farther/smaller target -> `vx > 0`
- nearer/larger target -> `vx < 0`
- stale/lost/invalid authority -> zero command

Stop normally after the check.

## 7. Restrained MAVROS command-path gate

Qualified pilot present.
Props removed or vehicle safely restrained.
Do not arm during this check.

Terminal A:

    export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
    export TAG=controller_command_path_ground_r1
    echo "$RUN_ID"
    ./tools/start_live_stack.sh --field-record --control-mavros --tag "$TAG"

Terminal B:

    read -r -p "RUN_ID: " RUN_ID
    export RUN_ID
    python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --condition baseline --scenario controller_command_path_ground

Check:

    timeout 20s ros2 topic echo /control_ref/cmd_vel
    timeout 20s ros2 topic echo /mavros/setpoint_velocity/cmd_vel
    timeout 20s ros2 topic echo /mavros/setpoint_raw/target_local
    timeout 12s ros2 topic echo /mavros/state --once

Require:

- expected command signs
- exact controller -> MAVROS mirror
- stale/lost -> zero
- expected FCU state/mode
- no unexpected arming or mode change

Abort on any unexpected behaviour.

## 8. Pilot safety gate

Before closed-loop flight confirm physically:

- RC/manual takeover works
- expected PreArm state understood
- failsafe behaviour understood
- pilot has immediate abort authority
- physical command direction/sign is correct
- passive recorder gate passed
- restrained command-path gate passed

## 9. Baseline closed-loop flight

Only after every previous gate passes.

Terminal A:

    export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
    export TAG=flight1_baseline
    echo "$RUN_ID"
    ./tools/start_live_stack.sh --field-record --control-mavros --tag "$TAG"

Terminal B:

    read -r -p "RUN_ID: " RUN_ID
    export RUN_ID
    python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --condition baseline --scenario following

After target selection:

    read -r -p "Visible person description: " PERSON
    read -r -p "Track ID: " TRACK_ID
    python3 tools/live/operator_event.py target_selected --run-id "$RUN_ID" --track-id "$TRACK_ID" --intended-physical-person "$PERSON"

Before stopping:

    python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID" --end-reason nominal_complete

At Terminal A:

    stop

## 10. Additional trials

Only after the baseline flight is clean.

### Loss / reacquisition

    export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
    export TAG=flight2_loss_reacquisition
    ./tools/start_live_stack.sh --field-record --control-mavros --tag "$TAG"

### Distractor crossing

    export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
    export TAG=flight3_distractor_crossing
    ./tools/start_live_stack.sh --field-record --control-mavros --tag "$TAG"

### Yaw-recovery candidate

Do not run unless explicitly approved after baseline review.

    export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
    export TAG=flight4_yaw_recovery_candidate
    ./tools/start_live_stack.sh --field-record --control-mavros --control-yaw-recovery --acknowledge-yaw-recovery-candidate --tag "$TAG"

## 11. Stop and verify every retained flight

Before `stop`:

    python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID" --end-reason nominal_complete

Then type:

    stop

Set bag path:

    printf -v BAG "bags/live_camera/%s__video__%s" "$RUN_ID" "$TAG"
    export BAG
    echo "$BAG"

Verify:

    python3 tools/live/verify_evidence_package.py --bag-dir "$BAG" --run-id "$RUN_ID" --field-record --expect-visual --expect-operator-events
    python3 tools/live/summarize_field_evidence.py --bag-dir "$BAG"
    python3 tools/live/assess_bag_topics.py "$BAG" --out "$BAG/per_topic_quality.json"

For controller trials also inspect:

    python3 tools/analysis/summarize_control_diagnostics.py "$BAG"

Keep every failed/incomplete run for diagnosis.

## 12. Pixhawk DataFlash

Retrieve the exact `.bin` belonging to the trial.

    read -r -p "Exact DataFlash .bin path: " DATAFLASH
    python3 tools/live/archive_pixhawk_dataflash.py --run-id "$RUN_ID" --bag-dir "$BAG" --source-bin "$DATAFLASH"

Then verify the controller trial package:

    python3 tools/live/verify_evidence_package.py --bag-dir "$BAG" --run-id "$RUN_ID" --control-trial --field-record --expect-visual --expect-operator-events

## 13. Leave field mode

After Pixhawk work is finished:

    sudo tools/host/set_pi_network_mode.sh unattended

Check:

    sudo tools/host/set_pi_network_mode.sh status
