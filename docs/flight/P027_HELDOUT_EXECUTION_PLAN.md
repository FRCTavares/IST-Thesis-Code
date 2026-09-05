# Issue #27 — Held-Out Physical Execution Plan

## Status

The prospective evaluation freeze is complete and merged into `main`.

Active authorities:

- split: `tim_mars_split_v3_2026_09_05`;
- comparison contract: `tim_mars_final_comparison_v2_2026_09_05`;
- frozen algorithm commit: `2476991d262f7f388930aece0d731745f20dc1b3`;
- canonical TIM-MARS SHA-256:
  `0f2ac3fc780781c3921430310abfddeac2bfeb6c1c833529f2f1054d263f15c0`;
- release state: `final_ready=0/3`.

H01, H02 and H03 have not been captured or inspected.

This document is the execution queue for physical work that must only be
performed when the required people, hardware and recording environment are
available.

## Scientific boundary

Before all three held-out sources, physical-v2 annotations,
participant/outfit records and hashes are frozen:

- do not inspect tracker or TIM correctness;
- do not inspect TIM candidate scores;
- do not compare architectures;
- do not tune thresholds;
- do not alter tracker settings;
- do not change models;
- do not change bootstrap or evaluation semantics.

A physical capture may be repeated only for a recording defect, unusable
imagery, or failure to perform the specified physical scenario.

It must never be repeated because an algorithm performs badly.

## Physical execution order

Perform one scenario at a time.

### 1. H01 — Exit and re-entry

Operator sheet:

`docs/flight/P027_H01_EXIT_REENTRY.md`

Physical requirements:

- selected target visible initially;
- at least one distractor visible;
- selected target fully exits the image;
- selected target physically absent for approximately 5–8 s;
- distractor visible during at least part of the absence;
- selected target re-enters;
- retain at least 10 s after re-entry.

Capture command:

    tools/experiments/record_p027_heldout_sequence.sh h01

After capture, inspect only recording integrity and physical-scene compliance.

### 2. H02 — Crossing

Operator sheet:

`docs/flight/P027_H02_CROSSING.md`

Capture command:

    tools/experiments/record_p027_heldout_sequence.sh h02

Perform the physical crossing exactly as specified by the operator sheet.
Do not inspect whether tracker identities switch.

### 3. H03 — Occlusion and distractor

Operator sheet:

`docs/flight/P027_H03_OCCLUSION_DISTRACTOR.md`

Capture command:

    tools/experiments/record_p027_heldout_sequence.sh h03

Perform the physical occlusion/distractor scenario exactly as specified by the
operator sheet. Acceptance is based on the physical scenario and recording
quality only.

## Pre-capture gate for every sequence

Before H01, H02 or H03:

1. repository tree must be clean;
2. active split validator must pass;
3. at least 40 GiB free storage;
4. `/dev/video0`, `/dev/media0` and `/dev/hailo0` must exist;
5. use the dedicated source-only capture helper;
6. tracker, TIM-MARS, controller and MAVROS remain disabled.

Validation command:

    python3 tools/analysis/validate_tim_evaluation_split.py --verify-hashes

## Allowed immediate post-capture inspection

Allowed before final release:

- `ros2 bag info`;
- topic presence and message counts;
- duration and timestamps;
- corruption/finalization checks;
- source-image quality;
- confirmation that the planned physical scenario occurred;
- physical-v2 annotation;
- anonymous participant and outfit coding.

## Required annotation outputs

- `docs/data/physical_target_references/heldout_h01_exit_reentry.json`
- `docs/data/physical_target_references/heldout_h02_crossing.json`
- `docs/data/physical_target_references/heldout_h03_occlusion_distractor.json`

For every retained sequence also record:

- anonymous participant codes;
- outfit codes;
- exact participant overlap with development/legacy recordings;
- exact clothing/outfit overlap with development/legacy recordings;
- source paths;
- source file sizes;
- annotation SHA-256;
- retained source hashes and provenance.

## Final release gate

Only after H01, H02 and H03 are captured, annotated and fully frozen:

    python3 tools/analysis/validate_tim_evaluation_split.py \
        --verify-hashes \
        --require-final-ready

Expected release state before architecture evaluation:

`final_ready=3/3`

Only after that gate passes may the frozen architecture cells be evaluated.

## Current next action

No physical experiment is required while away from the appropriate recording
environment.

The next physical thesis session should begin with H01 using its operator sheet,
followed by H02 and H03 if conditions and participants allow.
