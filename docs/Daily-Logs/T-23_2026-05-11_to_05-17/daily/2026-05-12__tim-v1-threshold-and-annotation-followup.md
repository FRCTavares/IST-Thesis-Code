# Daily Plan - 2026-05-12 - TIM-V1 Annotation, Threshold Tuning, and Report Consolidation

## Goal

Turn today's TIM-V1 implementation and evidence into a cleaner thesis-ready result package.

The main priority is not more live coding. The priority is to refine the evaluation so the claims are defensible.

## Starting state

TIM-V1 is implemented and pushed.

Current available evidence:

- TIM-V1J two-person ambiguity bag
- TIM-V1M appearance-critical crossing bag
- TIM-V1 appearance diagnostics reports
- first manual correctness annotation for TIM-V1J
- first-pass manual annotation for TIM-V1M
- offline threshold sweep script started
- Overleaf TIM-V1 document drafted

## Priority 1 - Check repository state

Commands:

    cd "$THESIS_ROOT"
    git status
    git log --oneline -20

Expected:

- working tree clean, or only today's final log/plan changes pending

If these are pending, commit them first:

- tools/analysis/sweep_tim_v1_thresholds_offline.py
- docs/annotations/tim_v1m_appearance_critical_crossing/target_correctness_annotations.csv
- docs/annotations/tim_v1m_appearance_critical_crossing/manual_review_notes.md
- docs/Daily-Logs/T-23_2026-05-11_to_05-17/daily/2026-05-11__tim-v1a-core-appearance.md

## Priority 2 - Refine TIM-V1M annotation

Open the TIM-V1M overlay videos and refine the intervals.

Bag:

    artifacts/bags/live_camera/2026-05-11__11-31-27__video__tim_v1m_appearance_critical_crossing

Current first-pass annotation:

    docs/annotations/tim_v1m_appearance_critical_crossing/target_correctness_annotations.csv

Manual facts already known:

- ID 1: selected person before occlusion
- ID 9: selected person during hard re-entry
- ID 10: selected person after reacquisition
- ID 11: selected person later
- ID 6: distractor

Questions to answer:

- When exactly does ID 9 become visible and correct?
- Is the selected person fully invisible or partially visible during the long occlusion?
- When does ID 10 replace ID 9?
- When does ID 11 replace ID 10?
- Is there any interval where TIM outputs the distractor?

Deliverable:

- refined target_correctness_annotations.csv
- short note explaining any uncertain intervals

## Priority 3 - Rerun TIM-V1M threshold sweep

After refining the annotation, rerun:

    python3 tools/analysis/sweep_tim_v1_thresholds_offline.py artifacts/bags/live_camera/2026-05-11__11-31-27__video__tim_v1m_appearance_critical_crossing --annotations docs/annotations/tim_v1m_appearance_critical_crossing/target_correctness_annotations.csv --out-dir reports/tim_v1_threshold_sweep --thresholds 0.60 0.55 0.50 0.45 --step-s 0.05

Inspect:

    reports/tim_v1_threshold_sweep/2026-05-11__11-31-27__video__tim_v1m_appearance_critical_crossing/summary.md

Expected interpretation to verify:

- 0.60 is conservative
- 0.50 to 0.55 may be better
- 0.45 likely increases wrong-target risk

Deliverable:

- updated threshold sweep result
- clear recommended candidate range for accept_score_lost

Do not change the live default yet unless the evidence is repeated on more bags.

## Priority 4 - Update Overleaf TIM-V1 document

Add the new section:

- Hard Re-Entry and LOST-State Threshold Sweep

Make sure the document is honest:

- TIM-V1 improves over raw /target in the two-person run
- appearance was active and used
- replay ablation showed appearance did not change TIM-V1J correctness
- TIM-V1M shows the acceptance policy is now the important tuning point
- more bags are required before final claims

Avoid overclaiming.

## Priority 5 - Prepare supervisor update

Create a concise update message with:

- what was implemented
- what was tested
- best result table
- failure/tuning result
- next plan

Main result to mention:

| Metric | Raw /target | TIM /target_memory |
|---|---:|---:|
| correct ratio | 0.585 | 0.959 |
| wrong ratio | 0.000 | 0.005 |
| lost ratio | 0.415 | 0.036 |

Important nuance:

- appearance is implemented and active
- current strongest evidence is for selected-target memory overall
- appearance-specific benefit still needs repeated and harder controlled tests

## Optional Priority 6 - Record one more two-person bag

Only do this after annotation/report cleanup.

New bag should be more controlled:

- both people visible from the start
- two IDs visible before selecting target
- different shirt colours
- one crossing event
- one full separation after crossing
- one short disappearance/re-entry

Command:

    ./tools/start_live_stack.sh --profile safe-camera --target-memory --target-memory-appearance --target-memory-appearance-image-topic /camera/dashboard --record-video --bag-tag tim_v1_next_two_person_repeat

## Definition of done for 2026-05-12

Minimum:

- TIM-V1M annotation refined
- threshold sweep rerun
- Overleaf TIM-V1 document updated
- supervisor update drafted

Good:

- one additional two-person bag recorded
- correctness annotation started for that bag

Stop condition:

Do not start TIM-V2 or ROI refine yet. Finish TIM-V1 evaluation first.
---

## TIM-V1M annotation refined and threshold sweep rerun

Refined the manual correctness annotation for:

- `2026-05-11__11-31-27__video__tim_v1m_appearance_critical_crossing`

Main correction:

- The previous annotation treated a long interval as mostly occluded/ambiguous.
- Manual video review confirmed that from approximately 56.11 s onward, the selected target is clearly visible as ID 11 while the distractor remains ID 6.
- Therefore, accepting ID 6 during this interval is a wrong-target failure, not a hidden-target case.

Final manual ID mapping:

- ID 1: selected target before crossing.
- ID 6: distractor.
- ID 9: selected target after first re-entry.
- ID 10: selected target after second re-entry.
- ID 11: selected target in the final visible interval.

Reran the offline `accept_score_lost` sweep.

Result:

| accept_score_lost | correct ratio | wrong ratio | lost ratio | correct [s] | wrong [s] | lost [s] |
|---:|---:|---:|---:|---:|---:|---:|
| 0.60 | 0.308 | 0.000 | 0.692 | 15.200 | 0.000 | 34.130 |
| 0.55 | 0.603 | 0.000 | 0.397 | 29.750 | 0.000 | 19.580 |
| 0.50 | 0.788 | 0.000 | 0.212 | 38.870 | 0.000 | 10.460 |
| 0.45 | 0.603 | 0.170 | 0.227 | 29.750 | 8.400 | 11.180 |

Interpretation:

- The default `accept_score_lost=0.60` is too conservative for this hard re-entry case.
- `0.50` gives the best result on this bag.
- `0.45` is too permissive and introduces clear wrong-target duration.
- This supports a candidate tuning range around `0.50-0.55`, but the live default should not be changed based on a single bag.

Conclusion:

TIM-V1M is now a useful threshold-stress case. It shows both sides of the trade-off:

- conservative thresholds delay reacquisition of the true target,
- permissive thresholds can lock onto the distractor.


---

## TIM-V1M appearance ON/OFF ablation completed

Extended the offline TIM-V1 threshold sweep script with:

- `--appearance-enabled`
- `--no-appearance`

This allows a direct TIM-V0-style geometry-only comparison against TIM-V1 appearance-assisted matching on the same recorded bag and annotation.

Ran the ablation on:

- `2026-05-11__11-31-27__video__tim_v1m_appearance_critical_crossing`

Main result:

| Method | accept_score_lost | Correct ratio | Wrong ratio | Lost ratio |
|---|---:|---:|---:|---:|
| TIM-V0, appearance OFF | 0.60 | 0.308 | 0.000 | 0.692 |
| TIM-V0, appearance OFF | 0.55 | 0.308 | 0.000 | 0.692 |
| TIM-V0, appearance OFF | 0.50 | 0.603 | 0.000 | 0.397 |
| TIM-V0, appearance OFF | 0.45 | 0.603 | 0.000 | 0.397 |
| TIM-V1, appearance ON | 0.60 | 0.308 | 0.000 | 0.692 |
| TIM-V1, appearance ON | 0.55 | 0.603 | 0.000 | 0.397 |
| TIM-V1, appearance ON | 0.50 | 0.788 | 0.000 | 0.212 |
| TIM-V1, appearance ON | 0.45 | 0.603 | 0.170 | 0.227 |

Interpretation:

- TIM-V1 appearance improves over TIM-V0 at `accept_score_lost=0.50`.
- Correct ratio improves from 0.603 to 0.788.
- Lost ratio decreases from 0.397 to 0.212.
- Wrong ratio remains 0.000 at 0.50.
- At 0.45, TIM-V1 becomes too permissive and introduces wrong-target duration.

Conclusion:

This is the first useful TIM-V0 versus TIM-V1 evidence. It supports the claim that appearance can improve reacquisition on the hard crossing bag, but only with an appropriate LOST-state acceptance threshold.
