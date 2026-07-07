# TIM-MARS selected-target memory

TIM-MARS is the selected-target memory layer used for safer vision-based UAV
person-following perception. It sits above detection, multi-object tracking, and
raw target selection. Its job is not to improve generic tracking. Its job is to
publish one conservative, controller-facing target state for the selected person.

The core safety principle is simple: when identity evidence is weak, TIM-MARS
prefers uncertainty or no publication over publishing a plausible but possibly
wrong target.

## Runtime data flow

Input topics:
- /tracks
- optional /camera/image_raw
- optional mirrored /target selection

Runtime path:
1. target_memory_mars_node.py receives tracker candidates.
2. Tracks are converted into CandidateTrack objects.
3. Optional MARS appearance embeddings are attached.
4. TargetIdentityMemory.update() evaluates the selected target.
5. The node publishes /target_memory_mars and /target_memory_mars/status.

Inside TargetIdentityMemory.update(), TIM-MARS combines:
- geometry scoring,
- appearance scoring,
- short-gap same-ID protection,
- absence-aware recovery gating,
- rank-aware reacquisition,
- hard-negative rejection.

## State machine

TIM-MARS maintains an internal selected-target state:

NO_TARGET -> LOCKED -> UNCERTAIN -> LOST -> REACQUIRED -> LOCKED

State meanings:
- NO_TARGET: no operator-selected or auto-selected target exists.
- LOCKED: the selected target is considered safe to publish.
- UNCERTAIN: the target is temporarily unreliable, usually after missed or weak evidence.
- LOST: the target has been missing long enough that reacquisition must be conservative.
- REACQUIRED: a candidate has been accepted after uncertainty/loss but needs confirmation before normal locked publication.

## Candidate scoring

Each tracker output is converted into a CandidateTrack. The memory state machine
compares each candidate against the remembered selected target using:
- tracker identity continuity,
- bbox IoU,
- normalized center distance,
- bbox scale similarity,
- detector/tracker confidence,
- optional positive appearance similarity,
- optional hard-negative appearance similarity.

Geometry is always the primary guard. Appearance is used only when configured
and when geometry makes the candidate plausible enough.

## Appearance memory policy

TIM-MARS can attach MARS ReID embeddings to candidates. The positive appearance
memory is updated conservatively:
- update only when the target is confidently LOCKED,
- freeze during UNCERTAIN, LOST, and REACQUIRED,
- optionally apply a cooldown after reacquisition,
- do not let appearance rescue geometrically implausible candidates.

This avoids learning a distractor during ambiguous recovery.

## Reacquisition safeguards

TIM-MARS includes several safeguards for selected-target recovery:
- same-ID relief: the previous tracker ID can be accepted with reduced threshold.
- short-gap protection: after a brief miss, new IDs can be suppressed while the old ID has a grace window to return.
- rank-aware reacquisition: in lost/uncertain states, candidates can be ranked by appearance evidence rather than raw total score alone.
- absence-aware recovery: after longer absence, new-ID recovery requires stronger geometry and appearance evidence.
- candidate-belief confirmation: plausible new candidates can require repeated observation before acceptance.
- hard-negative memory: distractor appearance prototypes observed while locked can suppress wrong-target recovery.

## ROS role

target_memory_mars_node.py is ROS glue around the pure algorithm. It owns:
- ROS parameter declaration and reading,
- subscriptions to tracks, selection commands, optional image stream, and optional raw target mirroring,
- conversion from Track2DArray to CandidateTrack,
- optional appearance attachment,
- publication of TargetState,
- JSON status diagnostics.

The node should not contain core selection policy. Core policy belongs in
target_memory.py and supporting modules.

## File map

- target_memory.py: core selected-target memory state machine.
- types.py: shared dataclasses, enums, and configuration.
- memory_state.py: private internal memory state and control-mode mapping.
- geometry_scoring.py: stateless bbox geometry and base candidate scoring.
- appearance_memory.py: crop, HSV feature, cosine similarity, and feature-memory update helpers.
- appearance_policy.py: appearance scoring policy and appearance gate logic.
- appearance_attachment.py: runtime MARS embedding attachment, caching, and diagnostics.
- mars_reid_backend.py: thin wrapper around the DeepSORT MARS-small128 extractor.
- hard_negative_memory.py: bounded distractor appearance memory.
- reacquisition_policy.py: confirmation counters and ambiguity/absence helper policies.
- ros_params.py: ROS parameter declaration and conversion to TargetMemoryConfig.
- ros_messages.py: conversion from pure TIM outputs to ROS messages and JSON diagnostics.
- target_memory_mars_node.py: ROS 2 node wiring the full TIM-MARS runtime path.

## Final thesis note

For thesis evaluation, TIM-MARS should be treated as a control-facing safety
layer. It is not a replacement for the detector or tracker. Its contribution is
conservative selected-target publication under identity ambiguity, short target
loss, distractors, and tracker ID instability.
