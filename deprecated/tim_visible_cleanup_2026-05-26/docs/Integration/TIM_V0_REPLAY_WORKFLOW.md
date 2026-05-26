# TIM-V0 Replay and Analysis Workflow

Date: 2026-05-06

Goal: document the reproducible workflow for analysing TIM-V0 behaviour from recorded live-camera bags.

---

## 1. Analyse a live TIM-V0 bag

Command:

    cd "$THESIS_ROOT"
    BAG="artifacts/bags/live_camera/<bag_name>"
    python3 tools/analysis/analyse_tim_v0_bag.py "$BAG"

Outputs:

- reports/tim_v0/<bag_name>/summary.md
- reports/tim_v0/<bag_name>/target_raw.csv
- reports/tim_v0/<bag_name>/target_memory.csv
- reports/tim_v0/<bag_name>/target_memory_status.csv

---

## 2. Run deterministic ID-switch fault injection

Command:

    python3 tools/analysis/evaluate_tim_v0_fault_injection_batch.py \
      "$BAG" \
      --selected-id 1 \
      --replacement-id 3

Outputs:

- reports/tim_v0_fault_injection_batch/<bag_name>/summary.md
- reports/tim_v0_fault_injection_batch/<bag_name>/summary.csv

Use this when you want a controlled comparison between:

- raw selected-ID target following
- TIM-V0 selected-target memory

---

## 3. Run lost-threshold sensitivity sweep

Command:

    python3 tools/analysis/sweep_tim_v0_fault_thresholds.py \
      "$BAG" \
      --selected-id 1 \
      --replacement-id 3 \
      --thresholds 0.35,0.38,0.40,0.42,0.45,0.50,0.60

Outputs:

- reports/tim_v0_threshold_sweep/<bag_name>/summary.md
- reports/tim_v0_threshold_sweep/<bag_name>/summary.csv

Use this to study the trade-off between:

- aggressive reacquisition
- conservative rejection after loss

---

## 4. Export thesis figures

Command:

    python3 tools/analysis/export_tim_v0_thesis_figures.py

Default output:

- figures/tim_v0/

Main figures:

- TIM-V0 state timeline
- raw target vs TIM-V0 validity
- TIM-V0 latency distribution
- fault-injection validity gain
- fault-injection reacquisition time

---

## 5. Recommended evidence bags

Useful bags currently available:

- 2026-05-05__09-55-39__video__tim_v0_occlusion_01
- 2026-05-06__12-11-17__video__tim_v0_ui_panel_screenshot_01

Use the first for controlled TIM-V0 state/fault-injection evidence.

Use the second for live UI validation, where TIM-V0 maintained target lock after raw target loss.

---

## 6. Interpretation rule

Natural/live bags show practical behaviour and state transitions.

Fault-injection bags show controlled raw-ID baseline versus TIM-V0 comparison.

Do not claim generic MOT improvement.

Report selected-target metrics:

- valid target duration
- LOCKED / UNCERTAIN / LOST / REACQUIRED time
- time to reacquire
- TIM latency
- raw target versus TIM target validity

---

## 7. Minimum reproducibility checklist

For a TIM-V0 result to be reusable, save:

- bag name
- tracker type
- detector/model
- TIM configuration
- analysis command
- summary.md
- relevant figures
- interpretation note

