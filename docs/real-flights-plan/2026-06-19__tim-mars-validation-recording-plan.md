# 2026-06-19 TIM-MARS validation recording plan

Purpose: record a compact validation set that directly answers the supervisor feedback from 2026-06-15.

The goal is not to collect many random bags. The goal is to collect a small set of controlled, annotatable sequences that show when TIM-MARS helps, when raw tracking is already enough, and when TIM-MARS must be conservative.

## 1. Supervisor feedback this plan addresses

Meysam's main concerns:

1. The paper is under-validated.
2. The experiments use too few sequences and too few people.
3. The current results are mixed: TIM-MARS helps ByteTrack, improves OCSORT, but can hurt DeepSORT-MARS.
4. The paper must clearly justify why TIM-MARS is needed if a stronger tracker already gives low wrong-target output.
5. Parameters must be reported for reproducibility.
6. The qualitative figure must be clearer.
7. The raw target selector must be explained better.
8. Ablations would help: geometry only, ID only, appearance only, full TIM-MARS.

This recording plan targets items 1, 2, 3, 4, 6, and 7 directly. Parameter and ablation tables can be produced after the data is collected.

## 2. Core framing

Do not frame TIM-MARS as universally better than every detector or tracker.

Use this framing:

TIM-MARS is a control-facing selected-target memory layer. It is useful when the detector-tracker stack becomes unstable after occlusion, target loss, re-entry, or multi-person ambiguity. Stronger detector-tracker combinations may reduce the need for aggressive memory correction, but they do not remove the need for explicit target selection, loss handling, and control-safe output.

Important rule:

Wrong selected target is worse than LOST.

Therefore the evaluation must separate:

- correct selected-target output
- wrong selected-target output
- lost or suppressed output
- no target selected yet

## 3. Tomorrow's minimum useful dataset

Record at least 4 sequences.

If there is more time, record 6.

### Required sequences

| Seq | Scenario | People | Duration | Purpose |
|---|---:|---:|---:|---|
| seq01 | clean two-person tracking | 2 | 45 to 60 s | show normal behaviour and no unnecessary TIM instability |
| seq02 | two-person hard re-entry | 2 | 60 to 90 s | direct replacement for current hard re-entry sequence |
| seq03 | three-person ambiguity | 3 | 60 to 90 s | answer the "more than two people" criticism |
| seq04 | person-to-person occlusion | 2 or 3 | 45 to 75 s | test occlusion without full FOV exit |

### Optional sequences

| Seq | Scenario | People | Duration | Purpose |
|---|---:|---:|---:|---|
| seq05 | similar clothing ambiguity | 2 or 3 | 60 to 90 s | stress MARS appearance and appearance ablation |
| seq06 | raw-stable strong-detector case | 2 | 45 to 60 s | show TIM should not degrade a stable raw track |

## 4. Visual setup rules

Use clothing that makes annotation easy.

Recommended:

- target: black shirt
- distractor 1: white shirt
- distractor 2: red, blue, or checkered shirt

Avoid:

- all people wearing dark clothes
- target too small
- camera pointed into sun
- unplanned bystanders
- people leaving the frame before the scenario is complete
- overlap that is impossible to annotate visually

Target size guideline:

- person height should usually be at least 15 to 25 percent of image height
- keep full body visible when possible

## 5. Safety and flight scope

Priority is perception validation, not aggressive autonomous flight.

Preferred order:

1. Ground/static drone or fixed camera, perception-only.
2. Hand-carried or slowly moved drone/camera, perception-only.
3. Low-risk flight only if already safe and supervised.

For tomorrow, default to:

- no control output
- no autonomous following
- record perception data first

Use flight only if it does not compromise safety or data quality.

## 6. Technical recording principle

The most important topic is:

/camera/image_raw

Reason: raw images allow offline reruns with different detector HEFs on the same sequence.

Also record live outputs when available:

/camera/fps
/detections
/tracks
/target
/target_memory_mars
/target_memory_mars/status
/timing
/timing_tracker
/timing_target

If MAVROS/IMU is already connected and stable, also record MAVROS topics. Do not add MAVROS if it risks breaking the perception recording.

## 7. Pre-recording checklist

Run before leaving for the field:

    cd ~/Desktop/Thesis-Code || exit 1

    git status --short
    df -h .

    source /opt/ros/jazzy/setup.bash
    source ros2_ws/install/setup.bash

    ros2 pkg executables thesis_bringup | sort | rg "perception|camera|pipeline|target_memory"
    ros2 pkg executables thesis_tracker | sort

Check detector HEFs:

    cd ~/Desktop/Thesis-Code || exit 1

    for m in yolov6n yolov8s yolov11n; do
      test -f "models/hef/${m}.hef" && echo "[ok] $m" || echo "[missing] $m"
    done

Check current live stack help includes detector flags:

    cd ~/Desktop/Thesis-Code || exit 1

    ./tools/start_live_stack.sh --help | rg "detector-model|detector-hef-path|tracker|record"

## 8. Live recording command template

Default recording mode for tomorrow:

- detector: yolov8s
- tracker: ByteTrack
- TIM-MARS enabled
- control disabled
- video/raw bag recording enabled

Use one bag per sequence.

Example for seq01:

    cd ~/Desktop/Thesis-Code || exit 1

    ./tools/start_live_stack.sh \
      --detector-model yolov8s \
      --tracker bytetrack \
      --mem mars \
      --no-control \
      --record-video \
      --bag-tag 2026-06-19__seq01__clean_two_person__yolov8s_bytetrack_tim_mars

Inside the live prompt:

    ids
    target <BLACK_SHIRT_TARGET_ID>
    status

At the end:

    stop

Repeat with a different bag tag for each sequence.

## 9. Sequence-specific recording commands

### seq01, clean two-person tracking

Goal: baseline where raw and TIM should both behave well.

    cd ~/Desktop/Thesis-Code || exit 1

    ./tools/start_live_stack.sh \
      --detector-model yolov8s \
      --tracker bytetrack \
      --mem mars \
      --no-control \
      --record-video \
      --bag-tag 2026-06-19__seq01__clean_two_person__yolov8s_bytetrack_tim_mars

Scenario:

- target selected manually at the start
- two people visible
- no crossing
- no hard occlusion
- simple walking or standing

Useful if:

- target is visible and annotatable for at least 45 s
- raw tracker is stable
- TIM does not introduce instability

Reject and redo if:

- wrong target selected at start
- target too small
- people are indistinguishable

### seq02, two-person hard re-entry

Goal: direct hard re-entry validation.

    cd ~/Desktop/Thesis-Code || exit 1

    ./tools/start_live_stack.sh \
      --detector-model yolov8s \
      --tracker bytetrack \
      --mem mars \
      --no-control \
      --record-video \
      --bag-tag 2026-06-19__seq02__two_person_hard_reentry__yolov8s_bytetrack_tim_mars

Scenario:

- target selected at start
- distractor remains visible
- target leaves FOV or becomes fully occluded
- target re-enters
- keep the re-entry inside the frame

Useful if:

- raw tracker has a chance to switch, lose, or become ambiguous
- black-shirt target remains visually identifiable
- full event is inside the frame

### seq03, three-person ambiguity

Goal: answer "more than two people".

    cd ~/Desktop/Thesis-Code || exit 1

    ./tools/start_live_stack.sh \
      --detector-model yolov8s \
      --tracker bytetrack \
      --mem mars \
      --no-control \
      --record-video \
      --bag-tag 2026-06-19__seq03__three_person_ambiguity__yolov8s_bytetrack_tim_mars

Scenario:

- target selected at start
- two distractors visible
- one distractor crosses near the target
- another distractor remains in the scene
- include at least one ambiguous moment

Useful if:

- all three people are visible for a meaningful part of the sequence
- the target is annotatable throughout the difficult interval
- there is a real ambiguity event

### seq04, person-to-person occlusion

Goal: isolate occlusion from FOV exit.

    cd ~/Desktop/Thesis-Code || exit 1

    ./tools/start_live_stack.sh \
      --detector-model yolov8s \
      --tracker bytetrack \
      --mem mars \
      --no-control \
      --record-video \
      --bag-tag 2026-06-19__seq04__person_occlusion__yolov8s_bytetrack_tim_mars

Scenario:

- target remains inside camera view
- distractor walks in front of target
- target becomes partially or fully occluded
- target reappears in similar area

Useful if:

- occlusion is clear but not impossible to annotate
- target reappears visibly
- raw tracker may switch or drop

### seq05, similar clothing ambiguity

Only record if there is enough time.

    cd ~/Desktop/Thesis-Code || exit 1

    ./tools/start_live_stack.sh \
      --detector-model yolov8s \
      --tracker bytetrack \
      --mem mars \
      --no-control \
      --record-video \
      --bag-tag 2026-06-19__seq05__similar_clothing_ambiguity__yolov8s_bytetrack_tim_mars

Scenario:

- two or three people with similar clothing colours
- target selected at start
- crossing, occlusion, or re-entry

Useful for appearance ablation.

### seq06, raw-stable strong-detector case

Only record if there is enough time.

    cd ~/Desktop/Thesis-Code || exit 1

    ./tools/start_live_stack.sh \
      --detector-model yolov8s \
      --tracker bytetrack \
      --mem mars \
      --no-control \
      --record-video \
      --bag-tag 2026-06-19__seq06__raw_stable_case__yolov8s_bytetrack_tim_mars

Scenario:

- clear lighting
- target remains visible
- no hard occlusion
- moderate motion

Purpose:

- show that TIM should preserve stable raw tracking
- useful for conservative/pass-through argument

## 10. What to say or write before each sequence

Record or write these notes:

- sequence number
- scenario name
- target description
- distractor descriptions
- detector
- tracker
- TIM mode
- people count
- lighting/weather
- whether drone was static, carried, or flying

Example:

Seq03, three-person ambiguity, target is black shirt, distractors are white shirt and red shirt, outdoor court, detector yolov8s, tracker ByteTrack, TIM-MARS enabled, static drone.

## 11. Immediate post-recording checks

After each bag, check topics and counts.

    cd ~/Desktop/Thesis-Code || exit 1
    source /opt/ros/jazzy/setup.bash
    source ros2_ws/install/setup.bash

    LATEST="$(find bags/live_camera -maxdepth 1 -type d | sort | tail -1)"

    echo "LATEST=$LATEST"
    ros2 bag info "$LATEST"

Minimum acceptable:

- duration at least 45 s
- /camera/image_raw exists
- /detections exists
- /tracks exists
- /target exists
- /target_memory_mars exists if TIM-MARS was running

If /camera/image_raw is missing, the bag is not useful for detector reruns.

## 12. End-of-day bag inventory

Run after all recordings:

    cd ~/Desktop/Thesis-Code || exit 1
    source /opt/ros/jazzy/setup.bash
    source ros2_ws/install/setup.bash

    echo "=== 2026-06-19 bags ==="
    find bags/live_camera -maxdepth 1 -type d -name '2026-06-19*' | sort

    echo
    echo "=== bag topic summaries ==="
    for b in $(find bags/live_camera -maxdepth 1 -type d -name '2026-06-19*' | sort); do
      echo
      echo "===== $b ====="
      ros2 bag info "$b" | rg "Duration|Messages|Topic: /camera/image_raw|Topic: /detections|Topic: /tracks|Topic: /target |Topic: /target_memory_mars|Topic: /timing"
    done

    echo
    df -h .

## 13. Offline detector replay plan after recording

Use only the best raw image bags.

Main detector replay set:

- yolov6n, baseline
- yolov8s, efficient strong candidate
- yolov11n, strong detector candidate

Main tracker:

- ByteTrack

Methods:

- raw ByteTrack
- ByteTrack + TIM-MARS

This gives 6 replay runs per sequence.

For 4 sequences, that is 24 runs. That is already enough.

Do not explode the matrix until the first 4 sequences are validated.

## 14. Offline replay command template

Use the detector replay script created on 2026-06-18.

Example:

    cd ~/Desktop/Thesis-Code || exit 1
    source /opt/ros/jazzy/setup.bash
    source ros2_ws/install/setup.bash

    RAW_BAG="bags/live_camera/2026-06-19__seq02__two_person_hard_reentry__yolov8s_bytetrack_tim_mars"

    RECORDER_STOP_TIMEOUT=120 tools/experiments/run_one_detector_tim_replay.sh \
      "$RAW_BAG" \
      yolov8s \
      1 \
      bytetrack \
      mars \
      0.5 \
      120

Use the correct selected target ID after inspecting the beginning of the sequence. Do not blindly use "largest" unless it is visually confirmed.

## 15. Offline replay matrix template

Run this only after confirming the bag is useful and target ID is known.

    cd ~/Desktop/Thesis-Code || exit 1
    source /opt/ros/jazzy/setup.bash
    source ros2_ws/install/setup.bash

    RAW_BAG="bags/live_camera/REPLACE_WITH_BAG"
    TARGET_ID="REPLACE_WITH_TARGET_ID"
    TRACKER="bytetrack"
    RATE="0.5"
    WAIT="120"

    for model in yolov6n yolov8s yolov11n; do
      for tim in off mars; do
        RECORDER_STOP_TIMEOUT=120 tools/experiments/run_one_detector_tim_replay.sh \
          "$RAW_BAG" \
          "$model" \
          "$TARGET_ID" \
          "$TRACKER" \
          "$tim" \
          "$RATE" \
          "$WAIT"
      done
    done

## 16. Coverage check for replay bags

After offline replay, check header-time coverage.

    cd ~/Desktop/Thesis-Code || exit 1
    source /opt/ros/jazzy/setup.bash
    source ros2_ws/install/setup.bash

    echo "=== replay bag counts ==="
    for b in $(find bags/detector_eval_matrix -maxdepth 1 -type d -name '*tracker_bytetrack*' | sort); do
      echo
      echo "===== $b ====="
      ros2 bag info "$b" | rg "Duration|Messages|Topic: /camera/image_raw|Topic: /detections|Topic: /tracks|Topic: /target |Topic: /target_memory_mars"
    done

## 17. Annotation plan

For each accepted sequence, create one annotation CSV under:

docs/data/annotations/june_hard_sequences/

Use the existing template:

tools/analysis/templates/target_correctness_annotations_template.csv

Each interval must identify:

- target visible or not
- correct selected target track ID
- distractor IDs
- event type
- notes

Important:

Existing annotations from older detector runs are not automatically valid for new detector runs because tracker IDs can change.

## 18. Qualitative figure plan

For the paper, replace the confusing Figure 3 with a full-width comparison.

Recommended layout:

- row 1: Raw ByteTrack
- row 2: ByteTrack + TIM-MARS
- columns: same timestamps across the sequence

Box meaning:

- green: correct selected target
- red: wrong selected target
- grey or yellow: LOST or no output
- blue: non-selected tracks

Also generate a timeline plot for the full sequence:

- green: correct
- red: wrong
- grey: lost
- white/black: no selected target

## 19. Parameter table to add later

Report actual TIM-MARS values:

- IoU weight
- distance weight
- scale weight
- confidence weight
- same-ID bonus
- locked accept threshold
- lost/reacquisition accept threshold
- ambiguity margin
- same-ID threshold relief
- appearance enabled
- appearance weight
- appearance min similarity
- appearance ambiguous-only setting
- appearance conservative gate settings
- rank-aware reacquisition enabled
- confirm frames
- missing TTL frames
- cooldown frames
- selected target initialisation policy
- raw selector policy

## 20. Raw selector explanation to write later

Clarify:

- initial person is selected manually through dashboard/API
- after selection, raw selector follows the selected tracker ID while available
- if selected ID disappears, document whether it outputs LOST/0 or selects a candidate
- state whether the policy is the same for all trackers
- distinguish raw selector from TIM-MARS
- explain that TIM-MARS sits above tracker output and publishes a control-facing selected target

## 21. Acceptance rules for tomorrow

A sequence is useful if:

- target selected correctly at the start
- target is visually annotatable
- event is fully inside frame
- duration at least 45 s
- /camera/image_raw recorded
- at least two people visible for challenge sequences
- three-person sequence has three visible candidates

Reject and redo if:

- target is too small
- target leaves frame before the planned event
- wrong target is selected at start
- people are visually indistinguishable
- sun/glare ruins boxes
- /camera/image_raw is missing

## 22. Do not track generated outputs

Do not commit:

- bags/
- reports/
- generated videos
- ros2_ws/log/
- log/
- build/
- install/

Commit only source and documentation changes unless explicitly needed.
