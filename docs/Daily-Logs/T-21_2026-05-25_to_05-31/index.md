# Weekly Log - T-21 - 2026-05-25 to 2026-05-31

## Weekly focus

This week focuses on completing a fair four-way comparison for the hard re-entry sequence and defining the next TIM-MARS improvement path.

Comparison methods:

1. Raw OCSORT
2. DeepSORT MARS
3. OCSORT + TIM-HSV
4. OCSORT + TIM-MARS

Core thesis principle remains:

    Correct target > any target

## Completed work

### Four-way comparison

Generated a clean four-panel comparison video:

    reports/four_way_video/hard_reentry_4panel_clean_no_extra_titles.mp4

Generated fair selected-target behaviour table:

    reports/four_way_video/tables/four_way_fair_correctness_percentages.md

Generated runtime/output performance table:

    reports/four_way_video/tables/four_way_runtime_performance_comparison.md

Generated combined PNG table figure:

    reports/four_way_video/tables/four_way_tables_correctness_and_performance.png

### DeepSORT correction

Corrected the DeepSORT MARS interpretation:

- DeepSORT target reference should be target `1`, not target `2`.
- DeepSORT's initial missing period should be interpreted as pre-output / no selected-target availability.
- Once DeepSORT outputs the selected target in this sequence, it remains correct.
- DeepSORT is therefore accurate after output, but delayed and heavier.

### TIM-MARS interpretation

Confirmed that TIM-MARS is not equivalent to DeepSORT.

TIM-MARS:

- uses MARS as a lightweight post-tracker memory cue,
- inherits OCSORT tracks and ID switches,
- does not integrate MARS into global tracker association,
- is faster and more deployable,
- but currently less powerful than DeepSORT for full identity association.

## Current technical conclusion

DeepSORT MARS provides strong identity stability after selected-target output, but has delayed selected-target availability and lower output throughput.

OCSORT + TIM-HSV and OCSORT + TIM-MARS maintain higher throughput and improve selected-target correctness over Raw OCSORT, but TIM-MARS still needs a stronger decision policy to better handle OCSORT ID switches.

## Remaining work this week

### Friday, 2026-05-29

Build a TIM-MARS failure audit for the hard re-entry bag.

Target outputs:

    reports/tim_mars_failure_audit/hard_reentry_event_table.csv
    reports/tim_mars_failure_audit/hard_reentry_event_table.md

### Saturday, 2026-05-30

Create an offline TIM-MARS policy simulator and test candidate improvements.

Target outputs:

    reports/tim_mars_policy_sweep/hard_reentry_policy_comparison.csv
    reports/tim_mars_policy_sweep/hard_reentry_policy_comparison.md

### Sunday, 2026-05-31

Either implement the best safe policy or freeze the implementation plan with evidence.

Possible outputs:

    docs/results/tim_mars/2026-05-31__hard-reentry-policy-audit-and-next-steps.md

## Daily logs

- [2026-05-27 - Four-way comparison, real TIM-MARS, and DeepSORT correction](daily/2026-05-27__four-way-comparison-real-tim-mars-and-deepsort.md)
- [2026-05-28 - TIM-MARS analysis and next improvement plan](daily/2026-05-28__tim-mars-analysis-and-next-improvement-plan.md)
- [2026-05-29 - TIM-MARS failure audit targets](daily/2026-05-29__tim-mars-failure-audit-targets.md)
- [2026-05-30 - TIM-MARS policy simulator targets](daily/2026-05-30__tim-mars-policy-simulator-targets.md)
- [2026-05-31 - TIM-MARS implementation and weekly summary targets](daily/2026-05-31__tim-mars-implementation-and-weekly-summary-targets.md)

## Commit guidance

Do not commit generated videos unless explicitly needed.

Recommended files to stage later:

    docs/Daily-Logs/T-21_2026-05-25_to_05-31/index.md
    docs/Daily-Logs/T-21_2026-05-25_to_05-31/daily/2026-05-27__four-way-comparison-real-tim-mars-and-deepsort.md
    docs/Daily-Logs/T-21_2026-05-25_to_05-31/daily/2026-05-28__tim-mars-analysis-and-next-improvement-plan.md
    docs/Daily-Logs/T-21_2026-05-25_to_05-31/daily/2026-05-29__tim-mars-failure-audit-targets.md
    docs/Daily-Logs/T-21_2026-05-25_to_05-31/daily/2026-05-30__tim-mars-policy-simulator-targets.md
    docs/Daily-Logs/T-21_2026-05-25_to_05-31/daily/2026-05-31__tim-mars-implementation-and-weekly-summary-targets.md

Suggested commit message if committing this documentation:

    28-05-26:"Add four-way comparison logs and TIM-MARS improvement plan."
