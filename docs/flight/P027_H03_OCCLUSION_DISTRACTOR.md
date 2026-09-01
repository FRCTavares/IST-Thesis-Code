# H03 — Occlusion with Distractor

## Goal

Test selected-person identity through visual occlusion while another person
remains visible near the last target location.

People required: **1 selected target + at least 1 distractor**.

## Record

    cd ~/Desktop/Thesis-Code || exit 1
    set +u
    tools/experiments/record_p027_heldout_sequence.sh h03

At the `live-stack>` prompt, perform:

1. target and distractor clearly visible;
2. partially occlude the target;
3. fully occlude the target while the target remains physically in the scene;
4. keep the distractor visible near the target's last visible position;
5. reveal the same target again;
6. keep recording at least 10 s after the reveal;
7. type `stop`.

H03 is **not** H01: the target remains physically present during the full
visual occlusion.

## Accept the capture only if

- `/camera/image_raw` and `/detections` were retained;
- the bag is readable and finalized;
- partial and full visual occlusion occurred;
- the distractor remained visible near the last target location;
- imagery is usable.

Acceptance must not depend on tracker or TIM performance.

## Immediate integrity check

    source /opt/ros/jazzy/setup.bash
    SOURCE_ROOT="bags/source/held_out/2026-09/h03_occlusion_distractor"
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

`docs/data/physical_target_references/heldout_h03_occlusion_distractor.json`
