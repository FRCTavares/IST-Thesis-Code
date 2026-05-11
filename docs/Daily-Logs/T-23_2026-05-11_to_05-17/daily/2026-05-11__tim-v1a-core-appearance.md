# Daily Log - 2026-05-11 - TIM-V1A Core Appearance Cue

## Goal

Resume thesis development and advance from TIM-V0 towards TIM-V1.

## Starting point

Repository was clean at the beginning of the session.

Relevant previous commits:

- 4d1df65 05-09-2026: Add TIM-V1A appearance feature utilities
- 1375ebe 05-09-2026: Prepare TIM field recording and TIM-V1A design

Existing baseline tests passed after disabling ROS pytest plugin autoload.

Command used:

    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest src/thesis_bringup/test/test_appearance_memory.py src/thesis_bringup/test/test_target_memory_synthetic.py -q

Result:

    20 passed

## TIM-V1A core appearance cue integrated

Implemented TIM-V1A inside the ROS-free TargetIdentityMemory core.

Changed files:

- ros2_ws/src/thesis_bringup/thesis_bringup/target_memory.py
- ros2_ws/src/thesis_bringup/test/test_target_memory_appearance.py

Main changes:

- CandidateTrack now supports optional appearance features.
- CandidateScore now reports appearance similarity and whether appearance was used.
- TargetMemoryConfig now exposes optional TIM-V1A appearance parameters:
  - appearance_enabled
  - appearance_weight
  - appearance_min_similarity
  - appearance_update_alpha
  - appearance_ambiguous_only
- Appearance remains disabled by default, preserving TIM-V0 behaviour.
- Appearance is used only as a gated tie-breaker.
- Appearance cannot rescue geometrically implausible candidates.
- Appearance memory updates only when the state is confirmed as LOCKED.
- Appearance memory freezes during UNCERTAIN, LOST, and REACQUIRED.

## Safety correction

Initial test feedback showed that a strong appearance score could rescue a far-away geometrically implausible candidate.

This was corrected by adding a geometry plausibility gate before applying the appearance bonus.

Interpretation:

- appearance can resolve ambiguous nearby candidates
- appearance cannot make TIM follow a far-away lookalike

## Validation

Command used:

    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest src/thesis_bringup/test/test_appearance_memory.py src/thesis_bringup/test/test_target_memory_synthetic.py src/thesis_bringup/test/test_target_memory_appearance.py -q

Result:

    25 passed

Syntax check:

    python3 -m py_compile ros2_ws/src/thesis_bringup/thesis_bringup/target_memory.py ros2_ws/src/thesis_bringup/thesis_bringup/appearance_memory.py ros2_ws/src/thesis_bringup/test/test_target_memory_appearance.py

Result:

- passed

## Commit

- 46bbd07 05-11-2026: Integrate TIM-V1A appearance cue

## Interpretation

TIM-V1A core logic is now implemented and unit-tested.

This is not live image integration yet. The ROS wrapper does not yet extract appearance features from camera images.

## Next step

Implement TIM-V1B:

- connect appearance extraction to target_memory_node.py
- subscribe to an image topic only when appearance is enabled
- extract per-track appearance features from the latest image
- keep the feature path disabled by default
- preserve TIM-V0 live behaviour unless explicitly enabled
