#!/usr/bin/env python3
"""Validate canonical timing metric keys in generated JSON/Markdown reports.

This checker is intentionally lightweight: it verifies key presence only.
Use it to guard against report schema/name drift during timing pipeline changes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from timing_contract import TOPIC_CANONICAL_FIELDS


@dataclass
class ValidationResult:
    ok: bool
    errors: List[str]


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

    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        return ValidationResult(False, [f"{path}: missing object key 'metrics'"])

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

        for field in TOPIC_CANONICAL_FIELDS.get(topic, []):
            if field not in topic_metrics:
                errors.append(f"{path}: missing canonical key metrics['{topic}']['{field}']")

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
