#!/usr/bin/env python3
"""Render CSV and figure outputs from the bbox-size-stratified report JSON.

Read-only, deterministic rendering of an already-generated
``bbox_size_stratified_report.json`` (produced by
``bbox_size_stratified_report.py``) into a flat CSV table and two PNG
figures. Does not recompute anything, does not touch TIM-MARS or any
frozen configuration.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = (
    ROOT
    / "artifacts"
    / "reports"
    / "p030_broader_sequences"
    / "bbox_size_stratified_report.json"
)
DEFAULT_OUTPUT_DIR = (
    ROOT / "artifacts" / "reports" / "p030_broader_sequences"
)


def flatten_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    bin_labels = [b["label"] for b in report["bins"]]
    rows: list[dict[str, Any]] = []

    for mode, per_sequence in (
        ("full_pipeline", report["full_pipeline"]),
        ("oracle_candidate", report["oracle_candidate"]),
    ):
        for sequence_id, data in per_sequence.items():
            distribution = data["size_distribution"]
            presence = data["candidate_presence_by_bin"]
            for label in bin_labels:
                row: dict[str, Any] = {
                    "mode": mode,
                    "sequence_id": sequence_id,
                    "status": data["status"],
                    "bin": label,
                    "gt_frames": distribution["counts_by_bin"][label],
                    "candidate_present_frames": presence[label][
                        "with_candidate"
                    ],
                    "candidate_present_fraction": presence[label][
                        "fraction_with_candidate"
                    ],
                }
                for stream_key, prefix in (
                    ("raw_by_bin", "raw"),
                    ("tim_by_bin", "tim"),
                ):
                    by_bin = data.get(stream_key)
                    summary = by_bin[label] if by_bin else None
                    if summary is None:
                        row[f"{prefix}_total_frames"] = 0
                        row[f"{prefix}_correct_fraction"] = None
                        row[f"{prefix}_wrong_person_count"] = None
                        for outcome_name in (
                            "correct_target",
                            "correct_same_person_recovery",
                            "safe_suppression",
                            "target_candidate_absent",
                            "distractor_selection",
                            "stale_id_transfer",
                            "ambiguous_candidate",
                        ):
                            row[f"{prefix}_{outcome_name}"] = None
                    else:
                        row[f"{prefix}_total_frames"] = summary[
                            "total_frames"
                        ]
                        row[f"{prefix}_correct_fraction"] = summary[
                            "correct_fraction"
                        ]
                        row[f"{prefix}_wrong_person_count"] = summary[
                            "wrong_person_count"
                        ]
                        for outcome_name in (
                            "correct_target",
                            "correct_same_person_recovery",
                            "safe_suppression",
                            "target_candidate_absent",
                            "distractor_selection",
                            "stale_id_transfer",
                            "ambiguous_candidate",
                        ):
                            row[f"{prefix}_{outcome_name}"] = summary[
                                "counts"
                            ][outcome_name]
                rows.append(row)
    return rows


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    if not rows:
        raise ValueError("no rows to write")
    fieldnames = list(rows[0].keys())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def render_outcome_figure(
    report: dict[str, Any], output_path: Path
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    bin_labels = [b["label"] for b in report["bins"]]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)

    for axis, (mode_key, mode_title) in zip(
        axes,
        (
            ("full_pipeline_aggregate_by_bin", "Full pipeline (aggregate)"),
            ("oracle_candidate_aggregate_by_bin", "Oracle candidate (aggregate)"),
        ),
    ):
        agg = report[mode_key]
        x = range(len(bin_labels))
        width = 0.35

        def fractions(stream: str, kind: str) -> list[float]:
            values = []
            for label in bin_labels:
                summary = agg[stream][label]
                total = summary["total_frames"]
                if total == 0:
                    values.append(0.0)
                    continue
                if kind == "correct":
                    values.append(summary["correct_fraction"] or 0.0)
                elif kind == "wrong":
                    values.append(summary["wrong_person_fraction"] or 0.0)
                else:
                    values.append(
                        summary["counts"]["safe_suppression"] / total
                    )
            return values

        raw_correct = fractions("raw", "correct")
        tim_correct = fractions("tim_mars", "correct")

        axis.bar(
            [i - width / 2 for i in x],
            raw_correct,
            width,
            label="Raw correct",
            color="#9aa5b1",
        )
        axis.bar(
            [i + width / 2 for i in x],
            tim_correct,
            width,
            label="TIM correct",
            color="#2f6fed",
        )
        axis.set_xticks(list(x))
        axis.set_xticklabels(bin_labels, rotation=30, ha="right")
        axis.set_title(mode_title)
        axis.set_ylim(0, 1.05)

    axes[0].set_ylabel("Fraction of GT-visible frames")
    axes[0].legend(loc="upper right", fontsize=8)
    fig.suptitle(
        "Raw vs TIM-MARS correct-target fraction by target-height bin"
    )
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def render_candidate_availability_figure(
    report: dict[str, Any], output_path: Path
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    bin_labels = [b["label"] for b in report["bins"]]
    sequence_ids = list(report["full_pipeline"].keys())

    fig, axis = plt.subplots(figsize=(8, 4.5))
    width = 0.25
    colors = ["#2f6fed", "#e07b39", "#3fb27f"]

    for offset, (sequence_id, color) in enumerate(
        zip(sequence_ids, colors)
    ):
        presence = report["full_pipeline"][sequence_id][
            "candidate_presence_by_bin"
        ]
        values = [
            (presence[label]["fraction_with_candidate"] or 0.0)
            for label in bin_labels
        ]
        positions = [
            i + (offset - 1) * width for i in range(len(bin_labels))
        ]
        short_name = sequence_id.split("_val_")[-1]
        axis.bar(positions, values, width, label=short_name, color=color)

    axis.set_xticks(list(range(len(bin_labels))))
    axis.set_xticklabels(bin_labels, rotation=30, ha="right")
    axis.set_ylabel("Fraction of GT-visible frames with a matching candidate")
    axis.set_title(
        "Full-pipeline candidate availability by target-height bin\n"
        "(uav0000117/137 never initialize; shown regardless)"
    )
    axis.set_ylim(0, 1.05)
    axis.legend(fontsize=8)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    arguments = parser.parse_args()

    report = json.loads(arguments.input.read_text(encoding="utf-8"))
    rows = flatten_rows(report)

    csv_path = arguments.output_dir / "bbox_size_stratified_report.csv"
    write_csv(rows, csv_path)

    outcome_figure_path = (
        arguments.output_dir / "bbox_size_outcome_fractions.png"
    )
    render_outcome_figure(report, outcome_figure_path)

    availability_figure_path = (
        arguments.output_dir / "bbox_size_candidate_availability.png"
    )
    render_candidate_availability_figure(report, availability_figure_path)

    print(f"csv: {csv_path}")
    print(f"figure 1: {outcome_figure_path}")
    print(f"figure 2: {availability_figure_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
