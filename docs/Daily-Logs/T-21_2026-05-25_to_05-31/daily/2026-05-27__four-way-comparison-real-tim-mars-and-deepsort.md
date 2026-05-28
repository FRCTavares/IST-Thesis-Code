# Daily Log - 2026-05-27 - Four-way comparison, DeepSORT correction, and real TIM-MARS validation

## Main objective

Prepare a supervisor-ready comparison between:

1. Raw OCSORT
2. DeepSORT MARS
3. OCSORT + TIM-HSV
4. OCSORT + TIM-MARS

The goal was to compare selected-target correctness and runtime behaviour on the hard re-entry sequence.

## Work completed

### Four-panel comparison video

Generated the clean four-panel comparison video:

    reports/four_way_video/hard_reentry_4panel_clean_no_extra_titles.mp4

Panels:

- Raw OCSORT
- DeepSORT MARS
- OCSORT + TIM-HSV
- OCSORT + TIM-MARS

The final grid removed the extra method titles added by the grid script and kept only the audit overlays already present in each individual panel.

### DeepSORT MARS rerun from image_raw

Reran DeepSORT MARS from the recorded `/camera/image_raw` dataset instead of relying on older DeepSORT outputs.

Final DeepSORT panel used:

    reports/videos/selected_target_comparison_2026-05-28/four_panel_real_tim_mars/02_deepsort_mars_fresh_image_raw_target1_id1_corrected_status_audit.mp4

Key correction:

- The DeepSORT selected target should be target ID `1`, not target `2`.
- The older annotation still contained an interval where the selected black-shirt target was treated as ID `70`.
- For the fresh DeepSORT target-1 rerun, visual audit confirmed that ID `1` corresponds to the selected black-shirt target.
- A corrected DeepSORT annotation was created:

    docs/annotations/2026-05-14__hard_reentry_deepsort_mars_target1/target_correctness_annotations_deepsort_target1_fresh_id1_v3.csv

### DeepSORT interpretation corrected

The first correctness table incorrectly treated DeepSORT's initial no-output period as lost tracking.

After visual audit, the interpretation was corrected:

- DeepSORT MARS has a long pre-output / no selected-target period.
- Once DeepSORT starts outputting the selected target, it remains correct in this sequence.
- Therefore, DeepSORT's weakness in this comparison is delayed selected-target availability and lower throughput, not wrong-target following after output.

Final fair interpretation:

    DeepSORT MARS is conservative during initialisation. It delays selected-target output until a stable identity is available. In this run, once the selected target was output, it remained correct.

### TIM-MARS validated as real ROS output

Real TIM-MARS output was used from the ROS replay bag:

    artifacts/bags/eval_matrix/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_ocsort__tim_mars__target_1__r4

TIM-MARS topic:

    /target_memory_mars

This confirmed that the TIM-MARS panel and table use a real ROS node output, not only an offline simulation.

### Tables generated

Generated final percentage-based comparison tables:

    reports/four_way_video/tables/four_way_fair_correctness_percentages.md
    reports/four_way_video/tables/four_way_fair_correctness_percentages.csv

Generated runtime/output-rate comparison tables:

    reports/four_way_video/tables/four_way_runtime_performance_comparison.md
    reports/four_way_video/tables/four_way_runtime_performance_comparison.csv

Generated combined table image for slides / Canva:

    reports/four_way_video/tables/four_way_tables_correctness_and_performance.png

## Main technical conclusion

DeepSORT MARS is very accurate once selected-target output becomes available, but it is heavier and slower. It also has delayed selected-target availability in this replay.

OCSORT + TIM-HSV and OCSORT + TIM-MARS maintain higher output throughput and improve selected-target correctness over Raw OCSORT, but the current TIM-MARS policy does not yet exploit MARS as deeply as DeepSORT because MARS is used as a lightweight post-tracker memory cue, not as the tracker association mechanism itself.

## Current limitation identified

TIM-MARS is not yet better than DeepSORT in this hard re-entry bag because:

- DeepSORT integrates MARS embeddings directly into the tracking association stage.
- TIM-MARS receives OCSORT tracks after OCSORT has already produced ID switches.
- TIM-MARS must decide after the fact whether a new tracker ID corresponds to the selected person.
- The current TIM policy is still too sticky and does not promote the correct re-entry candidate aggressively enough.

## Next direction

The next TIM improvement should not be just "add MARS". The next step is to improve the TIM decision policy:

1. Detect when the current output becomes appearance-inconsistent.
2. Promote a stable appearance-matched candidate after an ID switch.
3. Suppress output during ambiguous crossings.
4. Add stronger diagnostics for why TIM stays wrong, recovers, or refuses to switch.
