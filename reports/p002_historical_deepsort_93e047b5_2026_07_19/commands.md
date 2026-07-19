# P0.2 primary replay and evaluation commands

The exact replay commands are also preserved in each
`tim_replay_metadata.json` file.

Current canonical replay:

    tools/experiments/run_deterministic_tim_replay.py bags/replay/paper_final_deepsort_may_2026_07_03/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_deepsort__tim_off__target_1 bags/replay/p002_historical_deepsort_current_93e047b5_2026_07_19 --config ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml --model models/reid/mars-small128.pb --selected-track-id 1 --image-topic /camera/image_raw --tracks-topic /tracks --raw-target-topic /target --raw-target-mode selected_id --image-width 640 --image-height 640

Preserved July 12 replay:

    tools/experiments/run_deterministic_tim_replay.py bags/replay/paper_final_deepsort_may_2026_07_03/2026-05-14__11-03-26__dataset__tim_v1_hard_reentry_id_switch_raw__tracker_deepsort__tim_off__target_1 bags/replay/p002_historical_deepsort_july12_93e047b5_2026_07_19 --config reports/memory_tim_safety_eval/canonical_deepsort_may_selected_id_1/tim_mars_canonical_config.yaml --model models/reid/mars-small128.pb --selected-track-id 1 --image-topic /camera/image_raw --tracks-topic /tracks --raw-target-topic /target --raw-target-mode selected_id --image-width 640 --image-height 640

Correctness evaluation, applied to each output bag:

    thesis_env/bin/python tools/analysis/evaluate_tim_target_correctness.py <output-bag> --annotations docs/data/annotations/may_hard_reentry/deepsort_hard_reentry.csv --out-dir <report-directory> --step-s 0.05 --raw-topic /target --tim-topic /target_memory_mars --timebase header

Event-type evaluation, applied to each output bag:

    thesis_env/bin/python tools/analysis/evaluate_tim_by_event_type.py <output-bag> --annotations docs/data/annotations/may_hard_reentry/deepsort_hard_reentry.csv --out <report-directory>/by_event_type.csv --dt 0.05 --timebase header --raw-topic /target --tim-topic /target_memory_mars
