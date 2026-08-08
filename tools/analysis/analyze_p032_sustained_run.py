#!/usr/bin/env python3
"""Validate bounded Issue #32 sustained live/onboard run evidence.

Reuses tools/experiments/analyze_p044_sustained_soak.py's generic
percentile, windowing, and drift-check primitives rather than
re-implementing them. The acceptance gates here are Issue #32's own
(cadence consistency, thermal ceiling, memory floor, zero throttling,
resource drift bounds) -- not Issue #44's ReID-transport-specific gates.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_EXPERIMENTS_DIR = str(REPO_ROOT / "tools" / "experiments")
if _EXPERIMENTS_DIR not in sys.path:
    sys.path.insert(0, _EXPERIMENTS_DIR)

from analyze_p044_sustained_soak import (  # noqa: E402
    drift_within_limit,
    duration_within_tolerance,
    read_json,
    read_jsonl,
    require,
    require_window_counts,
    windowed_metric,
)

SCHEMA = "p032_sustained_run_analysis_v1"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timing-summary", required=True, type=Path)
    parser.add_argument("--relay-summary", required=True, type=Path)
    parser.add_argument("--resources-summary", required=True, type=Path)
    parser.add_argument("--resources-samples", required=True, type=Path)
    parser.add_argument("--health-summary", required=True, type=Path)
    parser.add_argument("--health-samples", required=True, type=Path)
    parser.add_argument("--duration-s", required=True, type=float)
    parser.add_argument("--warm-up-s", required=True, type=float)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--maximum-temperature-c", type=float, default=80.0
    )
    parser.add_argument(
        "--minimum-memory-available-mib", type=float, default=512.0
    )
    args = parser.parse_args()

    timing = read_json(args.timing_summary)
    relay = read_json(args.relay_summary)
    resources = read_json(args.resources_summary)
    health = read_json(args.health_summary)

    resource_samples = read_jsonl(args.resources_samples)
    health_samples = read_jsonl(args.health_samples)

    if not health_samples:
        raise SystemExit(
            "ERROR: no hardware-health samples were recorded."
        )

    if not resource_samples:
        raise SystemExit(
            "ERROR: no process-group resource samples were recorded."
        )

    sample_times = [
        int(sample["monotonic_ns"]) for sample in health_samples
    ] + [
        int(sample["sample_monotonic_ns"])
        for sample in resource_samples
    ]
    start_ns = min(sample_times)
    end_ns = max(sample_times)
    observed_duration_s = max(0.0, (end_ns - start_ns) / 1e9)
    duration_ns = max(1, end_ns - start_ns)

    violations: list[str] = []

    require(
        duration_within_tolerance(
            observed_duration_s,
            args.duration_s,
            early_allowance_s=15.0,
            late_allowance_s=30.0,
        ),
        "observed_duration_outside_requested_bound",
        violations,
    )

    # Timing / cadence. collect_live_timing_stats.py is started only after
    # the warm-up window, so its statistics already exclude warm-up; it
    # does not emit per-sample timestamps for further post-hoc windowing.
    require(
        float(timing.get("duration_s", 0.0)) > 0.0,
        "timing_zero_duration",
        violations,
    )

    for topic in ("/timing", "/timing_tracker", "/timing_target"):
        topic_stats = timing.get("topics", {}).get(topic, {})
        require(
            int(topic_stats.get("count", 0)) > 0,
            f"timing_no_samples_{topic}",
            violations,
        )

    cadence = timing.get("cadence_consistency", {})
    require(
        bool(cadence.get("within_tolerance")),
        "cadence_inconsistent_with_detection_rate",
        violations,
    )

    # Relay accounting confirms the source was consumed cleanly and
    # looped at least once -- direct evidence the run was genuinely
    # sustained rather than a single short pass.
    relay_counters = relay.get("counters", {})
    require(
        relay.get("schema") == "p044_soak_input_relay_summary_v1",
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

    # Resource windows (perception, TIM, relay process groups). Sampling
    # spans the full run including warm-up, so early/late drift reflects
    # genuine settling behaviour, not an artefact of a shifted window.
    resource_groups = resources.get("groups", {})
    resource_windows: dict[str, Any] = {}

    for group_name in ("perception", "tracker", "tim", "relay"):
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
            >= max(30, int(args.duration_s * 0.5)),
            f"resource_group_{group_name}_sample_count",
            violations,
        )

        predicate = lambda row, expected=group_name: (
            row.get("group") == expected
        )

        cpu = windowed_metric(
            resource_samples,
            timestamp_key="sample_monotonic_ns",
            value_key="cpu_percent",
            start_ns=start_ns,
            duration_ns=duration_ns,
            predicate=predicate,
        )
        rss = windowed_metric(
            resource_samples,
            timestamp_key="sample_monotonic_ns",
            value_key="rss_kib",
            start_ns=start_ns,
            duration_ns=duration_ns,
            predicate=predicate,
        )
        resource_windows[group_name] = {
            "cpu_percent": cpu,
            "rss_kib": rss,
        }

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

    # Hardware health: thermal ceiling, memory floor, zero throttling,
    # thermal drift.
    require(
        health.get("schema") == "p044_hardware_health_summary_v1",
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

    temperature_maximum = health.get("temperature_c", {}).get(
        "maximum"
    )
    require(
        temperature_maximum is not None
        and float(temperature_maximum) <= args.maximum_temperature_c,
        "temperature_limit",
        violations,
    )

    minimum_memory_kib = health.get("mem_available_kib", {}).get(
        "minimum"
    )
    require(
        minimum_memory_kib is not None
        and float(minimum_memory_kib)
        >= args.minimum_memory_available_mib * 1024.0,
        "minimum_available_memory",
        violations,
    )

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

    require_window_counts(
        health_windows["temperature_c"],
        minimum=3,
        label="temperature",
        violations=violations,
    )

    require(
        drift_within_limit(
            health_windows["temperature_c"]["early"]["mean"],
            health_windows["temperature_c"]["late"]["mean"],
            maximum_ratio=1.35,
            absolute_allowance=10.0,
        ),
        "temperature_drift",
        violations,
    )

    output = {
        "schema": SCHEMA,
        "requested_duration_s": args.duration_s,
        "warm_up_s": args.warm_up_s,
        "observed_duration_s": observed_duration_s,
        "analysis_start_monotonic_ns": start_ns,
        "analysis_end_monotonic_ns": end_ns,
        "passed": not violations,
        "violations": violations,
        "timing": timing,
        "relay": relay,
        "resources": resources,
        "health": health,
        "windows": {
            "resources": resource_windows,
            "health": health_windows,
        },
        "acceptance_thresholds": {
            "maximum_temperature_c": args.maximum_temperature_c,
            "minimum_memory_available_mib": (
                args.minimum_memory_available_mib
            ),
            "resource_cpu_maximum_mean_ratio": 1.75,
            "resource_rss_maximum_mean_ratio": 1.50,
            "temperature_maximum_mean_ratio": 1.35,
        },
        "claim_boundary": {
            "measurement_mode": "live_sustained",
            "source_category": (
                "replayed_bag_via_timestamp_refresh_relay"
            ),
            "physically_live_camera": False,
            "warm_up_excluded_from_latency_percentiles": True,
            "warm_up_included_in_resource_and_thermal_windows": True,
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
            f"ERROR: sustained-run validation found "
            f"{len(violations)} violation(s)."
        )
        return 1

    print("PASS: bounded sustained-run invariants hold.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
