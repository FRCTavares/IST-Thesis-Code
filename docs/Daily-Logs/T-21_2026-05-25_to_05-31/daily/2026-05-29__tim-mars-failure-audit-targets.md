# Daily Plan - 2026-05-29 - TIM-MARS failure audit

## Main objective

Build a failure-audit pipeline for the hard re-entry bag so that TIM-MARS improvement is based on evidence, not guessing.

## Target outputs

Create:

    reports/tim_mars_failure_audit/hard_reentry_event_table.csv
    reports/tim_mars_failure_audit/hard_reentry_event_table.md

Optional if time allows:

    reports/tim_mars_failure_audit/hard_reentry_timeline_plot.png

## Tasks

### 1. Confirm input artefacts

Use the hard re-entry OCSORT + TIM-MARS bag:

    artifacts/bags/eval_matrix/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_mars__target_1__r4

Use the manual OCSORT annotation:

    docs/annotations/2026-05-14__hard_reentry_ocsort_tim_on_target1/target_correctness_annotations_manual_review_v3.csv

Use topics:

    /target
    /target_memory_mars
    /target_memory_mars/status
    /tracks

### 2. Inspect available diagnostics

Check whether `/target_memory_mars/status` contains useful fields for:

- state
- reason
- candidate scores
- appearance similarity
- ambiguity
- current selected ID
- output validity

If the status message does not expose enough information, identify exactly which fields need to be added.

### 3. Build first audit script

Create a script under:

    tools/analysis/audit_tim_mars_failures.py

The script should load:

- bag messages,
- target correctness annotations,
- raw `/target`,
- `/target_memory_mars`,
- `/target_memory_mars/status`,
- `/tracks`.

### 4. Produce event-level table

For each annotation interval, report:

    start_s
    end_s
    expected_correct_id
    raw_target_ids_seen
    tim_mars_ids_seen
    dominant_raw_id
    dominant_tim_mars_id
    tim_mars_correct_duration_s
    tim_mars_wrong_duration_s
    tim_mars_lost_duration_s
    dominant_state
    dominant_reason

### 5. Identify key failure events

At minimum, inspect these intervals:

- ID handover around OCSORT ID 1 to ID 96.
- re-entry around ID 113.
- recovery around ID 142.
- late switch around ID 161.
- known distractor intervals involving ID 1.

## Success criteria

By the end of Friday:

- The audit table exists.
- Each major wrong interval has a probable cause.
- We know whether the next fix should be:
  1. appearance rejection,
  2. candidate promotion,
  3. ambiguity suppression,
  4. negative distractor memory,
  5. or better diagnostics first.

## Do not do

Do not modify the live TIM-MARS policy yet unless the audit clearly identifies a small safe diagnostic-only patch.
