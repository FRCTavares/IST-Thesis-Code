#!/usr/bin/env python3
"""Analyse retained raw resource telemetry for final Issue #32 reporting."""

from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Iterable
import json
import math
from pathlib import Path
import statistics
from typing import Any


SCHEMA = "p032_final_resource_analysis_v1"
DEFAULT_ARCHITECTURE_GROUPS = (
    "detector",
    "tracker",
    "tim",
    "controller",
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        stripped = line.strip()
        if not stripped:
            continue

        payload = json.loads(stripped)
        if not isinstance(payload, dict):
            raise ValueError(
                f"{path}:{line_number}: expected JSON object"
            )

        rows.append(payload)

    return rows


def finite_values(values: Iterable[Any]) -> list[float]:
    result: list[float] = []

    for value in values:
        if value is None:
            continue

        number = float(value)
        if math.isfinite(number):
            result.append(number)

    return result


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        raise ValueError("cannot compute percentile of empty data")

    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]

    position = max(0.0, min(1.0, fraction)) * (
        len(ordered) - 1
    )
    lower = int(math.floor(position))
    upper = int(math.ceil(position))

    if lower == upper:
        return ordered[lower]

    weight = position - lower
    return (
        ordered[lower] * (1.0 - weight)
        + ordered[upper] * weight
    )


def descriptive_stats(values: Iterable[Any]) -> dict[str, Any]:
    finite = finite_values(values)

    if not finite:
        return {
            "n": 0,
            "mean": None,
            "std": None,
            "minimum": None,
            "p50": None,
            "p90": None,
            "p95": None,
            "p99": None,
            "maximum": None,
        }

    return {
        "n": len(finite),
        "mean": statistics.fmean(finite),
        "std": statistics.pstdev(finite),
        "minimum": min(finite),
        "p50": percentile(finite, 0.50),
        "p90": percentile(finite, 0.90),
        "p95": percentile(finite, 0.95),
        "p99": percentile(finite, 0.99),
        "maximum": max(finite),
    }


def records_at_or_after(
    records: Iterable[dict[str, Any]],
    *,
    timestamp_key: str,
    threshold_ns: int,
) -> list[dict[str, Any]]:
    return [
        record
        for record in records
        if record.get(timestamp_key) is not None
        and int(record[timestamp_key]) >= int(threshold_ns)
    ]


def records_in_window(
    records: Iterable[dict[str, Any]],
    *,
    timestamp_key: str,
    start_ns: int,
    end_ns: int,
) -> list[dict[str, Any]]:
    return [
        record
        for record in records
        if record.get(timestamp_key) is not None
        and int(record[timestamp_key]) >= int(start_ns)
        and int(record[timestamp_key]) <= int(end_ns)
    ]


def metric_windows(
    records: list[dict[str, Any]],
    *,
    timestamp_key: str,
    value_key: str,
    steady_start_ns: int,
) -> dict[str, Any]:
    steady = records_at_or_after(
        records,
        timestamp_key=timestamp_key,
        threshold_ns=steady_start_ns,
    )

    return {
        "all": descriptive_stats(
            record.get(value_key)
            for record in records
        ),
        "steady_state": descriptive_stats(
            record.get(value_key)
            for record in steady
        ),
    }


def summarise_resource_groups(
    records: list[dict[str, Any]],
    *,
    steady_start_ns: int,
) -> dict[str, Any]:
    names = sorted({
        str(record["group"])
        for record in records
        if record.get("group") is not None
    })

    groups: dict[str, Any] = {}

    for name in names:
        subset = [
            record
            for record in records
            if str(record.get("group")) == name
        ]

        groups[name] = {
            "sample_count": len(subset),
            "cpu_percent": metric_windows(
                subset,
                timestamp_key="sample_monotonic_ns",
                value_key="cpu_percent",
                steady_start_ns=steady_start_ns,
            ),
            "rss_kib": metric_windows(
                subset,
                timestamp_key="sample_monotonic_ns",
                value_key="rss_kib",
                steady_start_ns=steady_start_ns,
            ),
            "member_count": metric_windows(
                subset,
                timestamp_key="sample_monotonic_ns",
                value_key="member_count",
                steady_start_ns=steady_start_ns,
            ),
        }

    return groups


def build_architecture_totals(
    records: list[dict[str, Any]],
    *,
    requested_groups: Iterable[str],
    steady_start_ns: int,
) -> dict[str, Any]:
    requested = tuple(dict.fromkeys(
        str(group).strip()
        for group in requested_groups
        if str(group).strip()
    ))

    observed = {
        str(record["group"])
        for record in records
        if record.get("group") is not None
    }

    included = tuple(
        group
        for group in requested
        if group in observed
    )
    missing = tuple(
        group
        for group in requested
        if group not in observed
    )

    by_timestamp: dict[int, dict[str, dict[str, Any]]] = defaultdict(dict)

    for record in records:
        group = str(record.get("group", ""))
        timestamp = record.get("sample_monotonic_ns")

        if group not in included or timestamp is None:
            continue

        by_timestamp[int(timestamp)][group] = record

    complete_rows: list[dict[str, Any]] = []

    for timestamp in sorted(by_timestamp):
        group_rows = by_timestamp[timestamp]

        if not included or any(
            group not in group_rows
            for group in included
        ):
            continue

        cpu_values = [
            group_rows[group].get("cpu_percent")
            for group in included
        ]
        rss_values = [
            group_rows[group].get("rss_kib")
            for group in included
        ]

        cpu_finite = finite_values(cpu_values)
        rss_finite = finite_values(rss_values)

        complete_rows.append({
            "sample_monotonic_ns": timestamp,
            "cpu_percent": (
                sum(cpu_finite)
                if len(cpu_finite) == len(included)
                else None
            ),
            "rss_kib": (
                sum(rss_finite)
                if len(rss_finite) == len(included)
                else None
            ),
        })

    return {
        "requested_groups": list(requested),
        "included_groups": list(included),
        "missing_requested_groups": list(missing),
        "complete_timestamp_count": len(complete_rows),
        "cpu_percent": metric_windows(
            complete_rows,
            timestamp_key="sample_monotonic_ns",
            value_key="cpu_percent",
            steady_start_ns=steady_start_ns,
        ),
        "rss_kib": metric_windows(
            complete_rows,
            timestamp_key="sample_monotonic_ns",
            value_key="rss_kib",
            steady_start_ns=steady_start_ns,
        ),
    }


def summarise_hardware(
    records: list[dict[str, Any]],
    *,
    steady_start_ns: int,
) -> dict[str, Any]:
    metrics = (
        "temperature_c",
        "arm_frequency_hz",
        "core_voltage_v",
        "mem_available_kib",
    )

    result = {
        metric: metric_windows(
            records,
            timestamp_key="monotonic_ns",
            value_key=metric,
            steady_start_ns=steady_start_ns,
        )
        for metric in metrics
    }

    throttle_values = [
        int(record["throttled"])
        for record in records
        if record.get("throttled") is not None
    ]
    steady_records = records_at_or_after(
        records,
        timestamp_key="monotonic_ns",
        threshold_ns=steady_start_ns,
    )
    steady_throttle = [
        int(record["throttled"])
        for record in steady_records
        if record.get("throttled") is not None
    ]

    result["throttling"] = {
        "all": {
            "sample_count": len(throttle_values),
            "nonzero_count": sum(
                value != 0
                for value in throttle_values
            ),
            "maximum_value": (
                max(throttle_values)
                if throttle_values
                else None
            ),
        },
        "steady_state": {
            "sample_count": len(steady_throttle),
            "nonzero_count": sum(
                value != 0
                for value in steady_throttle
            ),
            "maximum_value": (
                max(steady_throttle)
                if steady_throttle
                else None
            ),
        },
    }

    result["samples_with_errors"] = {
        "all": sum(
            bool(record.get("errors"))
            for record in records
        ),
        "steady_state": sum(
            bool(record.get("errors"))
            for record in steady_records
        ),
    }

    return result


def analyse(
    resource_records: list[dict[str, Any]],
    hardware_records: list[dict[str, Any]],
    *,
    warm_up_s: float,
    architecture_groups: Iterable[str],
    analysis_start_ns: int | None = None,
    analysis_end_ns: int | None = None,
) -> dict[str, Any]:
    resource_times = [
        int(record["sample_monotonic_ns"])
        for record in resource_records
        if record.get("sample_monotonic_ns") is not None
    ]
    hardware_times = [
        int(record["monotonic_ns"])
        for record in hardware_records
        if record.get("monotonic_ns") is not None
    ]

    if not resource_times:
        raise ValueError("no resource monotonic timestamps")
    if not hardware_times:
        raise ValueError("no hardware-health monotonic timestamps")
    if warm_up_s < 0.0:
        raise ValueError("warm_up_s must be non-negative")

    if analysis_start_ns is None:
        start_ns = min(
            min(resource_times),
            min(hardware_times),
        )
        start_source = "earliest_retained_sample"
    else:
        start_ns = int(analysis_start_ns)
        start_source = "explicit_argument"

    if analysis_end_ns is None:
        end_ns = max(
            max(resource_times),
            max(hardware_times),
        )
        end_source = "latest_retained_sample"
    else:
        end_ns = int(analysis_end_ns)
        end_source = "explicit_argument"

    if end_ns < start_ns:
        raise ValueError(
            "analysis_end_ns must not precede analysis_start_ns"
        )

    resource_window = records_in_window(
        resource_records,
        timestamp_key="sample_monotonic_ns",
        start_ns=start_ns,
        end_ns=end_ns,
    )
    hardware_window = records_in_window(
        hardware_records,
        timestamp_key="monotonic_ns",
        start_ns=start_ns,
        end_ns=end_ns,
    )

    if not resource_window:
        raise ValueError(
            "no resource samples inside analysis window"
        )
    if not hardware_window:
        raise ValueError(
            "no hardware-health samples inside analysis window"
        )

    steady_start_ns = (
        start_ns
        + int(round(float(warm_up_s) * 1e9))
    )

    groups = summarise_resource_groups(
        resource_window,
        steady_start_ns=steady_start_ns,
    )
    architecture = build_architecture_totals(
        resource_window,
        requested_groups=architecture_groups,
        steady_start_ns=steady_start_ns,
    )
    hardware = summarise_hardware(
        hardware_window,
        steady_start_ns=steady_start_ns,
    )

    return {
        "schema": SCHEMA,
        "measurement_window": {
            "analysis_start_monotonic_ns": start_ns,
            "analysis_start_source": start_source,
            "analysis_end_monotonic_ns": end_ns,
            "analysis_end_source": end_source,
            "observed_span_s": (
                max(0, end_ns - start_ns) / 1e9
            ),
            "warm_up_s": float(warm_up_s),
            "steady_state_start_monotonic_ns": steady_start_ns,
        },
        "resource_sample_count": len(resource_window),
        "hardware_sample_count": len(hardware_window),
        "resource_groups": groups,
        "architecture_total": architecture,
        "hardware": hardware,
        "integrity": {
            "resource_records_have_known_sample_schema": all(
                record.get("schema")
                == "p044_process_group_sample_v1"
                for record in resource_window
            ),
            "hardware_records_have_known_sample_schema": all(
                record.get("schema")
                == "p044_hardware_health_sample_v1"
                for record in hardware_window
            ),
            "architecture_has_complete_samples": (
                architecture["complete_timestamp_count"] > 0
            ),
            "steady_state_resource_samples_present": any(
                group["cpu_percent"]["steady_state"]["n"] > 0
                for group in groups.values()
            ),
            "steady_state_hardware_samples_present": (
                hardware["temperature_c"]["steady_state"]["n"] > 0
            ),
        },
        "claim_boundary": {
            "raw_sampler_schemas_modified": False,
            "historical_reports_rewritten": False,
            "core_voltage_is_power_measurement": False,
            "electrical_power_claim_available": False,
            "resource_totals_include_only_listed_architecture_groups": True,
        },
    }


def format_number(value: Any, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, int):
        return str(value)
    return f"{float(value):.{digits}f}"


def render_markdown(summary: dict[str, Any]) -> str:
    window = summary["measurement_window"]
    architecture = summary["architecture_total"]
    hardware = summary["hardware"]

    lines = [
        "# Issue #32 Final Resource Analysis",
        "",
        f"- Schema: `{summary['schema']}`",
        f"- Observed span: {format_number(window['observed_span_s'])} s",
        f"- Warm-up excluded from steady state: {format_number(window['warm_up_s'])} s",
        (
            "- Architecture groups included: "
            + ", ".join(architecture["included_groups"])
        ),
        (
            "- Missing requested groups: "
            + (
                ", ".join(architecture["missing_requested_groups"])
                if architecture["missing_requested_groups"]
                else "none"
            )
        ),
        "",
        "## Architecture total",
        "",
        "| Metric | Population | n | Mean | Std | p50 | p90 | p95 | p99 | Max |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    for metric_name, label in (
        ("cpu_percent", "CPU (%)"),
        ("rss_kib", "RSS (KiB)"),
    ):
        for population in ("all", "steady_state"):
            stats = architecture[metric_name][population]
            lines.append(
                "| "
                + " | ".join([
                    label,
                    population,
                    str(stats["n"]),
                    format_number(stats["mean"]),
                    format_number(stats["std"]),
                    format_number(stats["p50"]),
                    format_number(stats["p90"]),
                    format_number(stats["p95"]),
                    format_number(stats["p99"]),
                    format_number(stats["maximum"]),
                ])
                + " |"
            )

    lines.extend([
        "",
        "## Hardware health",
        "",
        "| Metric | Population | n | Mean | Std | p50 | p90 | p95 | p99 | Max |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])

    for metric_name, label in (
        ("temperature_c", "Temperature (C)"),
        ("arm_frequency_hz", "ARM frequency (Hz)"),
        ("mem_available_kib", "Available memory (KiB)"),
    ):
        for population in ("all", "steady_state"):
            stats = hardware[metric_name][population]
            lines.append(
                "| "
                + " | ".join([
                    label,
                    population,
                    str(stats["n"]),
                    format_number(stats["mean"]),
                    format_number(stats["std"]),
                    format_number(stats["p50"]),
                    format_number(stats["p90"]),
                    format_number(stats["p95"]),
                    format_number(stats["p99"]),
                    format_number(stats["maximum"]),
                ])
                + " |"
            )

    throttle = hardware["throttling"]
    lines.extend([
        "",
        "## Integrity / boundaries",
        "",
        (
            "- Non-zero throttle samples, all: "
            f"{throttle['all']['nonzero_count']}"
        ),
        (
            "- Non-zero throttle samples, steady state: "
            f"{throttle['steady_state']['nonzero_count']}"
        ),
        "- Core voltage is telemetry, not electrical power.",
        "- This analyser does not rewrite historical sampler output.",
        "",
    ])

    return "\n".join(lines)


def parse_groups(raw: str) -> tuple[str, ...]:
    return tuple(
        item.strip()
        for item in raw.split(",")
        if item.strip()
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--resources-samples",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--hardware-samples",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--output-json",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--output-markdown",
        type=Path,
    )
    parser.add_argument(
        "--warm-up-s",
        type=float,
        default=60.0,
    )
    parser.add_argument(
        "--analysis-start-monotonic-ns",
        type=int,
    )
    parser.add_argument(
        "--analysis-end-monotonic-ns",
        type=int,
    )
    parser.add_argument(
        "--architecture-groups",
        default=",".join(DEFAULT_ARCHITECTURE_GROUPS),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    summary = analyse(
        read_jsonl(args.resources_samples),
        read_jsonl(args.hardware_samples),
        warm_up_s=args.warm_up_s,
        architecture_groups=parse_groups(
            args.architecture_groups
        ),
        analysis_start_ns=args.analysis_start_monotonic_ns,
        analysis_end_ns=args.analysis_end_monotonic_ns,
    )

    args.output_json.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    args.output_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if args.output_markdown is not None:
        args.output_markdown.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        args.output_markdown.write_text(
            render_markdown(summary),
            encoding="utf-8",
        )

    print(
        json.dumps(
            {
                "schema": summary["schema"],
                "output_json": str(args.output_json),
                "output_markdown": (
                    str(args.output_markdown)
                    if args.output_markdown is not None
                    else None
                ),
                "architecture_groups": summary[
                    "architecture_total"
                ]["included_groups"],
                "missing_requested_groups": summary[
                    "architecture_total"
                ]["missing_requested_groups"],
                "steady_state_cpu_n": summary[
                    "architecture_total"
                ]["cpu_percent"]["steady_state"]["n"],
                "steady_state_temperature_n": summary[
                    "hardware"
                ]["temperature_c"]["steady_state"]["n"],
            },
            indent=2,
            sort_keys=True,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
