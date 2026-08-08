# Reproducing Final Thesis Result Artifacts

This document records how the final thesis result artifacts are organized and how
to verify that the local repository contains the evidence used for the reported
TIM-MARS evaluation.

## Current reproducibility command

The current implementation and frozen development matrix are reproduced with:

    python3 tools/reproduce_tim_mars.py --set development

This command validates source bags, annotations, and frozen hashes; builds with
`tools/thesis_build.sh`; executes the canonical dual-oracle component matrix;
records Git, model, split, configuration, runtime, and child-command
provenance; verifies replay fingerprints; and rejects inconsistent aggregate
CSV, JSON, or Markdown values.

For a preflight without running the matrix:

    python3 tools/reproduce_tim_mars.py --validate-only

The final held-out command is:

    python3 tools/reproduce_tim_mars.py --set final_held_out

That mode intentionally fails until H01-H03 are captured, annotated, frozen,
and accepted by the final-release split validator.

The historical `paper_final_*` artifacts below remain frozen for traceability.
They are not silently treated as current canonical evidence and are not mixed
with results generated from the current implementation.

## Scope

The final result artifacts are documented in:

- `docs/data/final_experiment_inventory.md`

That inventory is the source of truth for promoted final replay bags, reports,
and annotation CSVs.

## Final result tables

The compact thesis-facing result tables are stored in:

- `reports/paper_final_tables_2026_07_04/final_result_tables.md`

These tables separate:

- autonomous selected-target outputs
- annotation-driven DeepSORT diagnostics

The annotation-driven DeepSORT rows are not autonomous baselines. They measure
whether DeepSORT contained the correct physical target track when the correct
target-ID handoff was supplied from annotations.

## Final replay bags

The final replay bags are stored under historical submitted-paper folder names:

- `bags/replay/paper_final_tim_results_2026_07_03/`
- The historical DeepSORT May memory replay bag was deleted during cleanup and cannot currently be reproduced directly from the promoted replay directory. Its source DeepSORT bag remains available for a controlled regeneration.
- `bags/replay/paper_final_deepsort_june_full_2026_07_04/`
- `bags/replay/paper_final_deepsort_june_memory_2026_07_04/`
- `bags/replay/paper_final_deepsort_may_2026_07_03/`

The `paper_final_*` names are frozen for traceability. New thesis reruns should
use the naming contract documented in `bags/README.md`.

## Final reports

The final report directories are:

- `reports/paper_final_tim_results_2026_07_03/`
- `reports/paper_final_deepsort_may_2026_07_03/`
- `reports/paper_final_deepsort_may_memory_2026_07_03/`
- `reports/paper_final_deepsort_june_full_2026_07_04/`
- `reports/paper_final_deepsort_june_memory_2026_07_04/`
- `reports/paper_final_method_comparison_2026_07_03/`
- `reports/paper_final_sequence_audit_2026_07_04/`
- `reports/paper_final_tables_2026_07_04/`

## Final annotations

The final annotation CSVs are:

- `docs/data/annotations/may_hard_reentry/bytetrack_hard_reentry.csv`
- `docs/data/annotations/may_hard_reentry/deepsort_hard_reentry.csv`
- `docs/data/annotations/june_hard_sequences/seq01_bytetrack.csv`
- `docs/data/annotations/june_hard_sequences/seq03_bytetrack.csv`
- `docs/data/annotations/june_hard_sequences/seq04_bytetrack.csv`
- `docs/data/annotations/june_hard_sequences/seq03_deepsort.csv`
- `docs/data/annotations/june_hard_sequences/seq04_deepsort.csv`

Non-final annotations kept for provenance are listed in
`docs/data/final_experiment_inventory.md`.

## Final P030 broader-sequence evidence (Issue #30)

Canonical thesis-facing summary:
`docs/results/selected_target_tracking/p030_broader_sequences_summary.md`.
Full engineering record: `docs/issues/p1-12-broader-sequences.md`. The
full list of promoted P030 report/manifest/figure paths is in
`docs/data/final_experiment_inventory.md`; they are covered by the same
`Local verification` check below (its path-prefix filter includes
`docs/data/external_benchmark/` and `artifacts/reports/`).

To regenerate the P030 evidence from the frozen manifest and existing
capture/replay bags (read-only with respect to TIM-MARS/detector/
ByteTrack/sequence-selection; this does not rerun any Hailo capture):

    cd ~/Desktop/Thesis-Code
    python3 tools/analysis/aggregate_first_phase_report.py \
      --output artifacts/reports/p030_broader_sequences/first_phase_aggregate.json
    python3 tools/analysis/aggregate_oracle_report.py \
      --output artifacts/reports/p030_broader_sequences/oracle_aggregate.json
    python3 tools/analysis/bbox_size_stratified_report.py \
      --output artifacts/reports/p030_broader_sequences/bbox_size_stratified_report.json
    python3 tools/analysis/render_bbox_size_report_outputs.py

Regenerating a specific sequence's underlying frame report (only needed if
a report file is missing, not for routine verification) uses
`tools/analysis/run_external_sequence_report.py`'s `build_report()`
against that sequence's existing capture bag under
`bags/replay/p030_broader_sequences_external_2026_08_07/` (full pipeline)
or `bags/replay/p030_broader_sequences_oracle_2026_08_07/` (oracle,
built from `tools/analysis/build_oracle_candidate_bag.py`); see
`docs/issues/p1-12-broader-sequences.md` for the exact per-sequence
commands used.

## Final P031 parameter-sensitivity evidence (Issue #31)

Canonical thesis-facing summary:
`docs/results/selected_target_tracking/p031_parameter_sensitivity_summary.md`.
Full engineering record: `docs/issues/p1-13-parameter-sensitivity.md`. Tracked
provenance/aggregate/figure copies (with `SHA256SUMS`) are in
`docs/results/selected_target_tracking/p031_parameter_sensitivity_development/`.

To regenerate the 116-cell matrix, aggregate tables, and figures from the
frozen manifest, canonical config, and existing source bags (read-only with
respect to TIM-MARS/detector/ByteTrack/sequence-selection):

    cd ~/Desktop/Thesis-Code
    source /opt/ros/jazzy/setup.bash
    source ros2_ws/install/setup.bash
    for seq in dev_may_hard_reentry dev_june_seq01 dev_june_seq03 dev_june_seq04; do
      thesis_env/bin/python3 tools/experiments/run_tim_parameter_sensitivity.py \
        --run --resume --sequence "$seq"
    done
    thesis_env/bin/python3 tools/analysis/aggregate_parameter_sensitivity_report.py
    thesis_env/bin/python3 tools/analysis/plot_parameter_sensitivity.py

The aggregator refuses to run if any of the 116 expected
(configuration, sequence) cells is missing (`MissingCellError`), using the
same `expected_cells`/`missing_cells` helpers the runner itself uses, so the
completeness contract cannot silently drift between execution and
aggregation.

Sourcing the ROS 2 overlay before invoking the runner is required in a
non-interactive shell (SSH command execution does not source `.bashrc`); the
first `dev_june_seq01` attempt during this run failed with
`ModuleNotFoundError: No module named 'rosbag2_py'` for exactly this reason,
before any cell was written, and was corrected by sourcing the overlay
explicitly rather than by changing any experiment parameter.

## Local verification

Run from the repository root:

    cd ~/Desktop/Thesis-Code || return 1 2>/dev/null || true

    python3 - <<'PYVERIFY'
    from pathlib import Path
    import re

    inventory = Path("docs/data/final_experiment_inventory.md")
    text = inventory.read_text()

    missing = []
    for match in re.finditer(r"`([^`]+)`", text):
        value = match.group(1)
        if not value.startswith((
            "bags/",
            "reports/",
            "docs/data/annotations/",
            "docs/data/external_benchmark/",
            "artifacts/reports/",
        )):
            continue
        if "*" in value:
            continue
        path = Path(value.rstrip("/"))
        if not path.exists():
            missing.append(value)

    if missing:
        print("Missing final inventory paths:")
        for value in missing:
            print(f"- {value}")
        raise SystemExit(1)

    print("All concrete final inventory paths exist.")
    PYVERIFY

Also verify the final report directories are non-empty:

    cd ~/Desktop/Thesis-Code || return 1 2>/dev/null || true

    for d in \
      reports/paper_final_tim_results_2026_07_03 \
      reports/paper_final_deepsort_may_2026_07_03 \
      reports/paper_final_deepsort_may_memory_2026_07_03 \
      reports/paper_final_deepsort_june_full_2026_07_04 \
      reports/paper_final_deepsort_june_memory_2026_07_04 \
      reports/paper_final_method_comparison_2026_07_03 \
      reports/paper_final_sequence_audit_2026_07_04 \
      reports/paper_final_tables_2026_07_04
    do
      count=$(find "$d" -type f | wc -l)
      echo "$count files  $d"
    done

## Bag policy

Bag roles, deletion policy, and naming conventions are documented in:

- `bags/README.md`

Source bags are protected. Replay, review, temporary, and UI-generated bags are
disposable unless explicitly promoted in `docs/data/final_experiment_inventory.md`.
