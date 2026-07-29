#!/usr/bin/env python3
"""Analyse CPU ReID workload recorded in TIM-MARS status messages."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
import statistics
from typing import Any, Sequence


DEFAULT_TOPIC = "/target_memory_mars/status"
SUMMARY_SCHEMA = "p044_cpu_reid_workload_summary_v2"

REQUIRED_FIELDS = (
    "lat_ms",
    "appearance_candidates",
    "appearance_features_valid",
    "appearance_encoding_eligible",
    "appearance_backend_calls",
    "appearance_backend_requested",
    "appearance_backend_returned",
    "appearance_backend_valid",
    "appearance_backend_wall_ms",
)


def percentile(
    values: Sequence[float],
    fraction: float,
) -> float | None:
    """Return a linearly interpolated percentile."""

    if not values:
        return None

    ordered = sorted(float(value) for value in values)

    if len(ordered) == 1:
        return ordered[0]

    position = fraction * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)

    if lower == upper:
        return ordered[lower]

    weight = position - lower

    return float(
        ordered[lower] * (1.0 - weight)
        + ordered[upper] * weight
    )


def descriptive_stats(
    values: Sequence[float],
) -> dict[str, float | int | None]:
    """Return standard descriptive statistics."""

    cleaned = [float(value) for value in values]

    if not cleaned:
        return {
            "n": 0,
            "mean": None,
            "p50": None,
            "p95": None,
            "p99": None,
            "min": None,
            "max": None,
        }

    return {
        "n": len(cleaned),
        "mean": float(statistics.fmean(cleaned)),
        "p50": percentile(cleaned, 0.50),
        "p95": percentile(cleaned, 0.95),
        "p99": percentile(cleaned, 0.99),
        "min": float(min(cleaned)),
        "max": float(max(cleaned)),
    }


def pearson(
    xs: Sequence[float],
    ys: Sequence[float],
) -> float | None:
    """Return the Pearson correlation coefficient."""

    if len(xs) != len(ys) or len(xs) < 2:
        return None

    x_values = [float(value) for value in xs]
    y_values = [float(value) for value in ys]

    mean_x = statistics.fmean(x_values)
    mean_y = statistics.fmean(y_values)

    numerator = sum(
        (x_value - mean_x) * (y_value - mean_y)
        for x_value, y_value in zip(
            x_values,
            y_values,
            strict=True,
        )
    )

    denominator_x = sum(
        (value - mean_x) ** 2
        for value in x_values
    )
    denominator_y = sum(
        (value - mean_y) ** 2
        for value in y_values
    )

    denominator = math.sqrt(
        denominator_x * denominator_y
    )

    if denominator == 0.0:
        return None

    return float(numerator / denominator)


def read_status_records(
    bag_path: Path,
    *,
    topic: str,
    storage_id: str,
) -> list[tuple[int, dict[str, Any]]]:
    """Read JSON status records from a ROS 2 bag."""

    import rosbag2_py
    from rclpy.serialization import deserialize_message
    from std_msgs.msg import String

    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(
            uri=str(bag_path),
            storage_id=storage_id,
        ),
        rosbag2_py.ConverterOptions("", ""),
    )

    topic_types = {
        entry.name: entry.type
        for entry in reader.get_all_topics_and_types()
    }

    topic_type = topic_types.get(topic)

    if topic_type is None:
        raise ValueError(
            f"Status topic {topic!r} is absent from {bag_path}."
        )

    if topic_type != "std_msgs/msg/String":
        raise ValueError(
            f"Expected std_msgs/msg/String for {topic!r}, "
            f"found {topic_type!r}."
        )

    records: list[tuple[int, dict[str, Any]]] = []

    while reader.has_next():
        current_topic, data, timestamp_ns = reader.read_next()

        if current_topic != topic:
            continue

        message = deserialize_message(data, String)

        try:
            payload = json.loads(message.data)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid status JSON at {timestamp_ns}: {exc}"
            ) from exc

        if not isinstance(payload, dict):
            raise ValueError(
                f"Status payload at {timestamp_ns} is not an object."
            )

        records.append((int(timestamp_ns), payload))

    return records


def _validate_fields(
    records: Sequence[tuple[int, dict[str, Any]]],
) -> None:
    missing: dict[str, int] = {
        field: 0
        for field in REQUIRED_FIELDS
    }

    for _timestamp_ns, payload in records:
        for field in REQUIRED_FIELDS:
            if field not in payload:
                missing[field] += 1

    missing = {
        field: count
        for field, count in missing.items()
        if count > 0
    }

    if missing:
        raise ValueError(
            "Status records are missing required workload fields: "
            f"{missing}"
        )


def analyse_records(
    records: Sequence[tuple[int, dict[str, Any]]],
    *,
    run_name: str,
    git_commit: str | None = None,
    bag_path: str | None = None,
    status_topic: str = DEFAULT_TOPIC,
) -> dict[str, Any]:
    """Calculate workload, displacement, and warm-up statistics."""

    if not records:
        raise ValueError("No TIM-MARS status records were supplied.")

    ordered_records = sorted(
        records,
        key=lambda record: record[0],
    )

    _validate_fields(ordered_records)

    start_ns = ordered_records[0][0]
    end_ns = ordered_records[-1][0]
    duration_s = max(0.0, (end_ns - start_ns) / 1e9)

    calls: list[dict[str, Any]] = []
    non_call_payloads: list[dict[str, Any]] = []

    for record_index, (timestamp_ns, payload) in enumerate(
        ordered_records
    ):
        backend_calls = int(
            payload["appearance_backend_calls"]
        )

        if backend_calls <= 0:
            non_call_payloads.append(payload)
            continue

        requested = int(
            payload["appearance_backend_requested"]
        )
        wall_ms = float(
            payload["appearance_backend_wall_ms"]
        )
        latency_ms = float(payload["lat_ms"])

        calls.append(
            {
                "call_index": len(calls),
                "status_record_index": record_index,
                "time_s": (timestamp_ns - start_ns) / 1e9,
                "backend_calls": backend_calls,
                "requested": requested,
                "returned": int(
                    payload["appearance_backend_returned"]
                ),
                "valid": int(
                    payload["appearance_backend_valid"]
                ),
                "wall_ms": wall_ms,
                "latency_ms": latency_ms,
                "callback_overhead_ms": latency_ms - wall_ms,
                "wall_ms_per_crop": (
                    wall_ms / requested
                    if requested > 0
                    else None
                ),
            }
        )

    call_payloads = [
        payload
        for _timestamp_ns, payload in ordered_records
        if int(payload["appearance_backend_calls"]) > 0
    ]

    wall_all = [
        float(call["wall_ms"])
        for call in calls
    ]
    latency_all = [
        float(payload["lat_ms"])
        for _timestamp_ns, payload in ordered_records
    ]
    latency_calls = [
        float(payload["lat_ms"])
        for payload in call_payloads
    ]
    latency_non_calls = [
        float(payload["lat_ms"])
        for payload in non_call_payloads
    ]
    callback_overhead = [
        float(call["callback_overhead_ms"])
        for call in calls
    ]

    first_call = calls[0] if calls else None
    largest_call = (
        max(calls, key=lambda call: float(call["wall_ms"]))
        if calls
        else None
    )

    median_wall_ms = (
        float(statistics.median(wall_all))
        if wall_all
        else None
    )

    # Classify the first invocation against later calls rather than
    # allowing the candidate warm-up call to inflate its own threshold.
    warmup_reference_wall = (
        wall_all[1:]
        if len(wall_all) > 1
        else []
    )
    warmup_reference_median_wall_ms = (
        float(statistics.median(warmup_reference_wall))
        if warmup_reference_wall
        else None
    )
    warmup_threshold_ms = (
        max(
            100.0,
            3.0 * warmup_reference_median_wall_ms,
        )
        if warmup_reference_median_wall_ms is not None
        else None
    )

    first_call_is_largest = bool(
        first_call is not None
        and largest_call is not None
        and first_call["call_index"]
        == largest_call["call_index"]
    )

    first_call_is_warmup_outlier = bool(
        first_call_is_largest
        and warmup_threshold_ms is not None
        and float(first_call["wall_ms"])
        > warmup_threshold_ms
    )

    steady_calls = (
        calls[1:]
        if first_call_is_warmup_outlier
        else calls
    )
    steady_wall = [
        float(call["wall_ms"])
        for call in steady_calls
    ]

    totals = {
        "status_records": len(ordered_records),
        "appearance_candidates": sum(
            int(payload["appearance_candidates"])
            for _timestamp_ns, payload in ordered_records
        ),
        "appearance_features_valid": sum(
            int(payload["appearance_features_valid"])
            for _timestamp_ns, payload in ordered_records
        ),
        "appearance_encoding_eligible": sum(
            int(payload["appearance_encoding_eligible"])
            for _timestamp_ns, payload in ordered_records
        ),
        "appearance_backend_calls": sum(
            int(payload["appearance_backend_calls"])
            for _timestamp_ns, payload in ordered_records
        ),
        "appearance_backend_requested": sum(
            int(payload["appearance_backend_requested"])
            for _timestamp_ns, payload in ordered_records
        ),
        "appearance_backend_returned": sum(
            int(payload["appearance_backend_returned"])
            for _timestamp_ns, payload in ordered_records
        ),
        "appearance_backend_valid": sum(
            int(payload["appearance_backend_valid"])
            for _timestamp_ns, payload in ordered_records
        ),
    }

    total_backend_wall_ms = sum(wall_all)
    steady_backend_wall_ms = sum(steady_wall)

    latency_call_stats = descriptive_stats(latency_calls)
    latency_non_call_stats = descriptive_stats(
        latency_non_calls
    )

    call_mean = latency_call_stats["mean"]
    non_call_mean = latency_non_call_stats["mean"]

    displacement_mean_ms = (
        float(call_mean) - float(non_call_mean)
        if call_mean is not None and non_call_mean is not None
        else None
    )

    grouped_values: dict[int, list[float]] = defaultdict(list)

    for call in calls:
        grouped_values[int(call["requested"])].append(
            float(call["wall_ms"])
        )

    grouped_by_requested = {
        str(requested): descriptive_stats(values)
        for requested, values in sorted(grouped_values.items())
    }

    ratios = {
        "status_records_per_second": (
            len(ordered_records) / duration_s
            if duration_s > 0.0
            else None
        ),
        "backend_call_record_fraction": (
            len(calls) / len(ordered_records)
        ),
        "backend_calls_per_second": (
            totals["appearance_backend_calls"] / duration_s
            if duration_s > 0.0
            else None
        ),
        "requested_crops_per_second": (
            totals["appearance_backend_requested"] / duration_s
            if duration_s > 0.0
            else None
        ),
        "requested_per_call": (
            totals["appearance_backend_requested"]
            / totals["appearance_backend_calls"]
            if totals["appearance_backend_calls"] > 0
            else None
        ),
        "returned_per_requested": (
            totals["appearance_backend_returned"]
            / totals["appearance_backend_requested"]
            if totals["appearance_backend_requested"] > 0
            else None
        ),
        "valid_per_requested": (
            totals["appearance_backend_valid"]
            / totals["appearance_backend_requested"]
            if totals["appearance_backend_requested"] > 0
            else None
        ),
        "backend_wall_fraction_of_run_all": (
            (total_backend_wall_ms / 1000.0) / duration_s
            if duration_s > 0.0
            else None
        ),
        "backend_wall_fraction_of_run_steady_state": (
            (steady_backend_wall_ms / 1000.0) / duration_s
            if duration_s > 0.0
            else None
        ),
    }

    requested_counts = [
        float(call["requested"])
        for call in calls
    ]

    correlations = {
        "requested_count_vs_backend_wall": pearson(
            requested_counts,
            wall_all,
        ),
        "backend_wall_vs_callback_latency": pearson(
            wall_all,
            latency_calls,
        ),
    }

    integrity = {
        "all_required_fields_present": True,
        "has_backend_calls": bool(calls),
        "has_positive_backend_wall_time": any(
            value > 0.0
            for value in wall_all
        ),
        "non_call_records_with_nonzero_backend_wall_ms": sum(
            1
            for payload in non_call_payloads
            if float(
                payload["appearance_backend_wall_ms"]
            ) != 0.0
        ),
        "returned_not_greater_than_requested": (
            totals["appearance_backend_returned"]
            <= totals["appearance_backend_requested"]
        ),
        "valid_not_greater_than_returned": (
            totals["appearance_backend_valid"]
            <= totals["appearance_backend_returned"]
        ),
    }

    return {
        "schema": SUMMARY_SCHEMA,
        "run_name": run_name,
        "git_commit": git_commit,
        "bag_path": bag_path,
        "status_topic": status_topic,
        "duration_s": duration_s,
        "totals": totals,
        "ratios": ratios,
        "backend_wall_ms_all": descriptive_stats(wall_all),
        "backend_wall_ms_steady_state": descriptive_stats(
            steady_wall
        ),
        "total_backend_wall_ms_all": total_backend_wall_ms,
        "total_backend_wall_ms_steady_state": (
            steady_backend_wall_ms
        ),
        "tim_mars_latency_all_ms": descriptive_stats(
            latency_all
        ),
        "tim_mars_latency_backend_call_ms": (
            latency_call_stats
        ),
        "tim_mars_latency_non_call_ms": (
            latency_non_call_stats
        ),
        "callback_overhead_ms": descriptive_stats(
            callback_overhead
        ),
        "callback_latency_displacement_mean_ms": (
            displacement_mean_ms
        ),
        "grouped_backend_wall_ms_by_requested_crops": (
            grouped_by_requested
        ),
        "correlations": correlations,
        "warmup": {
            "first_call": first_call,
            "largest_call": largest_call,
            "median_backend_wall_ms": median_wall_ms,
            "warmup_reference_median_backend_wall_ms": (
                warmup_reference_median_wall_ms
            ),
            "warmup_threshold_ms": warmup_threshold_ms,
            "first_call_is_largest": first_call_is_largest,
            "first_call_is_warmup_outlier": (
                first_call_is_warmup_outlier
            ),
            "excluded_backend_calls_from_steady_state": (
                1
                if first_call_is_warmup_outlier
                else 0
            ),
        },
        "integrity": integrity,
    }


def _format_value(
    value: object,
    *,
    digits: int = 3,
) -> str:
    if value is None:
        return "n/a"

    if isinstance(value, bool):
        return "PASS" if value else "FAIL"

    if isinstance(value, float):
        return f"{value:.{digits}f}"

    return str(value)


def render_markdown(summary: dict[str, Any]) -> str:
    """Render a human-readable workload report."""

    totals = summary["totals"]
    ratios = summary["ratios"]
    warmup = summary["warmup"]
    integrity = summary["integrity"]

    lines = [
        "# TIM-MARS CPU ReID workload",
        "",
        f"- Run: `{summary['run_name']}`",
        f"- Commit: `{summary.get('git_commit')}`",
        f"- Bag: `{summary.get('bag_path')}`",
        f"- Duration: {_format_value(summary['duration_s'])} s",
        f"- Schema: `{summary['schema']}`",
        "",
        "## Workload totals",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]

    for key, value in totals.items():
        lines.append(f"| `{key}` | {value} |")

    lines.extend(
        [
            "",
            "## Backend timing",
            "",
            "| Population | n | Mean | p50 | p95 | p99 | Max |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for label, key in (
        ("all calls", "backend_wall_ms_all"),
        (
            "steady state",
            "backend_wall_ms_steady_state",
        ),
    ):
        values = summary[key]
        lines.append(
            f"| {label} "
            f"| {_format_value(values['n'])} "
            f"| {_format_value(values['mean'])} "
            f"| {_format_value(values['p50'])} "
            f"| {_format_value(values['p95'])} "
            f"| {_format_value(values['p99'])} "
            f"| {_format_value(values['max'])} |"
        )

    lines.extend(
        [
            "",
            "## Callback displacement",
            "",
            "| Metric | Value |",
            "|---|---:|",
            (
                "| backend-call latency mean (ms) | "
                f"{_format_value(summary['tim_mars_latency_backend_call_ms']['mean'])} |"
            ),
            (
                "| non-call latency mean (ms) | "
                f"{_format_value(summary['tim_mars_latency_non_call_ms']['mean'])} |"
            ),
            (
                "| mean displacement (ms) | "
                f"{_format_value(summary['callback_latency_displacement_mean_ms'])} |"
            ),
            (
                "| callback overhead mean (ms) | "
                f"{_format_value(summary['callback_overhead_ms']['mean'])} |"
            ),
            (
                "| backend/callback correlation | "
                f"{_format_value(summary['correlations']['backend_wall_vs_callback_latency'], digits=6)} |"
            ),
            "",
            "## Derived load",
            "",
            "| Metric | Value |",
            "|---|---:|",
        ]
    )

    for key, value in ratios.items():
        lines.append(
            f"| `{key}` | {_format_value(value, digits=6)} |"
        )

    lines.extend(
        [
            "",
            "## Warm-up classification",
            "",
            "| Metric | Value |",
            "|---|---:|",
            (
                "| first call is largest | "
                f"{_format_value(warmup['first_call_is_largest'])} |"
            ),
            (
                "| first call is warm-up outlier | "
                f"{_format_value(warmup['first_call_is_warmup_outlier'])} |"
            ),
            (
                "| warm-up threshold (ms) | "
                f"{_format_value(warmup['warmup_threshold_ms'])} |"
            ),
            (
                "| calls excluded from steady state | "
                f"{warmup['excluded_backend_calls_from_steady_state']} |"
            ),
            "",
            "## Integrity",
            "",
            "| Check | Result |",
            "|---|---:|",
        ]
    )

    for key, value in integrity.items():
        passed = (
            value is True
            or (
                key
                == "non_call_records_with_nonzero_backend_wall_ms"
                and value == 0
            )
        )
        lines.append(
            f"| `{key}` | {'PASS' if passed else 'FAIL'} |"
        )

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyse synchronous CPU ReID workload from "
            "/target_memory_mars/status."
        )
    )
    parser.add_argument("bag")
    parser.add_argument(
        "--topic",
        default=DEFAULT_TOPIC,
    )
    parser.add_argument(
        "--storage-id",
        default="mcap",
    )
    parser.add_argument(
        "--run-name",
        default=None,
    )
    parser.add_argument(
        "--git-commit",
        default=None,
    )
    parser.add_argument(
        "--json-out",
        required=True,
    )
    parser.add_argument(
        "--markdown-out",
        required=True,
    )
    parser.add_argument(
        "--require-live-wall-time",
        action="store_true",
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

    summary = analyse_records(
        records,
        run_name=args.run_name or bag_path.name,
        git_commit=args.git_commit,
        bag_path=str(bag_path),
        status_topic=args.topic,
    )

    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    json_path.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_markdown(summary),
        encoding="utf-8",
    )

    print(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )

    integrity = summary["integrity"]

    if (
        args.require_live_wall_time
        and not integrity["has_positive_backend_wall_time"]
    ):
        raise SystemExit(
            "ERROR: no positive live backend wall time was recorded."
        )

    if not integrity["returned_not_greater_than_requested"]:
        raise SystemExit(
            "ERROR: returned crops exceed requested crops."
        )

    if not integrity["valid_not_greater_than_returned"]:
        raise SystemExit(
            "ERROR: valid embeddings exceed returned embeddings."
        )

    if (
        integrity[
            "non_call_records_with_nonzero_backend_wall_ms"
        ]
        != 0
    ):
        raise SystemExit(
            "ERROR: non-call records contain backend wall time."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
