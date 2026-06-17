# Selected-target memory

Date: 2026-06-06

## Purpose

Selected-target memory converts noisy tracker outputs into a control-valid target state for person following.

This thesis is not generic multi-object tracking. The objective is not to maintain all identities equally. The objective is to maintain one selected person as a reliable control target under occlusion, identity switches, and re-entry.

## Core problem

A tracker can output plausible tracks while still selecting the wrong person after crossing or occlusion.

For UAV following, this is unsafe:

> Wrong target is worse than LOST.

A LOST output stops or pauses following. A wrong-target output can command the UAV toward the wrong person.

## Layer position

Selected-target memory sits above the tracker:

- detector outputs `/detections`;
- tracker outputs `/tracks`;
- raw selected target is published as `/target`;
- selected-target memory publishes `/target_memory_mars`.

The memory layer does not replace the detector or tracker. It filters and stabilises the selected target.

## Inputs

The memory layer uses:

- current tracker candidates;
- previous selected-target state;
- geometry consistency;
- motion consistency;
- scale consistency;
- detection or track confidence;
- optional appearance evidence.

## Outputs

The output is a target state that is suitable for downstream control only when it is sufficiently trusted.

Current TIM-MARS output topic:

- `/target_memory_mars`

Diagnostic status topic:

- `/target_memory_mars/status`

## States

The conceptual states are:

- `NO_TARGET`: no selected target has been initialised;
- `LOCKED`: selected target is trusted;
- `UNCERTAIN`: target may be present but evidence is ambiguous;
- `LOST`: selected target is not safely available;
- `REACQUIRED`: target has been recovered after uncertainty or loss.

The exact implementation may encode these states through target validity, ID, status strings, and diagnostic reasons.

## Safety rule

The safety priority is:

1. minimise wrong-target output;
2. preserve correct-target output;
3. accept LOST when identity evidence is insufficient.

Therefore, a conservative policy may be valid even if it increases LOST, provided it substantially reduces wrong output without destroying correct output.

## Why this matters for control

The control module should follow a validated selected-target state, not blindly follow the current tracker ID.

A tracker ID is an internal association label. It is not a safety guarantee.

Selected-target memory provides a control-facing interpretation:

- follow when locked;
- slow down or hold when uncertain;
- stop target-following when lost.

## Current implementation direction

The current strongest implementation is TIM-MARS:

- selected-target memory above tracker outputs;
- MARS appearance embeddings used as identity evidence;
- conservative filtering to reject likely wrong handovers;
- missing appearance does not automatically force LOST unless strict diagnostic mode is enabled.

## Current evidence

The current main result source is:

- `docs/results/selected_target_tracking/hard_reentry_multi_tracker_summary.md`

On the hard re-entry sequence, ByteTrack + TIM-MARS is currently the best result:

- correct ratio = 0.970;
- wrong ratio = 0.013;
- lost ratio = 0.017.

## Limitations

Selected-target memory depends on the base tracker producing usable candidate tracks.

It is not expected to solve:

- long disappearance with no visual evidence;
- severe blur where the detector fails;
- identical-looking distractors without reliable appearance separation;
- highly fragmented tracker output.

These cases should produce LOST rather than unsafe wrong-target output.
