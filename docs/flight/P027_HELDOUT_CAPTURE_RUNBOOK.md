# Issue #27 — H01–H03 Held-Out Capture

## What this is

H01–H03 are final **source-data captures**, not autonomous aircraft flights.

During these captures:

- source image: `640x480` at nominal 30 FPS;
- detector: frozen direct-Hailo YOLOv8s, 640x640 inference;
- recorded topics: `/camera/image_raw` + `/detections`;
- tracker: OFF;
- TIM-MARS: OFF;
- controller: OFF;
- MAVROS: OFF.

Use only the dedicated helper. It internally uses
`--source-record-no-mavros`; do not substitute the older `--source-record`
field workflow.

## Before each capture

    cd ~/Desktop/Thesis-Code || exit 1
    set +u
    export GIT_PAGER=cat
    export PAGER=cat
    git status --short
    python3 tools/analysis/validate_tim_evaluation_split.py --verify-hashes
    df -h /
    ls -l /dev/video0 /dev/media0 /dev/hailo0

Required:

- clean tracked worktree;
- active split validation passes;
- at least 40 GiB free;
- camera/media/Hailo devices exist.

## Execution plan

All physical H01–H03 work is queued in:

`docs/flight/P027_HELDOUT_EXECUTION_PLAN.md`

Do not start a real held-out capture unless working in the appropriate physical
recording environment.

## Scenario sheets

Run exactly one scenario at a time:

- [H01 — exit/re-entry](P027_H01_EXIT_REENTRY.md)
- [H02 — crossing](P027_H02_CROSSING.md)
- [H03 — occlusion/distractor](P027_H03_OCCLUSION_DISTRACTOR.md)

## After each capture

Allowed:

- `ros2 bag info`;
- topic counts, duration and timestamps;
- source-image quality;
- confirming that the planned **physical** scenario occurred;
- physical-v2 annotation;
- anonymous participant/outfit coding.

Forbidden until all three sequences are released:

- tracker/TIM correctness inspection;
- candidate-score inspection;
- architecture comparison;
- changing thresholds, tracker settings, models or identity policy.

A capture may be repeated for corruption, missing topics, unusable imagery, or
failure to perform the physical scenario. Never repeat it because an algorithm
later performs badly.

## Annotation outputs

Use:

- `docs/data/physical_target_references/heldout_h01_exit_reentry.json`
- `docs/data/physical_target_references/heldout_h02_crossing.json`
- `docs/data/physical_target_references/heldout_h03_occlusion_distractor.json`

Record anonymous participant/outfit codes and exact development/legacy
people/clothing overlap in the active split.

## Release gate

After all three retained sources and annotations are frozen and hashed:

    python3 tools/analysis/validate_tim_evaluation_split.py \
        --verify-hashes \
        --require-final-ready

Only after this passes may the four frozen architecture cells be evaluated.

If an outcome-driven behavior change is made afterward, the accessed sequences
are contaminated as final held-out evidence and a new prospective split is
required.
