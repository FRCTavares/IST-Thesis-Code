#!/usr/bin/env python3
"""Tiny freeze smoke check for thesis timing baseline.

This check asserts required canonical keys exist across the replay proof path:
- producer timing message capture
- bridge payload capture
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Set

REQUIRED_BRIDGE_KEYS = (
    "e2e_det_ms",
    "pub_dt_ms",
    "metrics_schema_version",
)

REQUIRED_PRODUCER_KEYS = (
    "infer_ms",
    "container_queue_ms",
)


def _read_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected JSON object")
    return payload


def _read_msg_keys(path: str) -> Set[str]:
    keys: Set[str] = set()
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or ":" not in line:
                continue
            key = line.split(":", 1)[0].strip()
            if key:
                keys.add(key)
    return keys


def _missing(keys: Set[str], required: tuple[str, ...]) -> List[str]:
    return [k for k in required if k not in keys]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Smoke check canonical timing freeze keys in proof artifacts")
    p.add_argument(
        "--bridge-json",
        default="artifacts/reports/timing/phase3_replay_bridge_payload.json",
        help="Bridge payload JSON artifact path",
    )
    p.add_argument(
        "--producer-msg",
        default="artifacts/reports/timing/phase3_replay_timing_msg.txt",
        help="Producer /timing message text artifact path",
    )
    p.add_argument(
        "--expected-schema-version",
        type=int,
        default=3,
        help="Expected frozen metrics schema version",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    failures: List[str] = []

    if not os.path.isfile(args.bridge_json):
        failures.append(f"missing bridge artifact: {args.bridge_json}")
    if not os.path.isfile(args.producer_msg):
        failures.append(f"missing producer artifact: {args.producer_msg}")

    if failures:
        print("Timing freeze smoke check: FAIL")
        for item in failures:
            print(f"- {item}")
        return 1

    bridge = _read_json(args.bridge_json)
    bridge_keys = set(bridge.keys())
    producer_keys = _read_msg_keys(args.producer_msg)

    missing_bridge = _missing(bridge_keys, REQUIRED_BRIDGE_KEYS)
    missing_producer = _missing(producer_keys, REQUIRED_PRODUCER_KEYS)

    if missing_bridge:
        failures.append(
            f"{args.bridge_json}: missing canonical keys: {', '.join(missing_bridge)}"
        )
    if missing_producer:
        failures.append(
            f"{args.producer_msg}: missing canonical keys: {', '.join(missing_producer)}"
        )

    schema_raw = bridge.get("metrics_schema_version")
    try:
        schema_version = int(schema_raw)
    except (TypeError, ValueError):
        schema_version = -1
    if schema_version != int(args.expected_schema_version):
        failures.append(
            f"{args.bridge_json}: metrics_schema_version={schema_raw!r} expected {args.expected_schema_version}"
        )

    if failures:
        print("Timing freeze smoke check: FAIL")
        for item in failures:
            print(f"- {item}")
        return 1

    print("Timing freeze smoke check: PASS")
    print(f"- bridge_json: {args.bridge_json}")
    print(f"- producer_msg: {args.producer_msg}")
    print(f"- verified_bridge_keys: {', '.join(REQUIRED_BRIDGE_KEYS)}")
    print(f"- verified_producer_keys: {', '.join(REQUIRED_PRODUCER_KEYS)}")
    print(f"- metrics_schema_version: {schema_version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
