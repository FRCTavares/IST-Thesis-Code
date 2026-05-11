#!/usr/bin/env python3
"""TIM-V1 appearance diagnostics report.

Reads target_memory_status.csv produced by analyse_tim_v0_bag.py and generates
a compact appearance-focused report.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import Counter
from pathlib import Path
from typing import Any


def as_float(row: dict[str, str], key: str) -> float:
    try:
        return float(row.get(key, "nan"))
    except Exception:
        return float("nan")


def as_int(row: dict[str, str], key: str) -> int:
    try:
        return int(float(row.get(key, 0) or 0))
    except Exception:
        return 0


def as_bool(row: dict[str, str], key: str) -> bool:
    return str(row.get(key, "")).lower() in {"true", "1", "yes"}


def finite(values: list[float]) -> list[float]:
    return [v for v in values if math.isfinite(v)]


def percentile(values: list[float], p: float) -> float:
    values = finite(values)
    if not values:
        return float("nan")
    s = sorted(values)
    return s[int((len(s) - 1) * p)]


def mean(values: list[float]) -> float:
    values = finite(values)
    if not values:
        return float("nan")
    return sum(values) / len(values)


def fmt(x: float, digits: int = 3) -> str:
    if not math.isfinite(x):
        return "n/a"
    return f"{x:.{digits}f}"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_summary(out_path: Path, source_csv: Path, rows: list[dict[str, str]]) -> None:
    n = len(rows)
    appearance_enabled = [r for r in rows if as_bool(r, "appearance_enabled")]
    valid_features = [r for r in rows if as_int(r, "appearance_features_valid") > 0]
    selected = [r for r in rows if r.get("target_track_id") not in {"", "None", None}]
    used = [r for r in rows if as_bool(r, "best_appearance_used")]

    ages = [as_float(r, "appearance_image_age_ms") for r in valid_features]
    lat = [as_float(r, "lat_ms") for r in rows]
    best_app = [as_float(r, "best_appearance") for r in rows]

    states = Counter(str(r.get("state", "")) for r in rows)
    skip_reasons = Counter(str(r.get("appearance_skip_reason", "")) for r in rows)
    used_by_state = Counter(str(r.get("state", "")) for r in used)

    lines: list[str] = []
    lines.append("# TIM-V1 Appearance Diagnostics")
    lines.append("")
    lines.append(f"- Source CSV: `{source_csv}`")
    lines.append(f"- Status rows: {n}")
    lines.append(f"- Appearance enabled rows: {len(appearance_enabled)}")
    lines.append(f"- Selected-target rows: {len(selected)}")
    lines.append(f"- Rows with valid appearance features: {len(valid_features)}")
    lines.append(f"- Rows with `best_appearance_used=true`: {len(used)}")
    lines.append("")

    lines.append("## Appearance feature extraction")
    lines.append("")
    lines.append(f"- Valid feature ratio: {len(valid_features)}/{n}" if n else "- Valid feature ratio: n/a")
    lines.append(f"- Image age mean: {fmt(mean(ages))} ms")
    lines.append(f"- Image age p50: {fmt(percentile(ages, 0.50))} ms")
    lines.append(f"- Image age p95: {fmt(percentile(ages, 0.95))} ms")
    lines.append(f"- Image age p99: {fmt(percentile(ages, 0.99))} ms")
    lines.append("")

    lines.append("## TIM latency")
    lines.append("")
    lines.append(f"- lat mean: {fmt(mean(lat))} ms")
    lines.append(f"- lat p50: {fmt(percentile(lat, 0.50))} ms")
    lines.append(f"- lat p95: {fmt(percentile(lat, 0.95))} ms")
    lines.append(f"- lat p99: {fmt(percentile(lat, 0.99))} ms")
    lines.append("")

    lines.append("## Best-candidate appearance")
    lines.append("")
    lines.append(f"- best appearance mean: {fmt(mean(best_app))}")
    lines.append(f"- best appearance p95: {fmt(percentile(best_app, 0.95))}")
    lines.append("")

    lines.append("## State counts")
    lines.append("")
    lines.append("| State | Rows |")
    lines.append("|---|---:|")
    for state, count in sorted(states.items()):
        lines.append(f"| {state or 'UNKNOWN'} | {count} |")
    lines.append("")

    lines.append("## Appearance skip reasons")
    lines.append("")
    lines.append("| Reason | Rows |")
    lines.append("|---|---:|")
    for reason, count in sorted(skip_reasons.items()):
        lines.append(f"| {reason or 'EMPTY'} | {count} |")
    lines.append("")

    lines.append("## Appearance-used by state")
    lines.append("")
    lines.append("| State | Rows |")
    lines.append("|---|---:|")
    if used_by_state:
        for state, count in sorted(used_by_state.items()):
            lines.append(f"| {state or 'UNKNOWN'} | {count} |")
    else:
        lines.append("| none | 0 |")
    lines.append("")

    lines.append("## Interpretation")
    lines.append("")
    if len(valid_features) > 0:
        lines.append("Appearance feature extraction was active and produced valid features.")
    else:
        lines.append("No valid appearance features were found. Check image topic, crop size, and timestamp age.")
    if len(used) > 0:
        lines.append("Appearance influenced at least one candidate association.")
    else:
        lines.append("Appearance did not influence association in this run. This is expected for stable single-person or non-ambiguous runs.")
    lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("status_csv", type=Path, help="target_memory_status.csv from TIM bag analysis")
    parser.add_argument("--out-root", type=Path, default=Path("reports/tim_v1_appearance"))
    args = parser.parse_args()

    status_csv = args.status_csv.resolve()
    rows = read_csv(status_csv)

    bag_name = status_csv.parent.name
    out_dir = args.out_root / bag_name
    out_dir.mkdir(parents=True, exist_ok=True)

    write_summary(out_dir / "summary.md", status_csv, rows)

    print(f"[ok] wrote {out_dir / 'summary.md'}")


if __name__ == "__main__":
    main()
