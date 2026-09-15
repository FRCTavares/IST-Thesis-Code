# Flight 3 — H02 Close Crossing

FINAL PROSPECTIVE HELD-OUT SOURCE CAPTURE.

Pilot manually flies the aircraft.

People:

- 1 selected target
- at least 1 distractor

## 1. Mandatory pre-capture check

Run:

    cd ~/Desktop/Thesis-Code || exit 1
    export GIT_PAGER=cat
    export PAGER=cat
    set +u

    git status --short

    python3 tools/analysis/validate_tim_evaluation_split.py \
        --verify-hashes

    df -h /
    ls -l /dev/video0 /dev/media0 /dev/hailo0

## 2. Start H02

Only when the real H02 scene and people are ready:

    tools/experiments/record_p027_heldout_sequence.sh h02

## 3. Physical scenario

At the `live-stack>` prompt:

1. target and distractor clearly separated
2. first close crossing
3. sustained overlap or near-overlap
4. separate clearly
5. second close crossing
6. separate clearly again
7. keep recording at least 10 s after final separation

Do not use tracker/TIM output to decide whether the crossing was difficult
enough.

## 4. Stop

Type:

    stop

## 5. Integrity check only

Run:

    source /opt/ros/jazzy/setup.bash

    SOURCE_ROOT="bags/source/held_out/2026-09/h02_crossing"

    LATEST_SOURCE_BAG="$(
        find "$SOURCE_ROOT" -mindepth 1 -maxdepth 1 -type d |
        sort |
        tail -n 1
    )"

    test -n "$LATEST_SOURCE_BAG" || {
        echo "No retained H02 source bag found."
        false
    }

    echo "$LATEST_SOURCE_BAG"
    ros2 bag info "$LATEST_SOURCE_BAG"

Accept based only on:

- `/camera/image_raw` retained
- `/detections` retained
- readable/finalized bag
- two physical close crossings occurred
- sustained overlap/near-overlap occurred
- imagery is usable

Do NOT evaluate TIM-MARS or tracker results.

Physical-v2 annotation target:

    docs/data/physical_target_references/heldout_h02_crossing.json

## Next

Open:

    less docs/flight/15-september/04_H03_OCCLUSION.md
