#!/usr/bin/env python3
"""Diagnose TIM wrong-target intervals from target_memory_status.csv."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("status_csv", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--interval",
        action="append",
        nargs=3,
        metavar=("START", "END", "LABEL"),
        help="Wrong interval: start end label",
    )
    args = parser.parse_args()

    df = pd.read_csv(args.status_csv)

    intervals = []
    if args.interval:
        for start, end, label in args.interval:
            intervals.append((float(start), float(end), label))

    args.out.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append("# TIM Wrong-Interval Diagnosis")
    lines.append("")
    lines.append(f"- Source: `{args.status_csv}`")
    lines.append("")

    rows_out = []

    for start, end, label in intervals:
        g = df[(df["t"] >= start) & (df["t"] <= end)].copy()

        lines.append(f"## {label}")
        lines.append("")
        lines.append(f"- interval: {start:.3f}-{end:.3f} s")
        lines.append(f"- rows: {len(g)}")

        if len(g) == 0:
            lines.append("")
            continue

        def vc(col: str, n: int = 10) -> str:
            if col not in g.columns:
                return "n/a"
            return g[col].value_counts(dropna=False).head(n).to_string()

        lines.append("")
        lines.append("### State counts")
        lines.append("")
        lines.append("```text")
        lines.append(vc("state"))
        lines.append("```")

        lines.append("")
        lines.append("### TIM output target IDs")
        lines.append("")
        lines.append("```text")
        lines.append(vc("target_track_id"))
        lines.append("```")

        lines.append("")
        lines.append("### Best candidate IDs")
        lines.append("")
        lines.append("```text")
        lines.append(vc("best_track_id"))
        lines.append("```")

        lines.append("")
        lines.append("### Appearance used")
        lines.append("")
        lines.append("```text")
        lines.append(vc("best_appearance_used"))
        lines.append("```")

        stat_cols = [
            "best_total",
            "best_iou",
            "best_distance",
            "best_scale",
            "best_confidence",
            "best_appearance",
            "lat_ms",
        ]

        lines.append("")
        lines.append("### Score statistics")
        lines.append("")
        lines.append("| field | mean | p50 | p95 | min | max |")
        lines.append("|---|---:|---:|---:|---:|---:|")

        for col in stat_cols:
            if col not in g.columns:
                continue
            vals = pd.to_numeric(g[col], errors="coerce").dropna()
            if vals.empty:
                continue
            lines.append(
                f"| {col} | {vals.mean():.3f} | {vals.quantile(0.50):.3f} | "
                f"{vals.quantile(0.95):.3f} | {vals.min():.3f} | {vals.max():.3f} |"
            )

        lines.append("")
        lines.append("### First 20 rows")
        lines.append("")
        keep_cols = [
            "t",
            "state",
            "target_track_id",
            "best_track_id",
            "best_total",
            "best_iou",
            "best_distance",
            "best_scale",
            "best_confidence",
            "best_appearance",
            "best_appearance_used",
            "reason",
        ]
        keep_cols = [c for c in keep_cols if c in g.columns]
        lines.append("```text")
        lines.append(g[keep_cols].head(20).to_string(index=False))
        lines.append("```")
        lines.append("")

        summary = {
            "label": label,
            "start_s": start,
            "end_s": end,
            "rows": len(g),
            "dominant_state": g["state"].mode().iloc[0] if "state" in g and not g["state"].mode().empty else "",
            "dominant_target_track_id": g["target_track_id"].mode().iloc[0] if "target_track_id" in g and not g["target_track_id"].mode().empty else "",
            "dominant_best_track_id": g["best_track_id"].mode().iloc[0] if "best_track_id" in g and not g["best_track_id"].mode().empty else "",
            "appearance_used_rows": int(pd.Series(g.get("best_appearance_used", [])).astype(str).str.lower().isin(["true", "1"]).sum()) if "best_appearance_used" in g else 0,
            "best_total_median": pd.to_numeric(g.get("best_total", pd.Series(dtype=float)), errors="coerce").median(),
            "best_appearance_median": pd.to_numeric(g.get("best_appearance", pd.Series(dtype=float)), errors="coerce").median(),
        }
        rows_out.append(summary)

    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    csv_out = args.out.with_suffix(".csv")
    pd.DataFrame(rows_out).to_csv(csv_out, index=False)

    print(f"[ok] wrote {args.out}")
    print(f"[ok] wrote {csv_out}")


if __name__ == "__main__":
    main()
