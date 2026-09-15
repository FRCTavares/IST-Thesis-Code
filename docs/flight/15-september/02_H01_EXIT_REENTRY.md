# Flight 2 — H01 Exit / Re-entry

FINAL PROSPECTIVE HELD-OUT SOURCE CAPTURE.

Pilot manually flies the aircraft.

Thesis controller, MAVROS, tracker, TIM-MARS and dashboard are OFF in the
frozen capture helper.

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

Required:

- clean tracked worktree
- split validation passes
- at least 40 GiB free
- camera/media/Hailo devices present

## 2. Start H01

Only when the real H01 scene and people are ready:

    tools/experiments/record_p027_heldout_sequence.sh h01

## 3. Physical scenario

At the `live-stack>` prompt:

1. target clearly visible
2. distractor visible
3. target fully exits the image
4. target remains physically absent about 5–8 s
5. distractor remains visible during at least part of the absence
6. target re-enters
7. keep recording at least 10 s after re-entry

Do not inspect tracker/TIM behaviour.

## 4. Stop

Type:

    stop

## 5. Integrity check only

Run:

    source /opt/ros/jazzy/setup.bash

    SOURCE_ROOT="bags/source/held_out/2026-09/h01_exit_reentry"

    LATEST_SOURCE_BAG="$(
        find "$SOURCE_ROOT" -mindepth 1 -maxdepth 1 -type d |
        sort |
        tail -n 1
    )"

    test -n "$LATEST_SOURCE_BAG" || {
        echo "No retained H01 source bag found."
        false
    }

    echo "$LATEST_SOURCE_BAG"
    ros2 bag info "$LATEST_SOURCE_BAG"

Accept based only on:

- `/camera/image_raw` retained
- `/detections` retained
- readable/finalized bag
- physical H01 scenario actually occurred
- imagery is usable

Do NOT evaluate TIM-MARS or tracker results.

Physical-v2 annotation target:

    docs/data/physical_target_references/heldout_h01_exit_reentry.json

## Next

Open:

    less docs/flight/15-september/03_H02_CROSSING.md
