# TIM-V2E Reacquisition Diagnostics

Date: 2026-05-23  
Scope: offline diagnostic review of TIM-V2E reacquisition frames on the two current standard scenarios.

## Purpose

This diagnostic checks whether TIM-V2E reacquisition events are actually useful, or whether they create wrong-target output.

The key question is:

> When TIM-V2E overrides the raw selected ID with a reacquired candidate, is the reacquired candidate correct?

## Inputs

Existing TIM-V2E timeline files:

- `reports/tim_v2_embedding/v2e_hybrid_hard_reentry_runtime_margin010_thr0_high03_c3/timeline.csv`
- `reports/tim_v2_embedding/v2e_hybrid_critical_crossing_runtime_margin010_thr0_high03_c3/timeline.csv`

Existing TIM-V2E summaries:

- hard re-entry:
  - correct_s: 72.553
  - wrong_s: 16.901
  - lost_s: 15.090
  - reacquired_s: 4.708

- critical crossing:
  - correct_s: 29.971
  - wrong_s: 0.046
  - lost_s: 9.839
  - reacquired_s: 18.857

## Diagnostic result

### Hard re-entry

- timeline rows: 895
- reacquired frames: 39
- reacquired output IDs: 96 and 113
- all inspected reacquisition intervals were labelled `correct`
- no wrong reacquisition interval was observed

Summary:

| Output ID | Correct ID | Label | Event |
|---:|---:|---|---|
| 96 | 96 | correct | wrong_target_interval |
| 113 | 113 | correct | wrong_target_interval |

### Critical crossing

- timeline rows: 932
- reacquired frames: 414
- reacquired output IDs: 9, 10, and 11
- all inspected reacquisition intervals were labelled `correct`
- no wrong reacquisition interval was observed

Summary:

| Output ID | Correct ID | Label | Event |
|---:|---:|---|---|
| 9 | 9 | correct | hard_reentry |
| 10 | 10 | correct | reentry_id_switch |
| 11 | 11 | correct | visible_but_wrong_best_candidate / late_reentry |

## Interpretation

TIM-V2E reacquisition is useful in the current standard cases.

The raw selected ID often remains attached to the wrong tracker ID. TIM-V2E suppresses that raw ID and outputs a high-similarity candidate instead. In the inspected reacquisition intervals, this candidate matches the annotated correct ID.

This supports the current TIM-V2E claim:

> TIM-V2E reduces wrong-target following by using learned appearance similarity to reject appearance-impossible selected IDs and reacquire the correct target candidate.

## Negative branch: V2F conservative probation

A V2F-style conservative probation branch was tested and rejected on 2026-05-23.

The tested idea was:

- keep V2E-style suppression;
- add a non-control-valid CANDIDATE/probation phase before reacquisition;
- only output the candidate after stricter confirmation.

This was rejected because even an equivalence-style configuration failed to reproduce V2E:

| Scenario | Method | correct_s | wrong_s | lost_s |
|---|---|---:|---:|---:|
| hard re-entry | V2E | 72.553 | 16.901 | 15.090 |
| hard re-entry | V2F equivalence attempt | 69.897 | 16.901 | 17.746 |
| critical crossing | V2E | 29.971 | 0.046 | 9.839 |
| critical crossing | V2F equivalence attempt | 17.764 | 0.046 | 22.046 |

Conclusion:

> Do not pursue non-control-valid candidate probation as the next TIM-V2 improvement. It converts useful correct reacquisition time into LOST time.

## Current decision

TIM-V2E remains the current best candidate.

Next useful work should focus on documenting and validating V2E, not replacing it with a stricter candidate-probation policy.
