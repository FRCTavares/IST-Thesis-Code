# Hard re-entry OC-SORT target 1 annotations

## Current annotation to use

Use:

    target_correctness_annotations_manual_review_v2.csv

This is the current corrected annotation for the hard re-entry sequence.

## Manual review evidence

The clean switch review is stored in:

    manual_switch_review_v2_clean.csv

It was produced from bag-rendered review clips generated directly from the MCAP bag with:

- `/camera/image_raw`
- `/tracks`
- `/target`
- `/target_memory`

Colour convention in the review clips:

- green: TIM `/target_memory`
- red: raw `/target`
- yellow: raw and TIM overlap
- grey: other tracks

## Superseded material

Older candidate annotations and intermediate review notes were moved to the root `deprecated/` folder.

Do not use the old candidate annotation for final evaluation. It was superseded because the later bag-rendered review with target boxes showed that events 01 to 03 were still wrong-target intervals, not correct TIM recoveries.
