# Daily Plan - 2026-05-31 - TIM-MARS implementation target and weekly summary

## Main objective

Implement the best validated TIM-MARS policy from the offline simulator, or, if the simulator is not conclusive, produce a clean weekly summary and freeze the next implementation plan.

## Target outputs

Possible implementation outputs:

    ros2_ws/src/thesis_bringup/thesis_bringup/nodes/target_memory_mars_node.py
    ros2_ws/src/thesis_bringup/thesis_bringup/target_identity_memory.py

Expected documentation outputs:

    docs/results/tim_mars/2026-05-31__hard-reentry-policy-audit-and-next-steps.md
    docs/Daily-Logs/T-21_2026-05-25_to_05-31/index.md

Optional final report update:

    docs/results/tim_mars/README.md

## Tasks

### 1. Review Friday and Saturday outputs

Check:

- failure audit table,
- policy sweep table,
- candidate best policy,
- whether the result is robust or overfitted.

### 2. Decide implementation path

Choose one:

#### Option A, implement policy

Use this only if the simulator clearly supports the policy.

Possible implementation:

- appearance inconsistency rejection,
- candidate promotion with confirmation frames,
- ambiguity suppression,
- added diagnostics.

#### Option B, diagnostics only

Use this if the simulator is inconclusive or if the policy is too risky.

Add diagnostics for:

    current_app_similarity
    best_candidate_app_similarity
    second_candidate_app_similarity
    candidate_promoted
    rejection_reason
    ambiguity_reason
    switch_margin

### 3. Validate

Run at minimum:

    python3 -m py_compile relevant Python files
    colcon build --symlink-install --packages-select thesis_bringup thesis_tracker thesis_msgs

If policy changed:

- rerun the hard re-entry bag,
- re-evaluate correctness,
- generate updated panel if result improves.

### 4. Write weekly summary

Update:

    docs/Daily-Logs/T-21_2026-05-25_to_05-31/index.md

Include:

- real TIM-MARS validated,
- DeepSORT comparison corrected,
- fair correctness/performance tables generated,
- current TIM-MARS limitation identified,
- next policy path defined.

## Success criteria

By the end of Sunday:

- The week has a clean technical narrative.
- The next TIM-MARS improvement path is justified by data.
- Either a safe policy improvement is implemented, or the implementation is deferred with clear evidence.

## Do not do

Do not force a policy into the ROS node if the offline evidence is weak.
