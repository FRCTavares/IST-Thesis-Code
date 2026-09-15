# 15 September 2026 — Field Capture Queue

This directory is the operator index for the non-closed-loop physical work
planned for 15 September 2026.

The canonical procedures remain in `docs/flight/`. In particular, the frozen
H01/H02/H03 files MUST NOT be moved, renamed, duplicated, or modified because
their exact paths are part of the Stage-7 prospective held-out contract.

## Planned today

### 1. FHD representative drone-POV development capture

Canonical sheet:

    docs/flight/P050_FHD_FIELD_CHEATSHEET.md

Development / non-held-out only.

### 2. Manual dynamic-UAV TIM-MARS validation

Canonical sheet:

    docs/flight/P050_DYNAMIC_UAV_TIM_TRIAL.md

Pilot has sole aircraft-motion authority. Thesis controller remains OFF.

### 3. Prospective held-out H01/H02/H03

Canonical runbook:

    docs/flight/P027_HELDOUT_CAPTURE_RUNBOOK.md

Current Stage-7 execution plan:

    docs/flight/P027_HELDOUT_EXECUTION_PLAN_v2.md

Scenario sheets:

    docs/flight/P027_H01_EXIT_REENTRY.md
    docs/flight/P027_H02_CROSSING.md
    docs/flight/P027_H03_OCCLUSION_DISTRACTOR.md

Frozen capture commands:

    tools/experiments/record_p027_heldout_sequence.sh h01
    tools/experiments/record_p027_heldout_sequence.sh h02
    tools/experiments/record_p027_heldout_sequence.sh h03

Do not inspect, replay, analyse, or tune against H01/H02/H03 between captures.

## Not authorised today by this queue

Autonomous / closed-loop controller trials are deferred to
`docs/flight/future-flights/README.md`.
