#!/usr/bin/env python3
"""
Evaluate TIM-V2E video-review annotations.

This evaluates manually reviewed visual intervals. It is separate from exact
bag/timeline evaluation and is meant for qualitative, video-grounded evidence.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from collections import defaultdict


def as_float(v, default=0.0) -> float:
    try:
        if v in ("", None):
            return default
        return float(v)
    except Exception:
        return default


def as_bool(v) -> bool:
    return str(v).strip().lower() in {"true", "1", "yes", "y"}


def classify_outputs(event: str) -> tuple[str, str]:
    event = event.strip()

    mapping = {
        "pre_selection": ("not_scored", "not_scored"),
        "correct_raw_correct_v2e": ("correct", "correct"),
        "wrong_raw_correct_v2e": ("wrong", "correct"),
        "wrong_raw_lost_v2e": ("wrong", "lost"),
        "wrong_raw_wrong_v2e": ("wrong", "wrong"),
        "lost_both_target_visible": ("lost", "lost"),
        "no_target_output": ("lost", "lost"),
        "crossing": ("correct", "lost"),
        "occlusion": ("not_scored", "not_scored"),
        "ambiguous_visibility": ("not_scored", "not_scored"),
        "target_absent": ("not_scored", "not_scored"),
    }

    return mapping.get(event, ("not_scored", "not_scored"))


def add_duration(stats: dict, who: str, label: str, duration: float) -> None:
    stats[f"{who}_{label}_s"] += duration


def evaluate(path: Path) -> dict:
    rows = list(csv.DictReader(path.open()))
    stats = defaultdict(float)
    event_stats = defaultdict(lambda: defaultdict(float))

    for r in rows:
        start = as_float(r["start_s"])
        end = as_float(r["end_s"])
        duration = max(0.0, end - start)
        event = r["event_type"].strip()
        visible = as_bool(r["target_visible"])
        target_label = r["target_label"].strip()

        raw_label, v2e_label = classify_outputs(event)

        stats["total_s"] += duration
        event_stats[event]["duration_s"] += duration

        if target_label == "NO_TARGET_SELECTED":
            stats["pre_selection_s"] += duration
            event_stats[event]["pre_selection_s"] += duration
            continue

        if not visible or target_label in {"TARGET_OCCLUDED", "TARGET_ABSENT", "AMBIGUOUS_TARGET"}:
            stats["not_scored_s"] += duration
            event_stats[event]["not_scored_s"] += duration
            continue

        if raw_label == "not_scored" or v2e_label == "not_scored":
            stats["not_scored_s"] += duration
            event_stats[event]["not_scored_s"] += duration
            continue

        stats["scored_visible_s"] += duration
        event_stats[event]["scored_visible_s"] += duration

        add_duration(stats, "raw", raw_label, duration)
        add_duration(stats, "v2e", v2e_label, duration)

        event_stats[event][f"raw_{raw_label}_s"] += duration
        event_stats[event][f"v2e_{v2e_label}_s"] += duration

    return {
        "path": str(path),
        "stats": dict(stats),
        "events": {k: dict(v) for k, v in event_stats.items()},
    }


def fmt(x: float) -> str:
    return f"{x:.3f}"


def ratio(num: float, den: float) -> float:
    return num / den if den > 0 else 0.0


def write_summary(path: Path, results: list[dict]) -> None:
    lines = []
    lines.append("# TIM-V2E Video Review Evaluation")
    lines.append("")
    lines.append("Manual visual intervals from overlay video/frame review.")
    lines.append("This is qualitative/video-grounded evidence, not exact bag/timeline scoring.")
    lines.append("")

    for res in results:
        stats = res["stats"]
        scored = stats.get("scored_visible_s", 0.0)

        lines.append(f"## {res['path']}")
        lines.append("")
        lines.append("### Global durations")
        lines.append("")
        lines.append("| Metric | Raw | TIM-V2E |")
        lines.append("|---|---:|---:|")
        lines.append(f"| correct_s | {fmt(stats.get('raw_correct_s', 0.0))} | {fmt(stats.get('v2e_correct_s', 0.0))} |")
        lines.append(f"| wrong_s | {fmt(stats.get('raw_wrong_s', 0.0))} | {fmt(stats.get('v2e_wrong_s', 0.0))} |")
        lines.append(f"| lost_s | {fmt(stats.get('raw_lost_s', 0.0))} | {fmt(stats.get('v2e_lost_s', 0.0))} |")
        lines.append("")
        lines.append("### Ratios over scored visible time")
        lines.append("")
        lines.append(f"- scored_visible_s: {fmt(scored)}")
        lines.append(f"- raw_correct_ratio: {ratio(stats.get('raw_correct_s', 0.0), scored):.3f}")
        lines.append(f"- raw_wrong_ratio: {ratio(stats.get('raw_wrong_s', 0.0), scored):.3f}")
        lines.append(f"- raw_lost_ratio: {ratio(stats.get('raw_lost_s', 0.0), scored):.3f}")
        lines.append(f"- v2e_correct_ratio: {ratio(stats.get('v2e_correct_s', 0.0), scored):.3f}")
        lines.append(f"- v2e_wrong_ratio: {ratio(stats.get('v2e_wrong_s', 0.0), scored):.3f}")
        lines.append(f"- v2e_lost_ratio: {ratio(stats.get('v2e_lost_s', 0.0), scored):.3f}")
        lines.append("")
        lines.append("### Event breakdown")
        lines.append("")
        lines.append("| Event | duration_s | raw_correct | raw_wrong | raw_lost | v2e_correct | v2e_wrong | v2e_lost |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")

        for event, ev in sorted(res["events"].items()):
            lines.append(
                f"| {event} | {fmt(ev.get('duration_s', 0.0))} | "
                f"{fmt(ev.get('raw_correct_s', 0.0))} | "
                f"{fmt(ev.get('raw_wrong_s', 0.0))} | "
                f"{fmt(ev.get('raw_lost_s', 0.0))} | "
                f"{fmt(ev.get('v2e_correct_s', 0.0))} | "
                f"{fmt(ev.get('v2e_wrong_s', 0.0))} | "
                f"{fmt(ev.get('v2e_lost_s', 0.0))} |"
            )

        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--annotations", nargs="+", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    results = [evaluate(p) for p in args.annotations]
    write_summary(args.output_dir / "summary.md", results)

    print(f"[ok] wrote {args.output_dir / 'summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
