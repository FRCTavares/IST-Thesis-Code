#!/usr/bin/env python3
"""Collect TIM replay-matrix summaries into one CSV and Markdown table."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


def extract_float(pattern: str, text: str) -> float | None:
    m = re.search(pattern, text)
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None


def extract_int(pattern: str, text: str) -> int | None:
    m = re.search(pattern, text)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def parse_run_name(name: str) -> dict[str, str]:
    tracker = ""
    tim_mode = ""
    target = ""

    m = re.search(r"__tracker_([^_]+)__tim_([^_]+)__target_(.+)$", name)
    if m:
        tracker = m.group(1)
        tim_mode = m.group(2)
        target = m.group(3)

    return {
        "run_name": name,
        "tracker": tracker,
        "tim_mode": tim_mode,
        "target_rule": target,
    }


def parse_summary(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8", errors="replace")
    run = parse_run_name(path.parent.name)

    raw_valid = extract_int(r"- Raw valid samples: (\d+)/", text)
    raw_total = extract_int(r"- Raw valid samples: \d+/(\d+)", text)
    tim_valid = extract_int(r"- TIM valid samples: (\d+)/", text)
    tim_total = extract_int(r"- TIM valid samples: \d+/(\d+)", text)

    raw_post_valid_s = extract_float(r"- Raw valid duration after TIM selection: ([0-9.]+)/", text)
    raw_post_total_s = extract_float(r"- Raw valid duration after TIM selection: [0-9.]+/([0-9.]+) s", text)

    tim_post_valid_s = extract_float(r"- TIM valid duration after TIM selection: ([0-9.]+)/", text)
    tim_post_total_s = extract_float(r"- TIM valid duration after TIM selection: [0-9.]+/([0-9.]+) s", text)

    reacq_events = extract_int(r"- Reacquisition samples/events observed: (\d+)", text)

    tim_p95 = extract_float(r"- p95: ([0-9.]+) ms", text)
    tim_p99 = extract_float(r"- p99: ([0-9.]+) ms", text)

    # Extract state durations from table rows if present.
    def state_duration(state: str) -> float | None:
        return extract_float(rf"\| {state} \| ([0-9.]+) \|", text)

    row = {
        **run,
        "summary_path": str(path),
        "raw_valid_samples": raw_valid,
        "raw_total_samples": raw_total,
        "tim_valid_samples": tim_valid,
        "tim_total_samples": tim_total,
        "raw_post_valid_s": raw_post_valid_s,
        "raw_post_total_s": raw_post_total_s,
        "tim_post_valid_s": tim_post_valid_s,
        "tim_post_total_s": tim_post_total_s,
        "locked_s": state_duration("LOCKED"),
        "uncertain_s": state_duration("UNCERTAIN"),
        "lost_s": state_duration("LOST"),
        "reacquired_s": state_duration("REACQUIRED"),
        "reacq_events": reacq_events,
        "tim_latency_p95_ms": tim_p95,
        "tim_latency_p99_ms": tim_p99,
    }

    return row


def fmt(x: object) -> str:
    if x is None:
        return ""
    if isinstance(x, float):
        return f"{x:.3f}"
    return str(x)


def write_markdown(rows: list[dict[str, object]], out_md: Path) -> None:
    cols = [
        "run_name",
        "tracker",
        "tim_mode",
        "target_rule",
        "raw_post_valid_s",
        "raw_post_total_s",
        "tim_post_valid_s",
        "tim_post_total_s",
        "reacq_events",
        "tim_latency_p95_ms",
    ]

    lines = []
    lines.append("# TIM Matrix Summary")
    lines.append("")
    lines.append(f"- Runs: {len(rows)}")
    lines.append("")
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("|" + "|".join(["---"] * len(cols)) + "|")

    for row in rows:
        lines.append("| " + " | ".join(fmt(row.get(c)) for c in cols) + " |")

    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reports-root",
        type=Path,
        default=Path("reports/tim_v0"),
    )
    parser.add_argument(
        "--glob",
        default="*tracker*__tim_*__target*/summary.md",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("reports/tim_matrix_summary"),
    )
    args = parser.parse_args()

    summaries = sorted(args.reports_root.glob(args.glob))
    rows = [parse_summary(p) for p in summaries]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_csv = args.out_dir / "summary.csv"
    out_md = args.out_dir / "summary.md"

    if rows:
        fieldnames = list(rows[0].keys())
    else:
        fieldnames = []

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    write_markdown(rows, out_md)

    print(f"[ok] rows: {len(rows)}")
    print(f"[ok] wrote {out_csv}")
    print(f"[ok] wrote {out_md}")


if __name__ == "__main__":
    main()
