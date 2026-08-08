#!/usr/bin/env python3
"""Compute Issue #32 selective-appearance-budget metrics from TIM-MARS status.

Reuses tools/analysis/analyse_tim_reid_workload.py's status-record bag
reader rather than re-implementing bag parsing. Adds the budget metrics
Issue #32 asks for that the existing analyser does not compute: candidates
encoded per second, embeddings per second, fraction of frames invoking
appearance, and a cache-hit-rate estimate derived from already-published
counters (appearance_features_valid vs appearance_backend_valid) rather than
a new instrumentation point.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_ANALYSIS_DIR = str(Path(__file__).resolve().parent)
if _ANALYSIS_DIR not in sys.path:
    sys.path.insert(0, _ANALYSIS_DIR)

from analyse_tim_reid_workload import (  # noqa: E402
    DEFAULT_TOPIC,
    read_status_records,
)

SCHEMA = "p032_appearance_budget_v1"


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None

    ordered = sorted(values)

    if len(ordered) == 1:
        return ordered[0]

    position = max(0.0, min(1.0, fraction)) * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))

    if lower == upper:
        return ordered[lower]

    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def latency_summary(values: list[float]) -> dict[str, Any]:
    finite = [v for v in values if math.isfinite(v)]
    return {
        "count": len(finite),
        "p50": percentile(finite, 0.50),
        "p90": percentile(finite, 0.90),
        "p95": percentile(finite, 0.95),
        "p99": percentile(finite, 0.99),
        "maximum": max(finite) if finite else None,
    }


REPLAY_MODE = "replay_algorithmic_cost"
LIVE_MODE = "live_sustained"
UNAVAILABLE_REPLAY_LATENCY_REASON = (
    "tools/experiments/run_deterministic_tim_replay.py hardcodes lat_ms=0.0 "
    "and appearance_backend_wall_ms=0.0 (verified in source): deterministic "
    "replay never measures wall time. Reporting these as zero would silently "
    "fabricate an implausible zero-latency claim. Genuine TIM core / MARS "
    "extraction latency percentiles come only from measurement_mode="
    "live_sustained."
)


def analyse(
    records: list[tuple[int, dict[str, Any]]],
    *,
    run_name: str,
    git_commit: str | None,
    bag_path: str,
    status_topic: str = DEFAULT_TOPIC,
    measurement_mode: str = LIVE_MODE,
) -> dict[str, Any]:
    if not records:
        raise ValueError("No TIM-MARS status records were supplied.")

    ordered = sorted(records, key=lambda record: record[0])
    start_ns = ordered[0][0]
    end_ns = ordered[-1][0]
    duration_s = max(1e-9, (end_ns - start_ns) / 1e9)

    total_records = len(ordered)
    frames_invoking_appearance = 0
    candidates_encoded_total = 0
    embeddings_valid_total = 0
    features_valid_total = 0
    lat_values: list[float] = []
    wall_values: list[float] = []
    skip_reason_counts: dict[str, int] = {}

    for _timestamp_ns, payload in ordered:
        backend_calls = int(payload["appearance_backend_calls"])

        if backend_calls > 0:
            frames_invoking_appearance += 1
            wall_values.append(
                float(payload["appearance_backend_wall_ms"])
            )

        candidates_encoded_total += int(
            payload["appearance_backend_requested"]
        )
        embeddings_valid_total += int(
            payload["appearance_backend_valid"]
        )
        features_valid_total += int(
            payload["appearance_features_valid"]
        )
        lat_values.append(float(payload["lat_ms"]))

        skip_reason = str(payload.get("appearance_skip_reason", ""))
        if skip_reason:
            skip_reason_counts[skip_reason] = (
                skip_reason_counts.get(skip_reason, 0) + 1
            )

    # A cache-served feature is a valid appearance feature in excess of
    # this run's fresh backend-valid count. This is derived from counters
    # the TIM-MARS status message already publishes; it is not a new
    # dedicated cache-hit instrumentation point.
    cache_served_total = max(
        0,
        features_valid_total - embeddings_valid_total,
    )
    cache_hit_rate = (
        cache_served_total / features_valid_total
        if features_valid_total > 0
        else None
    )

    if measurement_mode == REPLAY_MODE:
        wall_summary: dict[str, Any] | None = None
        core_summary: dict[str, Any] | None = None
        latency_unavailable_reason: str | None = (
            UNAVAILABLE_REPLAY_LATENCY_REASON
        )
    else:
        wall_summary = latency_summary(wall_values)
        core_summary = latency_summary(lat_values)
        latency_unavailable_reason = None

    return {
        "schema": SCHEMA,
        "run_name": run_name,
        "git_commit": git_commit,
        "bag_path": bag_path,
        "status_topic": status_topic,
        "measurement_mode": measurement_mode,
        "record_count": total_records,
        "duration_s": duration_s,
        "frames_invoking_appearance": frames_invoking_appearance,
        "fraction_frames_invoking_appearance": (
            frames_invoking_appearance / total_records
            if total_records > 0
            else None
        ),
        "candidates_encoded_total": candidates_encoded_total,
        "candidates_encoded_per_second": (
            candidates_encoded_total / duration_s
        ),
        "embeddings_valid_total": embeddings_valid_total,
        "embeddings_per_second": embeddings_valid_total / duration_s,
        "cache_served_total": cache_served_total,
        "cache_hit_rate": cache_hit_rate,
        "cache_hit_rate_definition": (
            "features_valid in excess of fresh backend_valid, as a "
            "fraction of total valid features; an estimate derived from "
            "already-published counters, not a dedicated cache-hit "
            "counter."
        ),
        "appearance_backend_wall_ms": wall_summary,
        "tim_core_latency_ms": core_summary,
        "latency_unavailable_reason": latency_unavailable_reason,
        "skip_reason_counts": dict(sorted(skip_reason_counts.items())),
    }


def render_markdown(summary: dict[str, Any]) -> str:
    wall = summary["appearance_backend_wall_ms"]
    core = summary["tim_core_latency_ms"]

    def fmt(value: float | None) -> str:
        return "n/a" if value is None else f"{value:.3f}"

    def row(label: str, source: str, values: dict[str, Any] | None) -> str:
        if values is None:
            return f"| {label} (`{source}`) | unavailable | -- | -- | -- | -- | -- |"
        return (
            f"| {label} (`{source}`) | {values['count']} | {fmt(values['p50'])} | "
            f"{fmt(values['p90'])} | {fmt(values['p95'])} | {fmt(values['p99'])} | "
            f"{fmt(values['maximum'])} |"
        )

    lines = [
        f"# Issue #32 Appearance Budget -- {summary['run_name']}",
        "",
        f"- bag: `{summary['bag_path']}`",
        f"- git commit: `{summary['git_commit']}`",
        f"- measurement mode: `{summary['measurement_mode']}`",
        f"- record count: {summary['record_count']}",
        f"- duration: {summary['duration_s']:.3f} s",
        "",
        "## Budget",
        "",
        f"- frames invoking appearance: {summary['frames_invoking_appearance']} "
        f"({fmt(summary['fraction_frames_invoking_appearance'])} fraction)",
        f"- candidates encoded / s: {fmt(summary['candidates_encoded_per_second'])}",
        f"- embeddings / s: {fmt(summary['embeddings_per_second'])}",
        f"- cache hit rate (estimate): {fmt(summary['cache_hit_rate'])}",
        "",
        "## Latency (ms)",
        "",
    ]

    if summary["latency_unavailable_reason"] is not None:
        lines.append(
            f"**Unavailable in this measurement mode:** "
            f"{summary['latency_unavailable_reason']}"
        )
        lines.append("")

    lines += [
        "| Metric | n | p50 | p90 | p95 | p99 | max |",
        "|---|---:|---:|---:|---:|---:|---:|",
        row("TIM core", "lat_ms", core),
        row("MARS extraction", "appearance_backend_wall_ms", wall),
        "",
        "## Skip reasons",
        "",
    ]

    if summary["skip_reason_counts"]:
        lines.append("| Reason | Count |")
        lines.append("|---|---:|")
        for reason, count in summary["skip_reason_counts"].items():
            lines.append(f"| {reason} | {count} |")
    else:
        lines.append("None recorded.")

    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compute Issue #32 selective-appearance-budget metrics from "
            "/target_memory_mars/status."
        )
    )
    parser.add_argument("bag")
    parser.add_argument("--topic", default=DEFAULT_TOPIC)
    parser.add_argument("--storage-id", default="mcap")
    parser.add_argument("--run-name", default=None)
    parser.add_argument("--git-commit", default=None)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--markdown-out", required=True)
    parser.add_argument(
        "--measurement-mode",
        choices=[REPLAY_MODE, LIVE_MODE],
        default=LIVE_MODE,
        help=(
            "replay_algorithmic_cost forces TIM core / MARS extraction "
            "latency fields to null: the deterministic TIM replay runner "
            "hardcodes lat_ms=0.0 and appearance_backend_wall_ms=0.0, so "
            "those fields never carry a real measurement in replay mode."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    bag_path = Path(args.bag).resolve()
    json_path = Path(args.json_out).resolve()
    markdown_path = Path(args.markdown_out).resolve()

    records = read_status_records(
        bag_path,
        topic=args.topic,
        storage_id=args.storage_id,
    )

    summary = analyse(
        records,
        run_name=args.run_name or bag_path.name,
        git_commit=args.git_commit,
        bag_path=str(bag_path),
        status_topic=args.topic,
        measurement_mode=args.measurement_mode,
    )

    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)

    json_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(summary), encoding="utf-8")

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
