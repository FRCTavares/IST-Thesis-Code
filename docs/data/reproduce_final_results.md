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
        if not value.startswith(("bags/", "reports/", "docs/data/annotations/")):
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
