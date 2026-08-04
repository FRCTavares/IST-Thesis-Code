#!/usr/bin/env python3
"""Validate bounded P044 sustained-operation evidence."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterable
import json
import math
from pathlib import Path
import statistics
from typing import Any


SCHEMA = "p044_sustained_reid_soak_analysis_v1"
WINDOW_NAMES = ("early", "middle", "late")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def finite_values(
    values: Iterable[Any],
) -> list[float]:
    resolved: list[float] = []

    for value in values:
        if value is None:
            continue

        number = float(value)

        if math.isfinite(number):
            resolved.append(number)

    return resolved


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


def metric_summary(values: Iterable[Any]) -> dict[str, Any]:
    finite = finite_values(values)

    if not finite:
        return {
            "count": 0,
            "minimum": None,
            "mean": None,
            "p50": None,
            "p95": None,
            "maximum": None,
        }

    return {
        "count": len(finite),
        "minimum": min(finite),
        "mean": statistics.fmean(finite),
        "p50": percentile(finite, 0.50),
        "p95": percentile(finite, 0.95),
        "maximum": max(finite),
    }


def classify_window(
    timestamp_ns: int,
    *,
    start_ns: int,
    duration_ns: int,
) -> str | None:
    offset = int(timestamp_ns) - int(start_ns)

    if offset < 0 or offset > int(duration_ns):
        return None

    fraction = offset / max(1, int(duration_ns))

    if fraction < 1.0 / 3.0:
        return "early"

    if fraction < 2.0 / 3.0:
        return "middle"

    return "late"


def windowed_metric(
    records: Iterable[dict[str, Any]],
    *,
    timestamp_key: str,
    value_key: str,
    start_ns: int,
    duration_ns: int,
    predicate: Callable[[dict[str, Any]], bool] | None = None,
) -> dict[str, dict[str, Any]]:
    values: dict[str, list[Any]] = {
        name: []
        for name in WINDOW_NAMES
    }

    for record in records:
        if predicate is not None and not predicate(record):
            continue

        timestamp = record.get(timestamp_key)
        value = record.get(value_key)

        if timestamp is None:
            continue

        window = classify_window(
            int(timestamp),
            start_ns=start_ns,
            duration_ns=duration_ns,
        )

        if window is not None:
            values[window].append(value)

    return {
        name: metric_summary(values[name])
        for name in WINDOW_NAMES
    }


def drift_within_limit(
    early: float | None,
    late: float | None,
    *,
    maximum_ratio: float,
    absolute_allowance: float,
) -> bool:
    if early is None or late is None:
        return False

    permitted = max(
        float(early) * float(maximum_ratio),
        float(early) + float(absolute_allowance),
    )
    return float(late) <= permitted


def require(
    condition: bool,
    reason: str,
    violations: list[str],
) -> None:
    if not condition:
        violations.append(reason)


def require_window_counts(
    summary: dict[str, dict[str, Any]],
    *,
    minimum: int,
    label: str,
    violations: list[str],
) -> None:
    for name in WINDOW_NAMES:
        require(
            int(summary[name]["count"]) >= minimum,
            f"{label}_{name}_sample_count",
            violations,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collector-summary", required=True, type=Path)
    parser.add_argument("--collector-events", required=True, type=Path)
    parser.add_argument("--relay-summary", required=True, type=Path)
    parser.add_argument("--resources-summary", required=True, type=Path)
    parser.add_argument("--resources-samples", required=True, type=Path)
    parser.add_argument("--health-summary", required=True, type=Path)
    parser.add_argument("--health-samples", required=True, type=Path)
    parser.add_argument("--duration-s", required=True, type=float)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--maximum-temperature-c", type=float, default=80.0)
    parser.add_argument(
        "--minimum-memory-available-mib",
        type=float,
        default=512.0,
    )
    args = parser.parse_args()

    collector = read_json(args.collector_summary)
    relay = read_json(args.relay_summary)
    resources = read_json(args.resources_summary)
    health = read_json(args.health_summary)

    events = read_jsonl(args.collector_events)
    resource_samples = read_jsonl(args.resources_samples)
    health_samples = read_jsonl(args.health_samples)

    relevant_event_times = [
        int(event["received_monotonic_ns"])
        for event in events
        if event.get("type") in {
            "timing",
            "reid_request",
            "reid_result",
        }
        and event.get("received_monotonic_ns") is not None
    ]

    if not relevant_event_times:
        raise SystemExit(
            "ERROR: no timing or ReID event timestamps were recorded."
        )

    start_ns = min(relevant_event_times)
    duration_ns = int(round(args.duration_s * 1e9))

    timing_predicate = lambda row: row.get("type") == "timing"
    successful_result_predicate = lambda row: (
        row.get("type") == "reid_result"
        and bool(row.get("succeeded"))
    )

    detector_infer = windowed_metric(
        events,
        timestamp_key="received_monotonic_ns",
        value_key="infer_ms",
        start_ns=start_ns,
        duration_ns=duration_ns,
        predicate=timing_predicate,
    )
    detector_e2e = windowed_metric(
        events,
        timestamp_key="received_monotonic_ns",
        value_key="e2e_det_ms",
        start_ns=start_ns,
        duration_ns=duration_ns,
        predicate=timing_predicate,
    )
    detector_cadence = windowed_metric(
        events,
        timestamp_key="received_monotonic_ns",
        value_key="pub_dt_ms",
        start_ns=start_ns,
        duration_ns=duration_ns,
        predicate=timing_predicate,
    )
    reid_worker = windowed_metric(
        events,
        timestamp_key="received_monotonic_ns",
        value_key="worker_ms",
        start_ns=start_ns,
        duration_ns=duration_ns,
        predicate=successful_result_predicate,
    )
    reid_e2e = windowed_metric(
        events,
        timestamp_key="received_monotonic_ns",
        value_key="end_to_end_ms",
        start_ns=start_ns,
        duration_ns=duration_ns,
        predicate=successful_result_predicate,
    )

    resource_windows: dict[str, Any] = {}

    for group_name in ("perception", "tim", "relay"):
        predicate = lambda row, expected=group_name: (
            row.get("group") == expected
        )

        resource_windows[group_name] = {
            "cpu_percent": windowed_metric(
                resource_samples,
                timestamp_key="sample_monotonic_ns",
                value_key="cpu_percent",
                start_ns=start_ns,
                duration_ns=duration_ns,
                predicate=predicate,
            ),
            "rss_kib": windowed_metric(
                resource_samples,
                timestamp_key="sample_monotonic_ns",
                value_key="rss_kib",
                start_ns=start_ns,
                duration_ns=duration_ns,
                predicate=predicate,
            ),
        }

    health_windows = {
        "temperature_c": windowed_metric(
            health_samples,
            timestamp_key="monotonic_ns",
            value_key="temperature_c",
            start_ns=start_ns,
            duration_ns=duration_ns,
        ),
        "mem_available_kib": windowed_metric(
            health_samples,
            timestamp_key="monotonic_ns",
            value_key="mem_available_kib",
            start_ns=start_ns,
            duration_ns=duration_ns,
        ),
        "arm_frequency_hz": windowed_metric(
            health_samples,
            timestamp_key="monotonic_ns",
            value_key="arm_frequency_hz",
            start_ns=start_ns,
            duration_ns=duration_ns,
        ),
    }

    violations: list[str] = []

    relay_counters = relay.get("counters", {})
    claim_boundary = relay.get("claim_boundary", {})

    require(
        relay.get("schema")
        == "p044_soak_input_relay_summary_v1",
        "relay_schema",
        violations,
    )
    require(
        int(relay_counters.get("images_received", 0)) > 0,
        "relay_no_images",
        violations,
    )
    require(
        int(relay_counters.get("tracks_received", 0)) > 0,
        "relay_no_tracks",
        violations,
    )
    require(
        relay_counters.get("images_received")
        == relay_counters.get("images_published"),
        "relay_image_accounting",
        violations,
    )
    require(
        relay_counters.get("tracks_received")
        == relay_counters.get("tracks_published"),
        "relay_track_accounting",
        violations,
    )
    require(
        int(relay_counters.get("image_publication_errors", -1)) == 0,
        "relay_image_publication_errors",
        violations,
    )
    require(
        int(relay_counters.get("track_publication_errors", -1)) == 0,
        "relay_track_publication_errors",
        violations,
    )
    require(
        int(relay.get("source_image_rewinds", 0)) >= 1,
        "relay_image_rewind_not_observed",
        violations,
    )
    require(
        int(relay.get("source_track_rewinds", 0)) >= 1,
        "relay_track_rewind_not_observed",
        violations,
    )
    require(
        claim_boundary.get("cpu_mars_authoritative") is True,
        "claim_cpu_mars_not_authoritative",
        violations,
    )
    require(
        claim_boundary.get("repvgg_observational") is True,
        "claim_repvgg_not_observational",
        violations,
    )
    require(
        claim_boundary.get("replayed_host_timing_cleared") is True,
        "claim_replayed_host_timing_not_cleared",
        violations,
    )
    require(
        claim_boundary.get("canonical_policy_changed") is False,
        "claim_canonical_policy_changed",
        violations,
    )

    counts = collector.get("counts", {})
    reid = collector.get("reid", {})
    executor = reid.get("latest_executor", {})
    transport = reid.get("latest_tim_transport", {})

    require(
        collector.get("condition") == "sustained_soak",
        "collector_condition",
        violations,
    )
    require(
        int(counts.get("timing", 0)) > 0,
        "collector_no_timing",
        violations,
    )
    require(
        int(counts.get("requests", 0)) > 0,
        "collector_no_requests",
        violations,
    )
    require(
        int(counts.get("successful_results", 0)) > 0,
        "collector_no_successful_results",
        violations,
    )
    require(
        int(counts.get("failed_results", -1)) == 0,
        "collector_failed_results",
        violations,
    )
    require(
        int(executor.get("failed", -1)) == 0,
        "executor_failures",
        violations,
    )
    require(
        int(executor.get("queued", -1)) == 0,
        "executor_queue_not_drained",
        violations,
    )
    require(
        executor.get("in_flight_request_id") is None,
        "executor_in_flight_not_drained",
        violations,
    )
    require(
        int(reid.get("maximum_engine_active_calls", 0)) <= 1,
        "hailo_execution_not_serialized",
        violations,
    )
    require(
        int(transport.get("in_flight", -1)) == 0,
        "tim_in_flight_not_drained",
        violations,
    )
    require(
        int(transport.get("accepted_results", 0)) > 0,
        "tim_no_accepted_observations",
        violations,
    )

    require(
        health.get("schema")
        == "p044_hardware_health_summary_v1",
        "health_schema",
        violations,
    )
    require(
        int(health.get("sample_count", 0))
        >= max(6, int(args.duration_s / 10.0)),
        "health_sample_count",
        violations,
    )
    require(
        int(health.get("samples_with_errors", -1)) == 0,
        "health_sampling_errors",
        violations,
    )
    require(
        int(health.get("nonzero_throttle_sample_count", -1)) == 0,
        "nonzero_throttle_observed",
        violations,
    )

    temperature_maximum = (
        health.get("temperature_c", {}).get("maximum")
    )
    require(
        temperature_maximum is not None
        and float(temperature_maximum)
        <= args.maximum_temperature_c,
        "temperature_limit",
        violations,
    )

    minimum_memory_kib = (
        health.get("mem_available_kib", {}).get("minimum")
    )
    require(
        minimum_memory_kib is not None
        and float(minimum_memory_kib)
        >= args.minimum_memory_available_mib * 1024.0,
        "minimum_available_memory",
        violations,
    )

    require_window_counts(
        detector_infer,
        minimum=10,
        label="detector_infer",
        violations=violations,
    )
    require_window_counts(
        detector_e2e,
        minimum=10,
        label="detector_e2e",
        violations=violations,
    )
    require_window_counts(
        reid_worker,
        minimum=3,
        label="reid_worker",
        violations=violations,
    )
    require_window_counts(
        reid_e2e,
        minimum=3,
        label="reid_e2e",
        violations=violations,
    )
    require_window_counts(
        health_windows["temperature_c"],
        minimum=3,
        label="temperature",
        violations=violations,
    )

    require(
        drift_within_limit(
            detector_infer["early"]["mean"],
            detector_infer["late"]["mean"],
            maximum_ratio=1.50,
            absolute_allowance=2.0,
        ),
        "detector_infer_drift",
        violations,
    )
    require(
        drift_within_limit(
            detector_e2e["early"]["mean"],
            detector_e2e["late"]["mean"],
            maximum_ratio=1.50,
            absolute_allowance=5.0,
        ),
        "detector_e2e_drift",
        violations,
    )
    require(
        drift_within_limit(
            reid_worker["early"]["mean"],
            reid_worker["late"]["mean"],
            maximum_ratio=2.0,
            absolute_allowance=5.0,
        ),
        "reid_worker_drift",
        violations,
    )
    require(
        drift_within_limit(
            reid_e2e["early"]["mean"],
            reid_e2e["late"]["mean"],
            maximum_ratio=2.0,
            absolute_allowance=50.0,
        ),
        "reid_e2e_drift",
        violations,
    )

    resource_groups = resources.get("groups", {})

    for group_name in ("perception", "tim", "relay"):
        group = resource_groups.get(group_name)

        require(
            isinstance(group, dict),
            f"resource_group_{group_name}_missing",
            violations,
        )

        if not isinstance(group, dict):
            continue

        require(
            int(group.get("sample_count", 0))
            >= max(30, int(args.duration_s * 0.50)),
            f"resource_group_{group_name}_sample_count",
            violations,
        )

        cpu = resource_windows[group_name]["cpu_percent"]
        rss = resource_windows[group_name]["rss_kib"]

        require_window_counts(
            cpu,
            minimum=10,
            label=f"{group_name}_cpu",
            violations=violations,
        )
        require_window_counts(
            rss,
            minimum=10,
            label=f"{group_name}_rss",
            violations=violations,
        )

        require(
            drift_within_limit(
                cpu["early"]["mean"],
                cpu["late"]["mean"],
                maximum_ratio=1.75,
                absolute_allowance=25.0,
            ),
            f"{group_name}_cpu_drift",
            violations,
        )
        require(
            drift_within_limit(
                rss["early"]["mean"],
                rss["late"]["mean"],
                maximum_ratio=1.50,
                absolute_allowance=128.0 * 1024.0,
            ),
            f"{group_name}_rss_drift",
            violations,
        )

    output = {
        "schema": SCHEMA,
        "duration_s": args.duration_s,
        "analysis_start_monotonic_ns": start_ns,
        "passed": not violations,
        "violations": violations,
        "relay": relay,
        "collector": collector,
        "resources": resources,
        "health": health,
        "windows": {
            "detector": {
                "infer_ms": detector_infer,
                "e2e_det_ms": detector_e2e,
                "pub_dt_ms": detector_cadence,
            },
            "reid": {
                "worker_ms": reid_worker,
                "end_to_end_ms": reid_e2e,
            },
            "resources": resource_windows,
            "health": health_windows,
        },
        "acceptance_thresholds": {
            "maximum_temperature_c": args.maximum_temperature_c,
            "minimum_memory_available_mib": (
                args.minimum_memory_available_mib
            ),
            "detector_maximum_mean_ratio": 1.50,
            "reid_maximum_mean_ratio": 2.0,
            "resource_cpu_maximum_mean_ratio": 1.75,
            "resource_rss_maximum_mean_ratio": 1.50,
            "resource_rss_absolute_allowance_mib": 128.0,
        },
        "claim_boundary": {
            "bounded_replay_soak": True,
            "cross_sequence_generality_proven": False,
            "authoritative_repvgg_safety_proven": False,
            "cpu_mars_authoritative": True,
            "repvgg_observational": True,
            "repvgg_ranking_enabled": False,
            "repvgg_memory_enabled": False,
            "repvgg_decision_integration_enabled": False,
            "canonical_policy_changed": False,
            "production_nodes_modified": False,
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(output, indent=2, sort_keys=True))

    if violations:
        print(
            f"ERROR: sustained-soak validation found "
            f"{len(violations)} violation(s)."
        )
        return 1

    print("PASS: bounded sustained-operation invariants hold.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
