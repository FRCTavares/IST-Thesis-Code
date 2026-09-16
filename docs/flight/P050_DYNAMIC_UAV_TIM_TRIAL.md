# Manual Moving-UAV TIM-MARS Trial

Non-held-out physical validation.

H01/H02/H03 are separate and must not be used here.

## Purpose

Validate TIM-MARS while the UAV itself moves.

The pilot owns all aircraft motion.

The thesis controller must remain disabled.

Use:

    --field-record --no-control

Do not add:

    --control-mavros
    --record-raw

## Before starting

Complete the field and passive MAVROS gates in:

    docs/flight/README.md

## Terminal A — start

    cd ~/Desktop/Thesis-Code || exit 1
    set +u
    source /opt/ros/jazzy/setup.bash
    source ros2_ws/install/setup.bash

    export RUN_ID="$(date +%Y-%m-%d__%H-%M-%S)"
    export TAG=dynamic_uav_tim_manual_r1
    echo "$RUN_ID"

    ./tools/start_live_stack.sh --field-record --no-control --tag "$TAG"

At the `live-stack>` prompt:

    ids

Then select the intended person:

    target <id>

## Terminal B — record events

    cd ~/Desktop/Thesis-Code || exit 1
    set +u
    source /opt/ros/jazzy/setup.bash
    source ros2_ws/install/setup.bash

    read -r -p "RUN_ID: " RUN_ID
    export RUN_ID

    python3 tools/live/operator_event.py trial_start --run-id "$RUN_ID" --condition baseline --scenario dynamic_uav_tim_manual

After target selection:

    read -r -p "Visible person description: " PERSON
    read -r -p "Track ID: " TRACK_ID

    python3 tools/live/operator_event.py target_selected --run-id "$RUN_ID" --track-id "$TRACK_ID" --intended-physical-person "$PERSON"

## Flight sequence

Aim for roughly 90–120 seconds.

1. Stable hover for about 10 s.
2. Translate laterally left/right.
3. Increase and reduce target distance.
4. Change yaw/viewpoint.
5. UAV and target move simultaneously.
6. Distractor crosses near the target.
7. Brief target loss and return from a changed viewpoint, only if safe.
8. Finish with about 10 s stable hover.

Pilot judgement overrides the sequence.

Do not fly aggressively just to make the test harder.

## Finish

Terminal B:

    python3 tools/live/operator_event.py trial_end --run-id "$RUN_ID" --end-reason nominal_complete

Terminal A:

    stop

## Verify

    printf -v BAG "bags/live_camera/%s__video__%s" "$RUN_ID" "$TAG"
    export BAG
    echo "$BAG"

    python3 tools/live/verify_evidence_package.py --bag-dir "$BAG" --run-id "$RUN_ID" --field-record --expect-visual --expect-operator-events

    python3 tools/live/summarize_field_evidence.py --bag-dir "$BAG"

    python3 tools/live/assess_bag_topics.py "$BAG" --out "$BAG/per_topic_quality.json"

## Keep the trial if

- evidence finalizes correctly;
- UAV motion is clearly more than normal hover correction;
- meaningful lateral background motion exists;
- target scale changes;
- multiple viewpoints are present;
- UAV and target move simultaneously;
- a distractor interaction occurs;
- controller remains disabled.

A loss/return event is useful but may be skipped if unsafe.

## Important

This trial does not change the frozen TIM-MARS algorithm or H01/H02/H03 evaluation contract.
