#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import importlib.util
import math
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt


def load_single_eval_module(repo_root: Path):
    path = repo_root / "tools" / "analysis" / "evaluate_tim_v0_fault_injection.py"
    spec = importlib.util.spec_from_file_location("tim_single_eval", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def count_valid(rows: list[dict[str, Any]], start_t: float) -> tuple[int, int]:
    post = [r for r in rows if float(r["t"]) >= start_t]
    valid = sum(1 for r in post if bool(r["valid"]))
    return valid, len(post)


def first_reacq_after(tim_rows: list[dict[str, Any]], t0: float) -> dict[str, Any] | None:
    for r in tim_rows:
        if float(r["t"]) >= t0 and r.get("state") == "REACQUIRED":
            return r
    return None


def run_case(
    mod,
    rows,
    selected_id: int,
    new_id: int,
    gap_start_s: float,
    gap_duration_s: float,
) -> dict[str, Any]:
    injected = mod.inject_fault(
        rows,
        selected_id=selected_id,
        new_id=new_id,
        gap_start_s=gap_start_s,
        gap_duration_s=gap_duration_s,
    )

    raw = mod.run_raw_selector(injected, selected_id=selected_id)
    tim = mod.run_tim(injected, selected_id=selected_id)

    fault_end_s = gap_start_s + gap_duration_s

    raw_valid, raw_total = count_valid(raw, gap_start_s)
    tim_valid, tim_total = count_valid(tim, gap_start_s)

    reacq = first_reacq_after(tim, fault_end_s)

    post_end = [r for r in tim if float(r["t"]) >= fault_end_s]
    last_post = post_end[-1] if post_end else (tim[-1] if tim else {})
    best_post = None
    if post_end:
        valid_best_rows = [
            r for r in post_end
            if not math.isnan(float(r.get("best_total", math.nan)))
        ]
        if valid_best_rows:
            best_post = max(valid_best_rows, key=lambda r: float(r.get("best_total", math.nan)))

    if best_post is None:
        best_post = {}

    if reacq is None:
        reacq_time_s = math.nan
        reacq_id = 0
        reacq_quality = math.nan
        reacq_reason = ""
    else:
        reacq_time_s = float(reacq["t"]) - fault_end_s
        reacq_id = int(reacq["id"])
        reacq_quality = float(reacq["quality"])
        reacq_reason = str(reacq["reason"])

    return {
        "selected_id": selected_id,
        "new_id": new_id,
        "gap_start_s": gap_start_s,
        "gap_duration_s": gap_duration_s,
        "fault_end_s": fault_end_s,
        "raw_valid": raw_valid,
        "raw_total": raw_total,
        "raw_valid_ratio": raw_valid / raw_total if raw_total else math.nan,
        "tim_valid": tim_valid,
        "tim_total": tim_total,
        "tim_valid_ratio": tim_valid / tim_total if tim_total else math.nan,
        "validity_gain": (tim_valid / tim_total if tim_total else 0.0) - (raw_valid / raw_total if raw_total else 0.0),
        "reacquired": reacq is not None,
        "reacq_time_s": reacq_time_s,
        "reacq_id": reacq_id,
        "reacq_quality": reacq_quality,
        "reacq_reason": reacq_reason,

        # Failure/debug diagnostics. Useful when reacquired == False.
        "final_state": str(last_post.get("state", "")),
        "final_reason": str(last_post.get("reason", "")),
        "final_quality": float(last_post.get("quality", math.nan)),
        "final_frames_since_seen": int(last_post.get("frames_since_seen", 0)),
        "final_num_candidates": int(last_post.get("num_candidates", 0)),
        "final_best_track_id": int(last_post.get("best_track_id", 0)),
        "final_best_total": float(last_post.get("best_total", math.nan)),
        "final_best_iou": float(last_post.get("best_iou", math.nan)),
        "final_best_distance": float(last_post.get("best_distance", math.nan)),
        "final_best_scale": float(last_post.get("best_scale", math.nan)),
        "final_best_confidence": float(last_post.get("best_confidence", math.nan)),
        "final_best_ambiguous": bool(last_post.get("best_ambiguous", False)),

        "max_best_track_id_after_reappearance": int(best_post.get("best_track_id", 0)),
        "max_best_total_after_reappearance": float(best_post.get("best_total", math.nan)),
        "max_best_iou_after_reappearance": float(best_post.get("best_iou", math.nan)),
        "max_best_distance_after_reappearance": float(best_post.get("best_distance", math.nan)),
        "max_best_scale_after_reappearance": float(best_post.get("best_scale", math.nan)),
        "max_best_confidence_after_reappearance": float(best_post.get("best_confidence", math.nan)),
        "max_best_reason_after_reappearance": str(best_post.get("reason", "")),
        "max_best_state_after_reappearance": str(best_post.get("state", "")),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def plot_validity_gain(rows: list[dict[str, Any]], out: Path) -> None:
    if not rows:
        return

    labels = [
        f"{r['gap_start_s']:.1f}s/{r['gap_duration_s']:.1f}s"
        for r in rows
    ]
    gains = [float(r["validity_gain"]) for r in rows]

    plt.figure(figsize=(12, 4))
    plt.bar(range(len(rows)), gains)
    plt.xticks(range(len(rows)), labels, rotation=45, ha="right")
    plt.ylabel("TIM valid ratio - raw valid ratio")
    plt.xlabel("gap_start/gap_duration")
    plt.title("TIM-V0 validity gain under injected ID-switch faults")
    plt.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(out, dpi=160)
    plt.close()


def plot_reacq_times(rows: list[dict[str, Any]], out: Path) -> None:
    valid_rows = [r for r in rows if bool(r["reacquired"]) and not math.isnan(float(r["reacq_time_s"]))]
    if not valid_rows:
        return

    labels = [
        f"{r['gap_start_s']:.1f}s/{r['gap_duration_s']:.1f}s"
        for r in valid_rows
    ]
    times = [float(r["reacq_time_s"]) for r in valid_rows]

    plt.figure(figsize=(12, 4))
    plt.bar(range(len(valid_rows)), times)
    plt.xticks(range(len(valid_rows)), labels, rotation=45, ha="right")
    plt.ylabel("reacquisition time after reappearance [s]")
    plt.xlabel("gap_start/gap_duration")
    plt.title("TIM-V0 reacquisition time under injected ID switches")
    plt.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(out, dpi=160)
    plt.close()


def write_summary(path: Path, bag: Path, rows: list[dict[str, Any]]) -> None:
    n = len(rows)
    n_reacq = sum(1 for r in rows if bool(r["reacquired"]))
    gains = [float(r["validity_gain"]) for r in rows]
    reacq_times = [
        float(r["reacq_time_s"])
        for r in rows
        if bool(r["reacquired"]) and not math.isnan(float(r["reacq_time_s"]))
    ]

    lines = []
    lines.append("# TIM-V0 Batch Fault-Injection Evaluation")
    lines.append("")
    lines.append(f"- Bag: `{bag}`")
    lines.append(f"- Cases: {n}")
    lines.append(f"- Reacquired cases: {n_reacq}/{n}")
    lines.append("")
    lines.append("## Aggregate results")
    lines.append("")
    if gains:
        lines.append(f"- Mean validity gain: {sum(gains) / len(gains):.3f}")
        lines.append(f"- Max validity gain: {max(gains):.3f}")
        lines.append(f"- Min validity gain: {min(gains):.3f}")
    if reacq_times:
        lines.append(f"- Mean reacquisition time: {sum(reacq_times) / len(reacq_times):.3f} s")
        lines.append(f"- Max reacquisition time: {max(reacq_times):.3f} s")
    lines.append("")
    lines.append("## Failed cases")
    lines.append("")
    failed = [r for r in rows if not bool(r["reacquired"])]
    if not failed:
        lines.append("- None.")
    else:
        lines.append("| gap start | duration | final state | final reason | final q | final best | max post best | max post reason |")
        lines.append("|---:|---:|---|---|---:|---:|---:|---|")
        for r in failed:
            lines.append(
                f"| {r['gap_start_s']:.2f} "
                f"| {r['gap_duration_s']:.2f} "
                f"| {r['final_state']} "
                f"| {r['final_reason']} "
                f"| {r['final_quality']:.3f} "
                f"| {r['final_best_total']:.3f} "
                f"| {r['max_best_total_after_reappearance']:.3f} "
                f"| {r['max_best_reason_after_reappearance']} |"
            )
    lines.append("")

    lines.append("## Cases")
    lines.append("")
    lines.append("| gap start | duration | raw valid | TIM valid | gain | reacquired | reacq time | reacq ID |")
    lines.append("|---:|---:|---:|---:|---:|:---:|---:|---:|")
    for r in rows:
        lines.append(
            f"| {r['gap_start_s']:.2f} | {r['gap_duration_s']:.2f} "
            f"| {r['raw_valid']}/{r['raw_total']} "
            f"| {r['tim_valid']}/{r['tim_total']} "
            f"| {r['validity_gain']:.3f} "
            f"| {bool(r['reacquired'])} "
            f"| {r['reacq_time_s'] if not math.isnan(float(r['reacq_time_s'])) else 'n/a'} "
            f"| {r['reacq_id']} |"
        )
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    lines.append(
        "This batch evaluation injects deterministic target ID-switch faults into recorded `/tracks` data. "
        "The raw selector keeps waiting for the originally selected ID, while TIM-V0 can recover the selected physical target "
        "under a replacement track ID using target memory and geometric consistency."
    )

    path.write_text("\n".join(lines))


def parse_list_floats(text: str) -> list[float]:
    return [float(x.strip()) for x in text.split(",") if x.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bag", type=Path)
    parser.add_argument("--selected-id", type=int, default=1)
    parser.add_argument("--new-id", "--replacement-id", dest="new_id", type=int, default=3)
    parser.add_argument("--gap-starts", type=str, default="24,26,28,30,32")
    parser.add_argument("--gap-durations", type=str, default="1,2,3")
    parser.add_argument("--out-root", type=Path, default=Path("reports/tim_v0_fault_injection_batch"))
    args = parser.parse_args()

    repo_root = Path.cwd()
    mod = load_single_eval_module(repo_root)

    bag = args.bag.resolve()
    out_dir = args.out_root / bag.name
    out_dir.mkdir(parents=True, exist_ok=True)

    # Reuse robust ROS bag reader from the single-case script.
    import rclpy
    rclpy.init()
    try:
        rows = mod.read_tracks(bag)
    finally:
        if rclpy.ok():
            rclpy.shutdown()

    gap_starts = parse_list_floats(args.gap_starts)
    gap_durations = parse_list_floats(args.gap_durations)

    results = []
    for start in gap_starts:
        for duration in gap_durations:
            results.append(
                run_case(
                    mod=mod,
                    rows=rows,
                    selected_id=args.selected_id,
                    new_id=args.new_id,
                    gap_start_s=start,
                    gap_duration_s=duration,
                )
            )

    write_csv(out_dir / "summary.csv", results)
    plot_validity_gain(results, out_dir / "validity_gain.png")
    plot_reacq_times(results, out_dir / "reacquisition_times.png")
    write_summary(out_dir / "summary.md", bag, results)

    print(f"[ok] wrote {out_dir}")
    print(f"[ok] summary: {out_dir / 'summary.md'}")
    print(f"[ok] csv: {out_dir / 'summary.csv'}")


if __name__ == "__main__":
    main()
