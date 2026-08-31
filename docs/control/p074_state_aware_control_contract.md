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

## Authority session and selection generation

TIM-MARS owns the controller-facing authority epoch:

- `selection_session_id` identifies one TIM-MARS node instance;
- `selection_generation` identifies select/clear transactions within that
  session.

The session identifier is newly generated when the TIM-MARS node starts.

Within one session, the generation:

- starts from zero;
- increments on every explicit select;
- increments on every explicit clear;
- increments for any mirrored positive selection accepted by TIM-MARS;
- never moves backwards.

Both fields are included in `/target_memory_mars/status`.

The controller:

- accepts a generation advance within the current session as an authority
  discontinuity;
- rejects generation rollback within the same session;
- accepts a previously unseen TIM-MARS session as a hard authority reset;
- retires the previous session when a new session is accepted;
- rejects delayed status from retired sessions.

Any accepted authority discontinuity immediately:

- cancels recovery;
- invalidates last-trusted recovery history;
- clears the cached target;
- commands zero until fresh trusted authority is established again.

The dashboard's existing target-authority generation remains UI/provenance
metadata and is not a separate controller identity authority.

## Trusted normal following

Normal translational following is allowed only when all of the following hold:

- controller-authoritative `TargetState` is valid and fresh;
- TIM-MARS status is fresh;
- TIM-MARS state is `LOCKED`;
- TIM-MARS control mode is `NORMAL`;
- status belongs to the current TIM-MARS session and selection generation;
- target and status have the same positive causal `frame_id`;
- target and status have the same positive source timestamp.

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

Active recovery is feature-gated and defaults OFF. The live-stack launcher
explicitly passes `enable_yaw_recovery=false`; deterministic implementation
does not by itself promote recovery for aircraft use.

The implemented development bounds are:

- requested recovery yaw rate: `0.10 rad/s`;
- maximum recovery duration: `1.0 s`;
- maximum integrated absolute yaw-command budget: `0.10 rad`;
- maximum last-trusted observation age: `1.0 s`;
- yaw magnitude additionally obeys the existing `max_yaw_z` limit;
- yaw command changes additionally obey the existing `max_delta_yaw_z`
  slew limit.

When enabled, recovery may begin only when:

- TIM-MARS reports `LOST`;
- a recent last-trusted observation exists;
- its selection generation is still current;
- TIM authority status remains fresh;
- the last trusted horizontal error provides a non-zero search direction;
- the same trusted observation has not already been consumed by a previous
  recovery attempt.

A recovery attempt starts from a hard-zero command. During recovery:

- `vx = 0`;
- `vy = 0`;
- only bounded yaw rate is permitted;
- yaw direction is the sign of the last trusted horizontal error;
- candidate, tracker, and detector geometry cannot steer recovery;
- yaw saturation remains capped;
- yaw slew remains capped;
- recovery duration is capped;
- integrated absolute yaw-command budget is capped;
- last-trusted observation age is capped.

One trusted observation can authorize at most one bounded recovery attempt.
A new trusted `LOCKED` + `NORMAL` observation re-arms recovery.

Recovery terminates immediately on:

- trusted reacquisition or another non-recovery authority state;
- explicit selection clear;
- selection-generation change;
- TIM authority session change;
- stale/future/non-monotonic authority information;
- timeout;
- yaw/search budget exhaustion;
- disabled feature.

After termination without trusted reacquisition, output is zero.

No endless scan, translation search, altitude search, candidate chasing,
mapping, planning, MPC, or RL control is introduced.

## Diagnostics

Controller diagnostics make the authority and recovery decision auditable.
The deterministic implementation reports:

- resolved policy mode and reason;
- TIM-MARS state and control mode;
- selection generation and authority session;
- authority-status freshness;
- recovery enabled/active state;
- last-trusted observation age;
- recovery direction;
- recovery elapsed time;
- integrated absolute yaw command;
- remaining integrated yaw budget;
- yaw saturation state;
- final post-shaping `(vx, vy, yaw_z)` command.

Recovery entry, budget exhaustion, and termination emit forced diagnostics.
Active recovery also emits diagnostics according to the controller debug
cadence.

Diagnostics provide observability only and never motion authority.

## Promotion boundary

Deterministic implementation and tests are required before physical validation.

Active recovery remains experimental until the later closed-loop comparison.
If it does not improve recovery without increasing wrong-person non-zero
control, it is rejected and the conservative hover-on-loss baseline is retained.
