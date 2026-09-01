# H01 — Exit and Re-entry

## Goal

Test a genuine selected-person disappearance and later re-entry.

People required: **1 selected target + at least 1 distractor**.

## Record

    cd ~/Desktop/Thesis-Code || exit 1
    set +u
    tools/experiments/record_p027_heldout_sequence.sh h01

At the `live-stack>` prompt, perform:

1. target clearly visible at the start;
2. distractor visible;
3. target fully exits the image;
4. target remains physically absent for about 5–8 s;
5. distractor remains visible during at least part of the absence;
6. target re-enters;
7. keep recording at least 10 s after re-entry;
8. type `stop`.

Do **not** inspect whether a tracker ID actually changed.

## Accept the capture only if

- `/camera/image_raw` and `/detections` were retained;
- the bag is readable and finalized;
- the physical exit/absence/re-entry happened as specified;
- imagery is usable.

Acceptance must not depend on tracker or TIM performance.

## Immediate integrity check

    source /opt/ros/jazzy/setup.bash
    SOURCE_ROOT="bags/source/held_out/2026-09/h01_exit_reentry"
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

`docs/data/physical_target_references/heldout_h01_exit_reentry.json`
