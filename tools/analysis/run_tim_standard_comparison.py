#!/usr/bin/env python3
"""
Standard TIM comparison runner.

Purpose:
- Produce one compact generated comparison summary per scenario.
- Reuse existing result summaries/timelines.
- Keep generated outputs under reports/tim_standard_matrix/<scenario>/.
- Keep curated thesis results separate under docs/results/.

This runner is intentionally read-only with respect to live/runtime defaults.
It does not launch ROS, replay bags, or change flight-safe configuration.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class MetricPair:
    raw: str
    policy: str


def repo_path(value: str) -> Path:
    p = Path(value)
    if not p.is_absolute():
        p = ROOT / p
    return p


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label}: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"{label} is not a file: {path}")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def annotation_coverage(path: Path) -> tuple[int, float]:
    rows = read_csv_rows(path)
    if not rows:
        return 0, 0.0

    end_values = []
    for row in rows:
        try:
            end_values.append(float(row.get("end_s", "0") or 0.0))
        except ValueError:
            pass

    return len(rows), max(end_values) if end_values else 0.0


def extract_global_result(summary_path: Path) -> dict[str, MetricPair]:
    text = summary_path.read_text(encoding="utf-8", errors="replace")
    results: dict[str, MetricPair] = {}

    for line in text.splitlines():
        m = re.match(
            r"\|\s*(correct_s|wrong_s|lost_s)\s*\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|",
            line,
        )
        if m:
            results[m.group(1)] = MetricPair(raw=m.group(2), policy=m.group(3))

    return results


def timeline_totals(path: Path, label_key: str) -> dict[str, float]:
    rows = read_csv_rows(path)
    if len(rows) < 2:
        return {}

    first = rows[0]
    if "t" in first:
        t_key = "t"
    elif "t_s" in first:
        t_key = "t_s"
    elif "time_s" in first:
        t_key = "time_s"
    else:
        raise ValueError(f"Timeline has no recognised time column: {path}")

    if label_key not in first:
        raise ValueError(f"Timeline has no `{label_key}` column: {path}")

    totals: dict[str, float] = {}

    for a, b in zip(rows, rows[1:]):
        try:
            dt = float(b[t_key]) - float(a[t_key])
        except Exception:
            continue

        if dt < 0 or dt > 1.0:
            continue

        label = a.get(label_key, "") or "UNKNOWN"
        totals[label] = totals.get(label, 0.0) + dt

    return totals


def duration_table(totals: dict[str, float]) -> str:
    if not totals:
        return "No durations extracted.\n"

    lines = ["| Label | Duration |", "|---|---:|"]
    for label, duration in sorted(totals.items()):
        lines.append(f"| {label} | {duration:.3f} s |")
    return "\n".join(lines) + "\n"


def metric_table(metrics: dict[str, MetricPair]) -> str:
    lines = ["| Metric | Raw | TIM policy |", "|---|---:|---:|"]
    for metric in ["correct_s", "wrong_s", "lost_s"]:
        pair = metrics.get(metric)
        if pair is None:
            lines.append(f"| {metric} | n/a | n/a |")
        else:
            lines.append(f"| {metric} | {pair.raw} | {pair.policy} |")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Generate a compact standard TIM scenario comparison summary."
    )
    ap.add_argument("--scenario", required=True, help="Scenario slug, e.g. critical_crossing")
    ap.add_argument("--annotation", required=True, help="Automatic target-correctness annotation CSV")
    ap.add_argument("--policy-summary", required=True, help="Selected policy summary.md")
    ap.add_argument("--policy-timeline", required=True, help="Selected policy timeline.csv")
    ap.add_argument("--baseline-summary", default="", help="Optional baseline/TIM-V0 summary.md")
    ap.add_argument("--video-review-annotation", default="", help="Optional manual video-review annotation CSV")
    ap.add_argument("--policy-name", default="TIM policy", help="Human-readable policy name")
    ap.add_argument("--out-root", default="reports/tim_standard_matrix", help="Generated output root")
    ap.add_argument("--date", default="", help="Date string for summary header, e.g. 2026-05-21")
    ap.add_argument("--notes", default="", help="Optional short interpretation note")
    return ap.parse_args()


def main() -> int:
    args = parse_args()

    annotation = repo_path(args.annotation)
    policy_summary = repo_path(args.policy_summary)
    policy_timeline = repo_path(args.policy_timeline)
    baseline_summary = repo_path(args.baseline_summary) if args.baseline_summary else None
    video_review_annotation = (
        repo_path(args.video_review_annotation) if args.video_review_annotation else None
    )

    require_file(annotation, "annotation")
    require_file(policy_summary, "policy summary")
    require_file(policy_timeline, "policy timeline")
    if baseline_summary is not None:
        require_file(baseline_summary, "baseline summary")
    if video_review_annotation is not None:
        require_file(video_review_annotation, "video-review annotation")

    out_dir = repo_path(args.out_root) / args.scenario
    out_dir.mkdir(parents=True, exist_ok=True)

    ann_rows, ann_end_s = annotation_coverage(annotation)
    video_rows, video_end_s = (
        annotation_coverage(video_review_annotation)
        if video_review_annotation is not None
        else (0, 0.0)
    )

    metrics = extract_global_result(policy_summary)

    raw_totals = timeline_totals(policy_timeline, "label_raw")
    policy_totals = timeline_totals(policy_timeline, "label_policy")

    generated_date = args.date or "unspecified"

    summary = f"""# TIM standard comparison: {args.scenario}

Generated: {generated_date}

## Inputs

| Item | Path |
|---|---|
| Automatic annotation | `{display_path(annotation)}` |
| Policy summary | `{display_path(policy_summary)}` |
| Policy timeline | `{display_path(policy_timeline)}` |
"""

    if baseline_summary is not None:
        summary += f"| Baseline summary | `{display_path(baseline_summary)}` |\n"
    if video_review_annotation is not None:
        summary += f"| Manual video-review annotation | `{display_path(video_review_annotation)}` |\n"

    summary += f"""
## Annotation coverage

| Annotation | Rows | End time |
|---|---:|---:|
| Automatic interval annotation | {ann_rows} | {ann_end_s:.2f} s |
"""

    if video_review_annotation is not None:
        summary += f"| Manual video-review annotation | {video_rows} | {video_end_s:.2f} s |\n"

    summary += f"""
## Global result

Policy: {args.policy_name}

{metric_table(metrics)}
## Timeline totals

### Raw labels

{duration_table(raw_totals)}
### Policy labels

{duration_table(policy_totals)}
## Interpretation note

"""

    if args.notes:
        summary += args.notes.strip() + "\n"
    else:
        summary += "No interpretation note provided. Curate the thesis-facing interpretation separately under docs/results/.\n"

    summary += """
## Output policy

This is generated output under `reports/tim_standard_matrix/`.
Do not commit this folder unless a specific generated artefact is deliberately curated.
Commit only small thesis-facing summaries under `docs/results/`.
"""

    manifest = {
        "scenario": args.scenario,
        "annotation": display_path(annotation),
        "policy_summary": display_path(policy_summary),
        "policy_timeline": display_path(policy_timeline),
        "baseline_summary": display_path(baseline_summary) if baseline_summary else "",
        "video_review_annotation": display_path(video_review_annotation) if video_review_annotation else "",
        "policy_name": args.policy_name,
        "out_dir": display_path(out_dir),
        "generated_date": generated_date,
    }

    (out_dir / "summary.md").write_text(summary, encoding="utf-8")
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"Wrote {display_path(out_dir / 'summary.md')}")
    print(f"Wrote {display_path(out_dir / 'manifest.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
