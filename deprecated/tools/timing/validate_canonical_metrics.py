#!/usr/bin/env python3
"""Validate canonical timing metric contracts in generated JSON/Markdown reports.

Phase-2 checks are strict and fail on:
- missing canonical keys
- missing contract metadata (schema/window/thresholds)
- negative timing stats
- impossible aggregate relationships (e2e_det_ms < infer_ms)
- cadence mismatch between detection output FPS and pub_dt_ms-derived FPS
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.timing_contract import (
    FPS_INTERVAL_RELATIVE_DELTA_MAX,
    METRICS_SCHEMA_VERSION,
    METRIC_WARN_THRESHOLDS,
    METRIC_WINDOWS,
    TOPIC_CANONICAL_FIELDS,
)


@dataclass
class ValidationResult:
    ok: bool
    errors: List[str]


_STAT_KEYS = ("n", "p50", "p95", "p99", "mean", "min", "max")


def _as_float(value, label: str, errors: List[str], path: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        errors.append(f"{path}: {label} is not numeric: {value!r}")
        return float("nan")


def _validate_contract_metadata(payload: Dict[str, object], path: str, errors: List[str]) -> None:
    contract = payload.get("contract")
    if not isinstance(contract, dict):
        errors.append(f"{path}: missing object key 'contract'")
        return

    schema_raw = contract.get("metrics_schema_version")
    try:
        schema_version = int(schema_raw)
    except (TypeError, ValueError):
        errors.append(f"{path}: contract.metrics_schema_version must be an integer")
        schema_version = -1

    if schema_version < METRICS_SCHEMA_VERSION:
        errors.append(
            f"{path}: contract.metrics_schema_version={schema_version} "
            f"is older than required {METRICS_SCHEMA_VERSION}"
        )

    windows = contract.get("metric_windows")
    if not isinstance(windows, dict):
        errors.append(f"{path}: missing object key contract.metric_windows")
    else:
        for key, expected in METRIC_WINDOWS.items():
            if key not in windows:
                errors.append(f"{path}: missing contract.metric_windows['{key}']")
                continue
            value = _as_float(windows.get(key), f"contract.metric_windows['{key}']", errors, path)
            if not math.isfinite(value) or value <= 0.0:
                errors.append(f"{path}: contract.metric_windows['{key}'] must be finite and > 0")
            if abs(value - expected) > 1e-6:
                errors.append(
                    f"{path}: contract.metric_windows['{key}']={value} "
                    f"does not match canonical {expected}"
                )

    thresholds = contract.get("metric_thresholds_ms")
    if not isinstance(thresholds, dict):
        errors.append(f"{path}: missing object key contract.metric_thresholds_ms")
    else:
        for key, expected in METRIC_WARN_THRESHOLDS.items():
            if key not in thresholds:
                errors.append(f"{path}: missing contract.metric_thresholds_ms['{key}']")
                continue
            value = _as_float(thresholds.get(key), f"contract.metric_thresholds_ms['{key}']", errors, path)
            if not math.isfinite(value) or value <= 0.0:
                errors.append(f"{path}: contract.metric_thresholds_ms['{key}'] must be finite and > 0")
            if abs(value - expected) > 1e-6:
                errors.append(
                    f"{path}: contract.metric_thresholds_ms['{key}']={value} "
                    f"does not match canonical {expected}"
                )


def _validate_topic_metric_stats(
    path: str,
    topic: str,
    topic_metrics: Dict[str, object],
    topic_count: int,
    errors: List[str],
) -> None:
    for field in TOPIC_CANONICAL_FIELDS.get(topic, []):
        if field not in topic_metrics:
            errors.append(f"{path}: missing canonical key metrics['{topic}']['{field}']")
            continue

        stats = topic_metrics.get(field)
        if not isinstance(stats, dict):
            errors.append(f"{path}: metrics['{topic}']['{field}'] must be an object")
            continue

        missing_keys = [k for k in _STAT_KEYS if k not in stats]
        if missing_keys:
            errors.append(
                f"{path}: metrics['{topic}']['{field}'] missing stat keys: {', '.join(missing_keys)}"
            )
            continue

        n = _as_float(stats.get("n"), f"metrics['{topic}']['{field}']['n']", errors, path)
        vmin = _as_float(stats.get("min"), f"metrics['{topic}']['{field}']['min']", errors, path)

        if math.isfinite(n) and n < 0:
            errors.append(f"{path}: metrics['{topic}']['{field}']['n'] must be >= 0")
        if topic_count > 0 and math.isfinite(n) and n <= 0:
            errors.append(
                f"{path}: metrics['{topic}']['{field}'] has no finite samples despite topics['{topic}']['count']={topic_count}"
            )

        if math.isfinite(vmin) and vmin < 0.0:
            errors.append(f"{path}: metrics['{topic}']['{field}']['min'] is negative ({vmin})")


def _validate_cross_metric_consistency(payload: Dict[str, object], path: str, errors: List[str]) -> None:
    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        return

    timing_metrics = metrics.get("/timing")
    if not isinstance(timing_metrics, dict):
        return

    e2e_stats = timing_metrics.get("e2e_det_ms")
    infer_stats = timing_metrics.get("infer_ms")
    if isinstance(e2e_stats, dict) and isinstance(infer_stats, dict):
        e2e_p50 = _as_float(e2e_stats.get("p50"), "metrics['/timing']['e2e_det_ms']['p50']", errors, path)
        infer_p50 = _as_float(infer_stats.get("p50"), "metrics['/timing']['infer_ms']['p50']", errors, path)
        if math.isfinite(e2e_p50) and math.isfinite(infer_p50) and e2e_p50 + 1e-6 < infer_p50:
            errors.append(
                f"{path}: impossible aggregate ordering: e2e_det_ms p50 ({e2e_p50:.3f}) < infer_ms p50 ({infer_p50:.3f})"
            )

    cadence = payload.get("cadence_consistency")
    if isinstance(cadence, dict):
        within = cadence.get("within_tolerance")
        rel_delta = _as_float(cadence.get("relative_delta"), "cadence_consistency.relative_delta", errors, path)
        if within is False:
            errors.append(
                f"{path}: det_out_fps inconsistent with canonical pub_dt_ms; "
                f"det_interval_ms is deprecated compatibility alias only: "
                f"relative_delta={rel_delta:.3f} > max {FPS_INTERVAL_RELATIVE_DELTA_MAX:.3f}"
            )
        return

    # Fallback for older report schema without cadence_consistency block.
    dstream = payload.get("detection_stream")
    if not isinstance(dstream, dict):
        errors.append(f"{path}: missing object key 'cadence_consistency' or 'detection_stream'")
        return

    det_hz = _as_float(dstream.get("hz"), "detection_stream.hz", errors, path)
    pub_dt_stats = timing_metrics.get("pub_dt_ms")
    if not isinstance(pub_dt_stats, dict):
        errors.append(f"{path}: missing metrics['/timing']['pub_dt_ms'] for cadence consistency check")
        return
    pub_dt_p50 = _as_float(pub_dt_stats.get("p50"), "metrics['/timing']['pub_dt_ms']['p50']", errors, path)
    if math.isfinite(det_hz) and det_hz > 0.0 and math.isfinite(pub_dt_p50) and pub_dt_p50 > 0.0:
        fps_from_pub_dt = 1000.0 / pub_dt_p50
        rel_delta = abs(det_hz - fps_from_pub_dt) / max(fps_from_pub_dt, 1e-9)
        if rel_delta > FPS_INTERVAL_RELATIVE_DELTA_MAX:
            errors.append(
                f"{path}: det_out_fps inconsistent with canonical pub_dt_ms; "
                f"det_interval_ms is deprecated compatibility alias only: "
                f"relative_delta={rel_delta:.3f} > max {FPS_INTERVAL_RELATIVE_DELTA_MAX:.3f}"
            )


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _validate_json(path: str, require_tracker: bool, require_target: bool) -> ValidationResult:
    errors: List[str] = []

    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as exc:
        return ValidationResult(False, [f"{path}: failed to parse JSON: {exc}"])

    if not isinstance(payload, dict):
        return ValidationResult(False, [f"{path}: root JSON value must be an object"])

    _validate_contract_metadata(payload, path, errors)

    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        return ValidationResult(False, [f"{path}: missing object key 'metrics'"])

    topics = payload.get("topics")
    topics_payload = topics if isinstance(topics, dict) else {}

    topics_to_check: List[str] = ["/timing"]
    if require_tracker:
        topics_to_check.append("/timing_tracker")
    if require_target:
        topics_to_check.append("/timing_target")

    # If not required, still validate optional topic keys when present.
    for maybe_topic in ["/timing_tracker", "/timing_target"]:
        if maybe_topic in metrics and maybe_topic not in topics_to_check:
            topics_to_check.append(maybe_topic)

    for topic in topics_to_check:
        topic_metrics = metrics.get(topic)
        if not isinstance(topic_metrics, dict):
            errors.append(f"{path}: missing metrics topic '{topic}'")
            continue

        topic_count = 0
        topic_summary = topics_payload.get(topic)
        if isinstance(topic_summary, dict):
            try:
                topic_count = int(topic_summary.get("count", 0))
            except (TypeError, ValueError):
                errors.append(f"{path}: topics['{topic}']['count'] must be an integer")

        _validate_topic_metric_stats(
            path=path,
            topic=topic,
            topic_metrics=topic_metrics,
            topic_count=topic_count,
            errors=errors,
        )

    _validate_cross_metric_consistency(payload, path, errors)

    return ValidationResult(len(errors) == 0, errors)


def _validate_markdown(path: str, require_tracker: bool, require_target: bool) -> ValidationResult:
    errors: List[str] = []
    try:
        text = _read_text(path)
    except Exception as exc:
        return ValidationResult(False, [f"{path}: failed to read markdown: {exc}"])

    # Base /timing section and canonical field rows.
    required_snippets = [
        "## Per-field stats (/timing)",
        "| pre_ms |",
        "| container_queue_ms |",
        "| zmq_roundtrip_ms |",
        "| infer_ms |",
        "| e2e_det_ms |",
        "| pub_dt_ms |",
    ]

    if require_tracker:
        required_snippets.extend([
            "## Tracker runtime",
            "track_ms",
        ])

    if require_target:
        required_snippets.extend([
            "## Target end-to-end runtime",
            "e2e_target_ms",
        ])

    for snippet in required_snippets:
        if snippet not in text:
            errors.append(f"{path}: missing markdown snippet: {snippet}")

    return ValidationResult(len(errors) == 0, errors)


def _existing_files(paths: Sequence[str]) -> Tuple[List[str], List[str]]:
    existing: List[str] = []
    missing: List[str] = []
    for p in paths:
        if os.path.isfile(p):
            existing.append(p)
        else:
            missing.append(p)
    return existing, missing


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate canonical timing metric keys in report outputs")
    p.add_argument("--json", dest="json_paths", action="append", default=[], help="Path to JSON report")
    p.add_argument("--markdown", dest="md_paths", action="append", default=[], help="Path to markdown report")
    p.add_argument("--require-tracker", action="store_true", help="Require tracker timing keys/sections")
    p.add_argument("--require-target", action="store_true", help="Require target timing keys/sections")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    if not args.json_paths and not args.md_paths:
        print("ERROR: provide at least one --json or --markdown input", file=sys.stderr)
        return 2

    failures: List[str] = []

    json_existing, json_missing = _existing_files(args.json_paths)
    md_existing, md_missing = _existing_files(args.md_paths)

    for p in json_missing:
        failures.append(f"missing file: {p}")
    for p in md_missing:
        failures.append(f"missing file: {p}")

    for path in json_existing:
        res = _validate_json(path, require_tracker=args.require_tracker, require_target=args.require_target)
        if not res.ok:
            failures.extend(res.errors)

    for path in md_existing:
        res = _validate_markdown(path, require_tracker=args.require_tracker, require_target=args.require_target)
        if not res.ok:
            failures.extend(res.errors)

    if failures:
        print("Canonical metrics validation: FAIL")
        for item in failures:
            print(f"- {item}")
        return 1

    print("Canonical metrics validation: PASS")
    checked = []
    checked.extend(json_existing)
    checked.extend(md_existing)
    for p in checked:
        print(f"- {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
