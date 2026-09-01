# H02 — Close Crossing

## Goal

Test selected-person identity during sustained target/distractor geometric
ambiguity.

People required: **1 selected target + at least 1 distractor**.

## Record

    cd ~/Desktop/Thesis-Code || exit 1
    set +u
    tools/experiments/record_p027_heldout_sequence.sh h02

At the `live-stack>` prompt, perform:

1. target and distractor start clearly separated;
2. perform a close crossing;
3. include sustained overlap or near-overlap;
4. separate clearly;
5. perform a second close crossing;
6. separate clearly again;
7. keep recording at least 10 s after the final separation;
8. type `stop`.

Do **not** inspect tracker/TIM output to decide whether the crossing was
"difficult enough".

## Accept the capture only if

- `/camera/image_raw` and `/detections` were retained;
- the bag is readable and finalized;
- both close crossings occurred;
- at least one sustained overlap/near-overlap occurred;
- imagery is usable.

Acceptance must not depend on tracker or TIM performance.

## Immediate integrity check

    source /opt/ros/jazzy/setup.bash
    SOURCE_ROOT="bags/source/held_out/2026-09/h02_crossing"
    LATEST_SOURCE_BAG="$(
        find "$SOURCE_ROOT" -mindepth 1 -maxdepth 1 -type d |
        sort |
        tail -n 1
    )"
    test -n "$LATEST_SOURCE_BAG" || {
        echo "No retained source bag found under $SOURCE_ROOT"
        false
    }
    echo "$LATEST_SOURCE_BAG"
    ros2 bag info "$LATEST_SOURCE_BAG"

Physical-v2 output:

`docs/data/physical_target_references/heldout_h02_crossing.json`
