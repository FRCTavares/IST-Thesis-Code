# Future Flights — Closed-Loop Validation Queue

This directory indexes physical work deferred beyond the 15 September
non-closed-loop capture session.

Canonical operator sheet:

    docs/flight/README.md

Detailed field procedure:

    docs/flight/field_day_runbook.md

Retained evidence contract:

    docs/flight/retained_evidence_package.md

## Deferred closed-loop work

Do not execute until the complete physical controller safety gate passes.

- RC takeover and RC failsafe validation
- PreArm / arming-readiness validation
- physical controller direction/sign validation
- restrained / props-off command-path validation
- closed-loop baseline following
- closed-loop distractor / crossing trial
- closed-loop loss / reacquisition trial
- bounded yaw-recovery candidate trial, only if separately authorised

The current MAVROS-inclusive retained recorder must also satisfy the strict
runtime-evidence gate before these are treated as final scientific trials.
