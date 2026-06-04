# TIM Evaluation Protocol

Date: 2026-05-07  
Scope: Target Identity Memory evaluation for selected-person UAV following.

## 1. Motivation

TIM must not be evaluated only by whether it keeps publishing a valid target.

Main principle:

> Correct target > any target.

A method that keeps outputting a target is not good if that target is the wrong person. For UAV following, a valid output is useful only when it still corresponds to the selected person.

Therefore, every future TIM comparison must separate:

- valid and correct
- valid but wrong
- invalid and lost

Valid target duration alone is insufficient.

A valid output can be correct, which is good, or wrong, which is dangerous.

This protocol evaluates whether TIM follows the selected person, not merely whether it follows some person.

## 2. Target Correctness Labels

### CORRECT_TARGET

TIM or raw output overlaps, or is associated with, the annotated selected person.

For the first track-ID based evaluator:

    output_track_id == correct_target_track_id

### WRONG_TARGET

The output is valid but overlaps a distractor or clearly follows the wrong person.

For the first track-ID based evaluator:

    output_track_id != 0
    output_track_id != correct_target_track_id

while the selected person is visible.

### LOST_TARGET

The selected person is visible, but the output is invalid.

For the first evaluator:

    target_visible == true
    output_track_id == 0

### TARGET_NOT_VISIBLE

The selected person is genuinely absent or fully occluded.

This should not be counted as lost target time, because there is no visible selected person to follow.

If the system outputs a valid target during this state, it is counted separately as target-absent-but-output-valid time.

### NO_TARGET_SELECTED

Time before the operator selects a target.

This interval is excluded from visible-target correctness ratios.

### UNCERTAIN_OUTPUT

Optional label for states where TIM is uncertain and intentionally outputs an invalid target.

This can be useful when analysing TIM safety behaviour.

## 3. Main Metrics

Report separately for raw `/target` and TIM `/target_memory`.

Duration metrics:

- correct_target_duration_s
- wrong_target_duration_s
- lost_target_duration_s
- target_not_visible_duration_s
- target_absent_but_output_valid_duration_s
- no_target_selected_duration_s

Ratio metrics over visible-target intervals:

    visible_target_duration_s =
        correct_target_duration_s
      + wrong_target_duration_s
      + lost_target_duration_s

    correct_target_ratio = correct_target_duration_s / visible_target_duration_s
    wrong_target_ratio   = wrong_target_duration_s   / visible_target_duration_s
    lost_target_ratio    = lost_target_duration_s    / visible_target_duration_s

Reacquisition metrics to add after the first evaluator:

- time_to_correct_reacquire_s
- number_of_correct_reacquisitions
- number_of_wrong_reacquisitions
- number_of_target_switches

TIM state durations:

- NO_TARGET
- LOCKED
- UNCERTAIN
- LOST
- REACQUIRED

Latency metrics:

- mean
- p50
- p95
- p99

## 4. Annotation Format

The first annotation format is interval-based and track-ID based.

Columns:

    bag_name,start_s,end_s,target_label,target_visible,correct_target_track_id,distractor_track_ids,event_type,notes

This is intentionally simple. The goal is to evaluate TIM behaviour, not build a full annotation platform.

Later versions may extend this format with manually drawn bounding boxes.

## 5. Classification Rule

For each annotation interval, evaluate raw `/target` and TIM `/target_memory` separately.

If the selected target is visible:

    output id == correct_target_track_id  -> CORRECT_TARGET
    output id == 0                        -> LOST_TARGET
    output id != correct_target_track_id  -> WRONG_TARGET

If the selected target is not visible:

    output id == 0 -> safe no-output behaviour
    output id != 0 -> target absent but output valid

If no target has been selected yet:

    label -> NO_TARGET_SELECTED

## 6. Interpretation

A method is better only if it improves correct target behaviour without increasing unsafe wrong-target output.

A result with higher valid duration but higher wrong-target duration is not necessarily an improvement.

For control, the ranking priority is:

1. correct target output
2. safe invalid output when uncertain
3. wrong target output

Wrong target output is the worst case.

## 7. First Version Acceptance Criteria

Minimum useful evaluator:

- reads one bag
- reads one annotation CSV
- compares raw `/target` against TIM `/target_memory`
- computes correct, wrong, lost, and absent-output durations
- writes `summary.md`
- writes `summary.csv`

This is enough for the first supervisor-feedback response.
