"""Aggregate the frozen Issue #31 (P1.13) 29x4 parameter-sensitivity matrix
into one report.

Mirrors the structure of aggregate_first_phase_report.py: it reads the
already-generated, already-evaluated per-cell report.json files produced by
tools/experiments/run_tim_parameter_sensitivity.py --run, and combines them
into per-sequence, all-cell, and cross-sequence-aggregate tables plus
per-dimension baseline-relative trade-off tables. It does not rerun TIM-MARS,
does not re-evaluate any bag, and does not alter any per-cell report.

Refuses to run if any of the 116 expected cells is missing, using the same
frozen expected_cells()/missing_cells() helpers the runner itself uses, so
the completeness contract cannot silently drift between the runner and this
aggregator.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools" / "experiments"))

from run_tim_parameter_sensitivity import (  # noqa: E402
    expected_cells,
    missing_cells,
)

REPORT_DIR = REPO_ROOT / "reports" / "p031_parameter_sensitivity_5b340c2b_2026-08-08"
LOCK_PATH = REPORT_DIR / "parameter_sensitivity_lock.json"
SEQ_DIR = REPORT_DIR / "sequences"
OUT_DIR = REPORT_DIR / "aggregate"

DURATION_FIELDS = [
    "correct_target_duration_s",
    "wrong_target_duration_s",
    "lost_target_duration_s",
    "target_absent_but_output_valid_duration_s",
    "no_target_selected_duration_s",
]


def load_lock() -> dict[str, Any]:
    return json.loads(LOCK_PATH.read_text())


def load_cell_report(sequence_id: str, config_id: str) -> dict[str, Any]:
    path = SEQ_DIR / sequence_id / config_id / "report.json"
    return json.loads(path.read_text())


def duration_row(stream_metrics: dict[str, Any]) -> dict[str, float]:
    return {field: float(stream_metrics[field]) for field in DURATION_FIELDS}


def build_all_cells_table(
    lock: dict[str, Any],
) -> list[dict[str, Any]]:
    sequences = lock["development_sequence_ids"]
    configs = lock["materialized_configs"]
    rows: list[dict[str, Any]] = []
    for sequence_id in sequences:
        for config in configs:
            config_id = config["id"]
            report = load_cell_report(sequence_id, config_id)
            raw = duration_row(report["duration_metrics"]["raw_target"])
            tim = duration_row(report["duration_metrics"]["tim_target_memory"])
            ep_tim = report["episode_metrics"]["tim_target_memory"]
            status = report.get("status_recovery_metrics", {})
            mem = report.get("memory_event_metrics", {})
            rows.append(
                {
                    "sequence_id": sequence_id,
                    "config_id": config_id,
                    "dimension_id": config["dimension_id"],
                    "order": config["order"],
                    "overrides": json.dumps(config["overrides"], sort_keys=True),
                    "raw_correct_s": raw["correct_target_duration_s"],
                    "raw_wrong_s": raw["wrong_target_duration_s"],
                    "raw_lost_s": raw["lost_target_duration_s"],
                    "raw_wrong_ratio": float(
                        report["duration_metrics"]["raw_target"]["wrong_target_ratio"]
                    ),
                    "raw_lost_ratio": float(
                        report["duration_metrics"]["raw_target"]["lost_target_ratio"]
                    ),
                    "tim_correct_s": tim["correct_target_duration_s"],
                    "tim_wrong_s": tim["wrong_target_duration_s"],
                    "tim_lost_s": tim["lost_target_duration_s"],
                    "tim_absent_valid_s": tim[
                        "target_absent_but_output_valid_duration_s"
                    ],
                    "tim_no_selection_s": tim["no_target_selected_duration_s"],
                    "tim_correct_ratio": float(
                        report["duration_metrics"]["tim_target_memory"][
                            "correct_target_ratio"
                        ]
                    ),
                    "tim_wrong_ratio": float(
                        report["duration_metrics"]["tim_target_memory"][
                            "wrong_target_ratio"
                        ]
                    ),
                    "tim_lost_ratio": float(
                        report["duration_metrics"]["tim_target_memory"][
                            "lost_target_ratio"
                        ]
                    ),
                    "tim_wrong_burst_count": ep_tim["wrong_target_burst_count"],
                    "tim_wrong_handover_count": ep_tim["wrong_handover_count"],
                    "tim_longest_wrong_burst_s": ep_tim["longest_wrong_target_burst_s"],
                    "recovery_attempt_count": status.get("recovery_attempt_count"),
                    "correct_candidate_suppressed_duration_s": status.get(
                        "correct_candidate_suppressed_duration_s"
                    ),
                    "hard_negative_contamination_count": mem.get(
                        "hard_negative_contamination_count"
                    ),
                    "positive_memory_contamination_count": mem.get(
                        "positive_memory_contamination_count"
                    ),
                    "total_memory_contamination_count": mem.get(
                        "total_memory_contamination_count"
                    ),
                }
            )
    return rows


def add_within_sequence_deltas(rows: list[dict[str, Any]]) -> None:
    baseline_by_sequence = {
        row["sequence_id"]: row for row in rows if row["config_id"] == "baseline"
    }
    for row in rows:
        baseline = baseline_by_sequence[row["sequence_id"]]
        row["delta_wrong_s_vs_baseline"] = row["tim_wrong_s"] - baseline["tim_wrong_s"]
        row["delta_lost_s_vs_baseline"] = row["tim_lost_s"] - baseline["tim_lost_s"]
        row["delta_correct_s_vs_baseline"] = (
            row["tim_correct_s"] - baseline["tim_correct_s"]
        )


def build_aggregate_table(
    lock: dict[str, Any], all_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    configs = lock["materialized_configs"]
    by_config: dict[str, list[dict[str, Any]]] = {}
    for row in all_rows:
        by_config.setdefault(row["config_id"], []).append(row)

    agg_rows: list[dict[str, Any]] = []
    for config in configs:
        config_id = config["id"]
        cell_rows = by_config[config_id]
        raw_correct = sum(r["raw_correct_s"] for r in cell_rows)
        raw_wrong = sum(r["raw_wrong_s"] for r in cell_rows)
        raw_lost = sum(r["raw_lost_s"] for r in cell_rows)
        tim_correct = sum(r["tim_correct_s"] for r in cell_rows)
        tim_wrong = sum(r["tim_wrong_s"] for r in cell_rows)
        tim_lost = sum(r["tim_lost_s"] for r in cell_rows)
        tim_absent = sum(r["tim_absent_valid_s"] for r in cell_rows)
        tim_noselect = sum(r["tim_no_selection_s"] for r in cell_rows)
        raw_total = raw_correct + raw_wrong + raw_lost
        tim_total = tim_correct + tim_wrong + tim_lost + tim_absent + tim_noselect
        agg_rows.append(
            {
                "config_id": config_id,
                "dimension_id": config["dimension_id"],
                "order": config["order"],
                "overrides": json.dumps(config["overrides"], sort_keys=True),
                "raw_correct_s": round(raw_correct, 3),
                "raw_wrong_s": round(raw_wrong, 3),
                "raw_lost_s": round(raw_lost, 3),
                "raw_wrong_ratio": round(raw_wrong / raw_total, 4) if raw_total else 0.0,
                "raw_lost_ratio": round(raw_lost / raw_total, 4) if raw_total else 0.0,
                "tim_correct_s": round(tim_correct, 3),
                "tim_wrong_s": round(tim_wrong, 3),
                "tim_lost_s": round(tim_lost, 3),
                "tim_absent_valid_s": round(tim_absent, 3),
                "tim_no_selection_s": round(tim_noselect, 3),
                "tim_correct_ratio": round(tim_correct / tim_total, 4) if tim_total else 0.0,
                "tim_wrong_ratio": round(tim_wrong / tim_total, 4) if tim_total else 0.0,
                "tim_lost_ratio": round(tim_lost / tim_total, 4) if tim_total else 0.0,
                "tim_wrong_burst_count_sum": sum(
                    r["tim_wrong_burst_count"] for r in cell_rows
                ),
                "recovery_attempt_count_sum": sum(
                    r["recovery_attempt_count"] or 0 for r in cell_rows
                ),
                "total_memory_contamination_count_sum": sum(
                    r["total_memory_contamination_count"] or 0 for r in cell_rows
                ),
            }
        )

    baseline = next(r for r in agg_rows if r["config_id"] == "baseline")
    for row in agg_rows:
        row["delta_wrong_s_vs_baseline"] = round(
            row["tim_wrong_s"] - baseline["tim_wrong_s"], 3
        )
        row["delta_lost_s_vs_baseline"] = round(
            row["tim_lost_s"] - baseline["tim_lost_s"], 3
        )
        row["delta_correct_s_vs_baseline"] = round(
            row["tim_correct_s"] - baseline["tim_correct_s"], 3
        )
    return agg_rows


def build_dimension_table(agg_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_order = sorted(agg_rows, key=lambda r: r["order"])
    return [
        {
            "order": r["order"],
            "dimension_id": r["dimension_id"] or "canonical",
            "config_id": r["config_id"],
            "tim_wrong_s": r["tim_wrong_s"],
            "tim_lost_s": r["tim_lost_s"],
            "tim_wrong_ratio": r["tim_wrong_ratio"],
            "tim_lost_ratio": r["tim_lost_ratio"],
            "delta_wrong_s_vs_baseline": r["delta_wrong_s_vs_baseline"],
            "delta_lost_s_vs_baseline": r["delta_lost_s_vs_baseline"],
        }
        for r in by_order
    ]


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"no rows to write for {path}")
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=list(rows[0].keys()), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")


def scan_completed_cells(sequences: list[str]) -> set[tuple[str, str]]:
    completed: set[tuple[str, str]] = set()
    for sequence_id in sequences:
        seq_dir = SEQ_DIR / sequence_id
        if not seq_dir.is_dir():
            continue
        for config_dir in seq_dir.iterdir():
            if (config_dir / "report.json").is_file():
                completed.add((config_dir.name, sequence_id))
    return completed


def main() -> int:
    lock = load_lock()
    sequences = lock["development_sequence_ids"]
    configurations = lock["materialized_configs"]

    expected = expected_cells(
        configurations, [{"id": s} for s in sequences]
    )
    completed = scan_completed_cells(sequences)
    missing = missing_cells(expected, completed)
    if missing:
        print(f"[error] {len(missing)} missing cells, refusing to aggregate:")
        for cfg, seq in sorted(missing):
            print(f"  {seq}/{cfg}")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    all_rows = build_all_cells_table(lock)
    add_within_sequence_deltas(all_rows)
    assert len(all_rows) == 116, f"expected 116 rows, got {len(all_rows)}"
    write_csv(OUT_DIR / "matrix_all_sequences.csv", all_rows)
    write_json(OUT_DIR / "matrix_all_sequences.json", all_rows)

    agg_rows = build_aggregate_table(lock, all_rows)
    assert len(agg_rows) == 29, f"expected 29 aggregate rows, got {len(agg_rows)}"
    write_csv(OUT_DIR / "matrix_aggregate.csv", agg_rows)
    write_json(OUT_DIR / "matrix_aggregate.json", agg_rows)

    dim_rows = build_dimension_table(agg_rows)
    write_csv(OUT_DIR / "dimension_tradeoff.csv", dim_rows)
    write_json(OUT_DIR / "dimension_tradeoff.json", dim_rows)

    print(f"[ok] aggregated 116 cells / 29 configs / {len(sequences)} sequences")
    print(f"[ok] wrote: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
