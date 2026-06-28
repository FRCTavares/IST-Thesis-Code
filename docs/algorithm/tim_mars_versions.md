# TIM-MARS Algorithm Versions and Final Simplification

This document records the evolution of the TIM selected-target memory layer and defines the simplified final version used in the thesis.

## Final thesis name

The final algorithm should be referred to simply as:

**TIM-MARS: Target Identity Memory with MARS appearance consistency**

Do not describe the final algorithm as TIM-V4A, TIM-V4B, TIM-V4C, or TIM-V4D in the thesis. Those names are internal experiment history.

## Core problem

The tracker can output plausible but wrong identities after occlusion, crossing, or re-entry. For UAV following, publishing a wrong target is more dangerous than temporarily publishing no target.

Therefore, TIM-MARS follows the rule:

**wrong target is worse than lost target**

When identity evidence is ambiguous, TIM-MARS suppresses the controller-facing target instead of publishing a likely distractor.

## Final simplified algorithm

TIM-MARS is a selected-target memory layer placed after:

1. person detector
2. multi-object tracker
3. operator/raw target selector

It does not replace the detector or tracker. It filters the selected target before it reaches the controller.

The final algorithm has three components.

### 1. Geometric selected-target memory

TIM keeps a memory of the selected target:

- last trusted tracker ID
- last trusted bounding box
- target quality
- frames since last trusted observation
- finite state: NO_TARGET, LOCKED, UNCERTAIN, LOST, REACQUIRED

Each tracker candidate is scored against the target memory using:

- bounding-box IoU
- centre distance
- scale similarity
- detector/tracker confidence
- same-ID continuity bonus

This is the geometry-only TIM baseline.

### 2. MARS appearance consistency

TIM-MARS adds a MARS ReID embedding for each candidate when image data is available.

Appearance is used as supporting evidence, not as a full replacement for geometry. A candidate must still be geometrically plausible.

The positive appearance memory is updated only during trusted LOCKED states. It is frozen during uncertain, lost, or risky reacquisition states to avoid learning the wrong person.

### 3. Hard-negative and conservative ambiguity suppression

During trusted lock, nearby non-selected candidates can be stored as hard-negative appearance prototypes.

A future candidate is rejected if it matches both:

- the positive target memory
- a remembered negative/distractor memory

The conservative output filter suppresses candidates whose appearance evidence is not strong or not clearly separated from another candidate.

The practical final preset is:

- hard-negative memory enabled
- conservative appearance filtering enabled
- rank-aware reacquisition enabled
- absence recovery disabled
- appearance update cooldown disabled
- balanced appearance margin: 0.15

## State machine

### NO_TARGET

No operator-selected target exists. No controller-valid output is published.

### LOCKED

The selected target is trusted. Controller output is valid.

### UNCERTAIN

A plausible candidate exists, but the evidence is ambiguous or rejected by a safety gate. Controller output is suppressed.

### LOST

The selected target has been missing or unsafe for multiple frames. Controller output is suppressed.

### REACQUIRED

A candidate has been reacquired after uncertainty/loss, but it is not yet fully trusted. Controller output is suppressed until confirmed.

## Version history

### TIM-V0: Geometry-only selected-target memory

Used only geometric consistency:

- IoU
- distance
- scale
- confidence
- tracker ID continuity

This established the core memory layer independent of ROS and independent of appearance.

### TIM-V1: Lightweight appearance support

Added optional appearance memory.

Appearance was used only as a gated tie-breaker and was disabled by default. This helped in ambiguous frames but was not sufficient for strong re-identification.

### TIM-MARS: MARS appearance embeddings

Replaced lightweight appearance with MARS ReID embeddings.

This made appearance matching more meaningful for person re-identification and re-entry.

### Hard-negative TIM-MARS

Added memory of nearby distractors during trusted lock.

This prevents TIM from accepting a candidate that looks like the selected person but also matches a known distractor.

### Conservative TIM-MARS

Added explicit suppression when appearance evidence is not clearly separated from other candidates.

This implements the thesis safety rule: lost is safer than wrong.

### Balanced TIM-MARS

The strict conservative preset used an appearance margin of 0.25. In full clean replay, this was too suppressive.

A margin of 0.15 gave the best observed balance on the current diagnostic sequence:

- high correct-target duration
- zero wrong-target duration
- low lost-target duration

This should be treated as the practical field preset, while the stricter preset remains a safety-focused diagnostic preset.

## Internal experiments not part of the final algorithm

The following experimental branches should not be presented as part of the final thesis algorithm unless they are explicitly evaluated:

- active appearance-first reselection
- same-ID appearance ambiguity policy variants
- V4A risk policy
- old-ID distrust
- old-ID handoff
- old-ID reacquire block
- hold-last-on-reject

These were useful during exploration but make the final algorithm harder to explain and should be removed or quarantined from the main implementation if unused.

## Final thesis description

TIM-MARS is a conservative selected-target memory layer for RGB-only UAV person following. It combines geometric target continuity, MARS appearance consistency, and hard-negative distractor memory to decide whether the currently selected target is safe to publish. When target identity is ambiguous, TIM-MARS suppresses the output rather than risk commanding the UAV toward the wrong person.
