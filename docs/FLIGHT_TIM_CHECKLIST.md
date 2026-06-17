# Flight TIM Checklist

Date: 2026-06-06

## Purpose

Checklist for using selected-target memory during live or flight-oriented tests.

Current active selected-target memory direction:

- TIM-MARS
- output topic: `/target_memory_mars`
- diagnostic topic: `/target_memory_mars/status`

## Safety rule

Wrong target is worse than LOST.

During flight-oriented tests, the system must prefer LOST or no control-valid target over following the wrong person.

## Before flight

Verify the active stack:

- live stack starts cleanly;
- camera publishes frames;
- detector publishes `/detections`;
- tracker publishes `/tracks`;
- selected target output is available;
- dashboard target selection works;
- control node does not command motion without a valid target.

## Target selection

Target selection must be explicit.

Do not rely on automatic target selection for flight tests.

Use dashboard or API selection, then verify:

- selected target ID is visible in `/tracks`;
- `/target` updates;
- `/target_memory_mars` updates;
- `/target_memory_mars/status` reports a sensible state.

## TIM-MARS checks

Before using TIM-MARS in a flight-oriented test, confirm:

- `/target_memory_mars` is publishing;
- `/target_memory_mars/status` is publishing;
- the selected target does not jump to an obvious distractor during a static check;
- LOST is produced when evidence is insufficient;
- wrong-target output is not treated as acceptable continuity.

## Conservative appearance policy

Current hard re-entry evaluation policy uses conservative appearance filtering.

Important parameter:

- `appearance_conservative_require_appearance=false`

Meaning:

- apply conservative appearance checks when appearance is available;
- do not force LOST only because appearance is temporarily unavailable;
- use strict appearance-required mode only for diagnostics.

## Control interpretation

Recommended control interpretation:

| TIM state | Control behaviour |
|---|---|
| LOCKED | normal target-following allowed |
| REACQUIRED | cautious following or confirmation |
| UNCERTAIN | slow down, hold, or yaw-only behaviour |
| LOST | stop target-following / hover |
| NO_TARGET | no target-following |

The exact controller behaviour must remain conservative until validated outdoors.

## Do not use during flight

Do not use during flight unless explicitly implemented, documented, and enabled:

- archived TIM variants;
- offline policy simulators;
- unvalidated learned models;
- generated experimental timelines;
- manual-review-only annotations.

## Logging requirement

For flight-oriented TIM tests, record at minimum:

- `/camera/dashboard`
- `/detections`
- `/tracks`
- `/target`
- `/target_memory_mars`
- `/target_memory_mars/status`
- `/timing`
- `/timing_tracker`
- `/timing_target`
- `/control_ref/cmd_vel`

With MAVROS context, also record:

- `/mavros/state`
- `/mavros/local_position/pose`
- `/mavros/local_position/velocity_local`
- `/mavros/imu/data_raw`

## Post-flight review

After each test:

1. inspect target status transitions;
2. inspect wrong-target intervals;
3. verify LOST intervals are safe;
4. render visual audit clips if any target handover occurs;
5. write a short result note under `docs/results/` only if the test changes the thesis interpretation.

## Current result reference

Current selected-target tracking result source:

- `docs/results/selected_target_tracking/hard_reentry_multi_tracker_summary.md`

Current TIM-MARS design references:

- `docs/design/selected_target_memory.md`
- `docs/design/tim_mars_design.md`
- `docs/design/tim_evaluation_protocol.md`
- `docs/design/tim_tooling_index.md`
