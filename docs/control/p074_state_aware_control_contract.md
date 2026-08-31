# Issue #74 — State-aware selected-person control contract

Date frozen: 31 August 2026

## Authority boundary

TIM-MARS remains the sole selected-person identity authority.

The controller may consume:

- `/target_memory_mars` for controller-authoritative target geometry;
- `/target_memory_mars/status` for TIM-MARS state, control intent, selection generation, and diagnostics.

The controller must never derive motion authority from:

- `/target`;
- `/tracks`;
- detector candidates;
- candidate ranking diagnostics;
- unconfirmed reacquisition candidates.

## Existing fail-safe retained

The canonical TIM-MARS runtime uses `zero_id_when_not_visible=true`.

When TIM-MARS does not grant `control_valid`, the controller-facing
`TargetState` is therefore published with `id=0` and zero geometry.

The existing controller freshness checks, saturation, slew limiting,
body-frame command convention, and optional MAVROS publication remain in force.

## Selection generation

TIM-MARS owns the controller-facing `selection_generation`.

The generation:

- starts from zero for a TIM-MARS node instance;
- increments on every explicit select;
- increments on every explicit clear;
- increments for any mirrored positive selection accepted by TIM-MARS;
- is included in `/target_memory_mars/status`.

The controller treats any generation change, including a decrease after a
TIM-MARS restart, as an authority discontinuity.

A generation change immediately:

- cancels recovery;
- invalidates last-trusted recovery history;
- commands zero until fresh trusted authority is established again.

The dashboard's existing target-authority generation remains UI/provenance
metadata and is not a separate controller identity authority.

## Trusted normal following

Normal translational following is allowed only when all of the following hold:

- controller-authoritative `TargetState` is valid and fresh;
- TIM-MARS state is `LOCKED`;
- TIM-MARS control mode is `NORMAL`;
- target and status belong to the current selection generation.

Normal following reuses the existing controller:

- bbox horizontal centre error -> yaw rate;
- apparent target height -> forward/back velocity;
- optional lateral behaviour remains unchanged;
- existing saturation and slew limits remain unchanged.

## Uncertain and confirmation states

For `UNCERTAIN`, `REACQUIRED`, `CONFIRM`, stale status, mismatched authority,
or otherwise untrusted state:

- forward velocity is zero;
- lateral velocity is zero;
- candidate geometry cannot steer the aircraft;
- default output is hover/zero.

A `REACQUIRED` state does not immediately restore translation. Normal following
resumes only after TIM-MARS returns to trusted `LOCKED` + `NORMAL`.

## Last-trusted observation

The controller may retain only observations received while the normal-follow
trust conditions above are satisfied.

Retained recovery memory is limited to:

- horizontal image error;
- observation timestamp;
- selection generation.

It is never updated from raw tracker or detector data, uncertain candidates,
LOST state, or confirmation state.

## Bounded yaw-only recovery

Active recovery is feature-gated and defaults OFF.

When enabled, recovery may begin only when:

- TIM-MARS reports `LOST`;
- a recent last-trusted observation exists;
- its selection generation is still current;
- source/status timing remains valid.

During recovery:

- `vx = 0`;
- `vy = 0`;
- only bounded yaw rate is permitted;
- yaw direction is the sign of the last trusted horizontal error;
- yaw magnitude is capped;
- yaw slew remains capped;
- recovery duration is capped;
- integrated absolute yaw-command budget is capped;
- last-trusted observation age is capped.

Recovery terminates immediately on:

- trusted reacquisition;
- explicit selection clear;
- selection-generation change;
- stale/future/non-monotonic authority information;
- timeout;
- yaw/search budget exhaustion;
- disabled feature.

After termination without trusted reacquisition, output is zero.

No endless scan, translation search, altitude search, candidate chasing,
mapping, planning, MPC, or RL control is introduced.

## Diagnostics

The controller must expose enough diagnostics to reconstruct each decision,
including:

- resolved mode;
- reason;
- TIM-MARS state;
- TIM-MARS control mode;
- selection generation;
- target/status freshness;
- recovery enabled/active;
- last-trusted age;
- recovery direction;
- recovery elapsed time;
- used/remaining yaw budget;
- saturation state;
- final command values.

## Promotion boundary

Deterministic implementation and tests are required before physical validation.

Active recovery remains experimental until the later closed-loop comparison.
If it does not improve recovery without increasing wrong-person non-zero
control, it is rejected and the conservative hover-on-loss baseline is retained.
