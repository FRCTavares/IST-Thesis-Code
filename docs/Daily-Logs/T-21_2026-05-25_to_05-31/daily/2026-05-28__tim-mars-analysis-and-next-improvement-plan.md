# Daily Log - 2026-05-28 - TIM-MARS analysis and next improvement plan

## Main objective

Convert the four-way comparison into a clear technical conclusion and define the next improvement path for TIM.

## Work completed

### Fair interpretation of DeepSORT MARS

Clarified that DeepSORT MARS should not be described as failing after output.

Correct interpretation:

- DeepSORT MARS delays selected-target output during initialisation.
- Once selected-target output becomes available, it remains correct in this sequence.
- This suggests a conservative identity initialisation behaviour.
- The cost is lower output rate and delayed selected-target availability.

Thesis-safe wording:

    DeepSORT MARS is accurate after selected-target output, but its selected identity becomes available late and the pipeline has lower throughput than the OCSORT-based alternatives.

### TIM-MARS compared against DeepSORT MARS

Clarified why TIM-MARS is not as good as DeepSORT in this bag.

Key point:

    TIM-MARS is not DeepSORT. It uses a MARS cue inside a lightweight selected-target memory layer on top of OCSORT, while DeepSORT integrates MARS directly into the tracker association stage.

This means:

- DeepSORT uses MARS at every association step.
- TIM-MARS only sees the tracks after OCSORT has already produced IDs.
- TIM-MARS inherits OCSORT ID switches.
- TIM-MARS must decide whether a new OCSORT ID is the selected target after the fact.

### Next improvement direction defined

The current TIM-MARS result shows that adding appearance features alone is not sufficient.

Next policy improvements should target:

1. Less wrong-target duration.
2. Less lost-target duration.
3. More correct-target duration.

Priority remains:

    wrong target is worse than lost target

## Proposed TIM improvement targets

### A. Reacquisition candidate promotion

Add a rule that promotes a new candidate ID when:

- current memory output is appearance-inconsistent,
- another candidate has high MARS similarity to the selected-target memory,
- the candidate remains stable for N frames,
- the score margin over the current output is large enough.

### B. Current-output appearance rejection

TIM should not only ask which candidate looks like memory. It should also ask whether the current output still looks like the selected target.

If current output has poor appearance similarity, TIM should downgrade it or enter an uncertain/reacquisition state.

### C. Appearance as a gate, not only a bonus

MARS similarity should sometimes veto a geometrically plausible but visually wrong candidate, especially during:

- crossings,
- occlusion exits,
- re-entry,
- ID switches,
- close distractor interactions.

### D. Ambiguity suppression

If two candidates are too close in score, TIM should prefer no valid control output over a wrong target.

### E. Negative distractor memory

Maintain a lightweight memory of repeated distractor appearances and penalise candidates that look like known distractors.

## Target artefacts for the rest of the week

The main deliverable for the rest of the week is a TIM-MARS failure audit:

    reports/tim_mars_failure_audit/hard_reentry_event_table.csv
    reports/tim_mars_failure_audit/hard_reentry_event_table.md

The audit should explain, per event, why TIM-MARS stayed correct, became wrong, lost the target, or recovered.

Expected columns:

    time_s
    expected_id
    raw_target_id
    tim_mars_id
    best_candidate_id
    current_output_correct
    best_candidate_correct
    current_mars_similarity
    best_candidate_mars_similarity
    decision_state
    decision_reason

## End-of-day status

The four-way comparison is usable for presentation, but the next thesis contribution should focus on improving TIM's decision policy rather than treating the current TIM-MARS result as final.
