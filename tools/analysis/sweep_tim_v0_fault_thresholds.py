#!/usr/bin/env python3
"""Sweep TIM-V0 lost-state acceptance threshold under deterministic ID-switch faults."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import math
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt


def load_batch_module(repo_root: Path):
    path = repo_root / "tools" / "analysis" / "evaluate_tim_v0_fault_injection_batch.py"
    spec = importlib.util.spec_from_file_location("tim_batch_eval", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_summary(path: Path, bag: Path, rows: list[dict[str, Any]]) -> None:
    lines = []
    lines.append("# TIM-V0 Lost-Threshold Sensitivity Sweep")
    lines.append("")
    lines.append(f"- Bag: `{bag}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| accept_score_lost | reacquired | mean gain | max gain | min gain | mean reacq time [s] | max reacq time [s] | failed |")
    lines.append("|---:|---:|---:|---:|---:|---:|---:|---:|")

    for r in rows:
        mean_t = "n/a" if math.isnan(float(r["mean_reacq_time_s"])) else f"{r['mean_reacq_time_s']:.3f}"
        max_t = "n/a" if math.isnan(float(r["max_reacq_time_s"])) else f"{r['max_reacq_time_s']:.3f}"
        lines.append(
            f"| {r['accept_score_lost']:.2f} "
            f"| {int(r['reacquired_cases'])}/{int(r['cases'])} "
            f"| {r['mean_validity_gain']:.3f} "
            f"| {r['max_validity_gain']:.3f} "
            f"| {r['min_validity_gain']:.3f} "
            f"| {mean_t} "
            f"| {max_t} "
            f"| {int(r['failed_cases'])} |"
        )

    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append(
        "Lower lost-state thresholds make reacquisition easier after injected ID switches, "
        "but they also accept weaker geometric evidence. Higher thresholds are more conservative "
        "and reduce the risk of wrong reacquisition, at the cost of failing more weak cases."
    )
    lines.append("")
    lines.append(
        "This sweep should be interpreted as threshold sensitivity under deterministic fault injection, "
        "not as a full safety proof. A true wrong-reacquisition metric requires annotated natural multi-person data."
    )

    path.write_text("\n".join(lines))


def plot_summary(rows: list[dict[str, Any]], out: Path) -> None:
    thresholds = [float(r["accept_score_lost"]) for r in rows]
    reacq = [float(r["reacquired_cases"]) for r in rows]
    mean_gain = [float(r["mean_validity_gain"]) for r in rows]

    fig, ax1 = plt.subplots(figsize=(7.5, 4.0), dpi=180)

    ax1.plot(thresholds, reacq, marker="o", label="reacquired cases")
    ax1.set_xlabel("accept_score_lost")
    ax1.set_ylabel("reacquired cases / 15")
    ax1.set_ylim(0, 15.5)
    ax1.grid(True, alpha=0.3)

    ax2 = ax1.twinx()
    ax2.plot(thresholds, mean_gain, marker="s", linestyle="--", label="mean validity gain")
    ax2.set_ylabel("mean validity gain")
    ax2.set_ylim(0, 1.0)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="best")

    ax1.set_title("TIM-V0 sensitivity to lost-state acceptance threshold")
    fig.tight_layout()
    fig.savefig(out / "threshold_sensitivity.png")
    fig.savefig(out / "threshold_sensitivity.pdf")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bag", type=Path)
    parser.add_argument("--selected-id", type=int, default=1)
    parser.add_argument("--new-id", "--replacement-id", dest="new_id", type=int, default=3)
    parser.add_argument("--thresholds", type=str, default="0.45,0.50,0.55,0.60,0.65")
    parser.add_argument("--gap-starts", type=str, default="24,26,28,30,32")
    parser.add_argument("--gap-durations", type=str, default="1,2,3")
    parser.add_argument("--out-root", type=Path, default=Path("reports/tim_v0_threshold_sweep"))
    args = parser.parse_args()

    repo_root = Path.cwd()
    batch = load_batch_module(repo_root)
    single = batch.load_single_eval_module(repo_root)

    bag = args.bag.resolve()
    out_dir = args.out_root / bag.name
    out_dir.mkdir(parents=True, exist_ok=True)

    import rclpy
    rclpy.init()
    try:
        rows = single.read_tracks(bag)
    finally:
        if rclpy.ok():
            rclpy.shutdown()

    thresholds = batch.parse_list_floats(args.thresholds)
    gap_starts = batch.parse_list_floats(args.gap_starts)
    gap_durations = batch.parse_list_floats(args.gap_durations)

    sweep_rows = []

    for thr in thresholds:
        case_rows = []
        for start in gap_starts:
            for duration in gap_durations:
                case_rows.append(
                    batch.run_case(
                        mod=single,
                        rows=rows,
                        selected_id=args.selected_id,
                        new_id=args.new_id,
                        gap_start_s=start,
                        gap_duration_s=duration,
                        accept_score_lost=thr,
                    )
                )

        gains = [float(r["validity_gain"]) for r in case_rows]
        reacq_times = [
            float(r["reacq_time_s"])
            for r in case_rows
            if bool(r["reacquired"]) and not math.isnan(float(r["reacq_time_s"]))
        ]
        n_reacq = sum(1 for r in case_rows if bool(r["reacquired"]))

        sweep_rows.append({
            "accept_score_lost": thr,
            "cases": len(case_rows),
            "reacquired_cases": n_reacq,
            "failed_cases": len(case_rows) - n_reacq,
            "mean_validity_gain": sum(gains) / len(gains) if gains else math.nan,
            "max_validity_gain": max(gains) if gains else math.nan,
            "min_validity_gain": min(gains) if gains else math.nan,
            "mean_reacq_time_s": sum(reacq_times) / len(reacq_times) if reacq_times else math.nan,
            "max_reacq_time_s": max(reacq_times) if reacq_times else math.nan,
        })

    write_csv(out_dir / "summary.csv", sweep_rows)
    write_summary(out_dir / "summary.md", bag, sweep_rows)
    plot_summary(sweep_rows, out_dir)

    print(f"[ok] wrote {out_dir}")
    print(f"[ok] summary: {out_dir / 'summary.md'}")
    print(f"[ok] csv: {out_dir / 'summary.csv'}")


if __name__ == "__main__":
    main()
