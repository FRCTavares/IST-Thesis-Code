# UAV Dataset Recording Protocol

Date: 2026-05-07  
Purpose: Record reusable drone-view RGB footage for selected-target perception evaluation, detector testing, annotation, and possible fine-tuning.

## 1. Main Principle

Record once, replay many times.

The dataset should allow the same visual footage to be reused with different detector, tracker, and TIM versions.

## 2. Recording Modes

### Analysis mode

Command:

    ./tools/start_live_stack.sh --record-video --bag-tag <tag>

Main purpose:

- dashboard replay
- TIM analysis
- timing analysis
- target-correctness evaluation

Main visual topic:

    /camera/dashboard

### Dataset mode

Command:

    ./tools/start_live_stack.sh --record-dataset --bag-tag <tag>

Main purpose:

- raw drone-view footage
- offline replay
- detector evaluation
- annotation
- possible fine-tuning

Main visual topic:

    /camera/image_raw

## 3. Dataset Topics

Dataset bags record:

- /camera/image_raw
- /camera/fps
- /camera/camera_info
- /detections
- /tracks
- /target
- /target_memory
- /target_memory/status
- /timing
- /timing_tracker
- /timing_target

The source of truth for future reprocessing is:

    /camera/image_raw

The old detections, tracks, target, and target_memory topics are reference metadata from the live run.

## 4. Offline Replay Rule

When testing a new detector, tracker, or TIM version, replay only source camera topics:

    ros2 bag play <dataset_bag> --topics /camera/image_raw /camera/fps

Do not replay old /detections, /tracks, /target, or /target_memory when generating new outputs.

## 5. Naming Convention

Use scenario-based names.

Good examples:

- court_single_person_clean_01
- court_two_people_crossing_01
- court_occlusion_near_01
- court_occlusion_far_01
- court_distractor_same_clothes_01
- court_distance_10m_01
- court_distance_15m_01
- court_distance_20m_01
- court_target_leaves_frame_01
- court_fast_yaw_01
- court_strong_sunlight_01

Avoid names like:

- test1
- bag2
- good_one
- tim_test

## 6. Minimum First Dataset Batch

Record short clips, preferably 30 to 90 seconds each.

| Scenario | Purpose |
|---|---|
| single target walking slowly | clean baseline |
| single target walking fast | motion stress |
| target at 10 m | nominal operating distance |
| target at 15 m | small-person stress |
| target at 20 m | tiny-person stress |
| partial occlusion | uncertainty and reacquisition |
| full short occlusion | LOST and REACQUIRED |
| two people crossing | wrong-target risk |
| distractor near target | ambiguity |
| target leaves frame and returns | safe loss and recovery |
| strong sunlight | exposure stress |
| yaw motion | UAV image-motion stress |

## 7. Metadata to Record Per Clip

For every clip, note:

- scenario
- camera model
- camera resolution
- camera FPS
- approximate target distance
- number of people
- target clothing
- distractor clothing
- lighting and weather
- tracker
- detector
- whether target was selected
- known occlusion or ID-switch moments
- notes

## 8. Dataset Uses

### Detector dataset

Extract frames and annotate person boxes.

Initial class:

    person

### TIM dataset

Use bags plus interval annotations:

    docs/Novelty/annotations/*_target_correctness.csv

TIM labels should separate:

- CORRECT_TARGET
- WRONG_TARGET
- LOST_TARGET
- TARGET_NOT_VISIBLE
- NO_TARGET_SELECTED

## 9. Storage Policy

Raw image bags can be large.

Therefore:

- prefer short controlled clips
- use descriptive tags
- avoid long random recordings
- keep generated bags out of Git
