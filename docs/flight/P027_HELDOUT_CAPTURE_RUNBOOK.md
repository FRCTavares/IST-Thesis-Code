# Issue #27 — H01/H02/H03 Held-Out Capture

Capture is complete.

Accepted source-only runs from 15 September 2026:

- H01: `16-31-10`
- H02: `16-35-33`
- H03: `16-55-25`

Rejected recording attempt:

- H03: `16-41-41`

Each accepted capture retained only:

    /camera/image_raw
    /detections

Tracker, TIM-MARS, controller and MAVROS were OFF.

## Current work

Do not recapture the sequences.

Continue with annotation and release preparation in:

    docs/flight/P027_HELDOUT_EXECUTION_PLAN_v2.md

Required annotation files:

    docs/data/physical_target_references/heldout_h01_exit_reentry.json
    docs/data/physical_target_references/heldout_h02_crossing.json
    docs/data/physical_target_references/heldout_h03_occlusion_distractor.json

Check the active freeze with:

    cd ~/Desktop/Thesis-Code || exit 1
    set +u
    python3 tools/analysis/validate_tim_evaluation_split.py docs/data/splits/tim_mars_split_v4.json --verify-hashes

Final release requires:

    python3 tools/analysis/validate_tim_evaluation_split.py docs/data/splits/tim_mars_split_v4.json --verify-hashes --require-final-ready

Required before final held-out evaluation:

    final_ready=3/3

Do not change the frozen algorithm, tracker, models, thresholds, evaluator semantics, architecture arms or primary metrics based on held-out results.
