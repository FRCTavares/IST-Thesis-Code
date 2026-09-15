# Flight 4 — H03 Occlusion / Distractor

FINAL PROSPECTIVE HELD-OUT SOURCE CAPTURE.

Pilot manually flies the aircraft.

People:

- 1 selected target
- at least 1 distractor

H03 is NOT H01. The target remains physically present during full visual
occlusion.

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

## 2. Start H03

Only when the real H03 scene and people are ready:

    tools/experiments/record_p027_heldout_sequence.sh h03

## 3. Physical scenario

At the `live-stack>` prompt:

1. target and distractor clearly visible
2. partially occlude the target
3. fully occlude target while target remains physically in the scene
4. distractor remains visible near target's last visible location
5. reveal the same target
6. keep recording at least 10 s after reveal

## 4. Stop

Type:

    stop

## 5. Integrity check only

Run:

    source /opt/ros/jazzy/setup.bash

    SOURCE_ROOT="bags/source/held_out/2026-09/h03_occlusion_distractor"

    LATEST_SOURCE_BAG="$(
        find "$SOURCE_ROOT" -mindepth 1 -maxdepth 1 -type d |
        sort |
        tail -n 1
    )"

    test -n "$LATEST_SOURCE_BAG" || {
        echo "No retained H03 source bag found."
        false
    }

    echo "$LATEST_SOURCE_BAG"
    ros2 bag info "$LATEST_SOURCE_BAG"

Accept based only on:

- `/camera/image_raw` retained
- `/detections` retained
- readable/finalized bag
- partial and full occlusion occurred
- distractor remained visible near last target location
- imagery is usable

Do NOT evaluate TIM-MARS or tracker results.

Physical-v2 annotation target:

    docs/data/physical_target_references/heldout_h03_occlusion_distractor.json

## Next

Open:

    less docs/flight/15-september/05_DYNAMIC_UAV_TIM_MARS.md
