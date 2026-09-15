#!/usr/bin/env python3
"""Print and strictly gate finalized structured-plus-visual field evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _load(bag_dir: Path, name: str) -> dict[str, Any]:
    path = bag_dir / name
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{name} missing or unreadable: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{name} is not a JSON object")
    return value


def summarize(bag_dir: Path) -> tuple[bool, list[str]]:
    integrity = _load(bag_dir, "bag_integrity.json")
    transport = _load(bag_dir, "recorder_transport_status.json")
    visual = _load(bag_dir, "visual_evidence_status.json")
    package = _load(bag_dir, "evidence_package_status.json")

    duration_s = float(integrity.get("duration_ns") or 0) / 1e9
    lines = [
        f"bag: {bag_dir}",
        f"storage: {integrity.get('storage_identifier')}",
        f"duration_s: {duration_s:.6f}",
        f"bag_bytes: {integrity.get('total_bytes')}",
    ]
    counts = integrity.get("topic_message_counts")
    if not isinstance(counts, dict):
        counts = {}
    for topic, raw_count in sorted(counts.items()):
        count = int(raw_count)
        rate = count / duration_s if duration_s > 0 else 0.0
        lines.append(f"{topic}: count={count} retained_hz={rate:.3f}")

    recorders = transport.get("recorders")
    main = recorders.get("main", {}) if isinstance(recorders, dict) else {}
    lines.extend([
        "transport: "
        f"{transport.get('quality_status')} "
        f"count={main.get('reported_transport_loss_count')} "
        f"parse_ok={main.get('parse_ok')}",
        "visual: "
        f"passed={visual.get('passed')} "
        f"finalization={visual.get('finalization')} "
        f"codec={visual.get('codec')} "
        f"size={visual.get('width')}x{visual.get('height')} "
        f"fps={visual.get('measured_fps')} "
        f"frames={visual.get('decoded_frames')}",
        f"runtime_status: {package.get('runtime_status')}",
        f"pending: {package.get('pending')}",
        f"problems: {package.get('problems')}",
    ])

    image_topics = sorted(
        topic for topic in counts
        if topic in {"/camera/dashboard", "/camera/image_raw"}
    )
    ok = (
        integrity.get("passed") is True
        and duration_s > 0
        and not image_topics
        and transport.get("quality_status") == "observed_zero"
        and main.get("reported_transport_loss_count") == 0
        and main.get("parse_ok") is True
        and visual.get("passed") is True
        and visual.get("recorder_alive_at_stop") is True
        and visual.get("finalization") == "graceful"
        and package.get("runtime_status") == "complete_runtime_evidence"
        and not package.get("problems")
    )
    if image_topics:
        lines.append(f"unexpected_structured_image_topics: {image_topics}")
    lines.append(f"runtime_evidence_acceptable: {ok}")
    return ok, lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bag-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        ok, lines = summarize(args.bag_dir.resolve())
    except ValueError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
