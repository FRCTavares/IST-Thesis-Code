# Issue #27 — Held-Out Physical Execution Plan (v2)

Stage-7 held-out capture is complete.

The original `P027_HELDOUT_EXECUTION_PLAN.md` is historical provenance for the superseded split-v3 freeze.

## Active freeze

- split: `docs/data/splits/tim_mars_split_v4.json`
- comparison: `docs/data/splits/tim_mars_final_comparison_v3.json`
- algorithm authority: `79f11b631688889bf5ffbeb3c16ef543a53f9973`
- canonical TIM-MARS SHA-256: `b0a98334cadf635aa831d1bbe335f172686339f81def3efd2200211479c50f8c`

Validate:

    cd ~/Desktop/Thesis-Code || exit 1
    set +u
    python3 tools/analysis/validate_tim_evaluation_split.py docs/data/splits/tim_mars_split_v4.json --verify-hashes

## Captures — COMPLETE

Accepted source-only captures from 15 September 2026:

- H01: `16-31-10`
- H02: `16-35-33`
- H03: `16-55-25`

Each retained only:

    /camera/image_raw
    /detections

During capture:

- tracker OFF
- TIM-MARS OFF
- controller OFF
- MAVROS OFF

The earlier H03 `16-41-41` attempt is rejected recording evidence and is not part of the final evaluation.

Do not recapture H01/H02/H03 because of algorithm results.

## Current work

Physical-v2 annotation and release preparation are now the only Issue #27 steps before evaluation.

Required annotation files:

    docs/data/physical_target_references/heldout_h01_exit_reentry.json
    docs/data/physical_target_references/heldout_h02_crossing.json
    docs/data/physical_target_references/heldout_h03_occlusion_distractor.json

For each sequence:

1. complete human physical-v2 annotation;
2. record anonymous participant/outfit information;
3. verify source and annotation hashes;
4. update the corresponding split entry;
5. validate the split;
6. mark that entry ready only after review.

Do not use held-out algorithm performance to change:

- TIM-MARS
- tracker configuration
- detector/model choice
- thresholds
- evaluator semantics
- architecture arms
- primary metrics

## Release gate

Do not run the final held-out architecture evaluation until:

    python3 tools/analysis/validate_tim_evaluation_split.py docs/data/splits/tim_mars_split_v4.json --verify-hashes --require-final-ready

Required result:

    final_ready=3/3

Only after that gate passes may the frozen architecture comparison run on H01/H02/H03.

## Important

The first held-out access already locked the prospective algorithm and evaluation contract.

Recording-integrity failures may be documented as rejected attempts.

Bad algorithm performance is never a reason to recapture or change the frozen contract.
