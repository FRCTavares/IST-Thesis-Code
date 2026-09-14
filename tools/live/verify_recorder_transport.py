#!/usr/bin/env python3
"""Record exact rosbag transport-loss observations from archived recorder logs.

Structural MCAP integrity is independent of transport quality. A missing,
partial, or ambiguous log is unavailable, never an implicit zero.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPORT_NAME = "recorder_transport_status.json"
LOSS_PHRASE = "Number of messages lost on the transport layer:"
LOSS_LINE = re.compile(
    r"^\[WARN\] \[[0-9.]+\] \[rosbag2_recorder\]: "
    r"Number of messages lost on the transport layer: ([0-9]+)\s*$"
)


def observe(recorder: str, source_log: Path, scope: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "recorder": recorder,
        "scope": scope,
        "source_log": str(source_log),
        "log_present": source_log.is_file(),
        "parse_ok": False,
        "status": "unavailable",
        "reported_transport_loss_count": None,
    }
    if not result["log_present"]:
        result["reason"] = "archived recorder log missing"
        return result
    try:
        lines = source_log.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        result["reason"] = f"recorder log unreadable: {exc}"
        return result

    diagnostics = [line for line in lines if LOSS_PHRASE in line]
    stopped = any(
        "[rosbag2_recorder]: Recording stopped" in line for line in lines
    )
    result["recording_stopped_observed"] = stopped
    if not stopped:
        result["reason"] = "final Recording stopped marker absent"
    elif len(diagnostics) != 1:
        result["reason"] = (
            f"expected one explicit final transport-loss line, found {len(diagnostics)}"
        )
    else:
        match = LOSS_LINE.fullmatch(diagnostics[0])
        if match is None:
            result["reason"] = "transport-loss line malformed"
        else:
            count = int(match.group(1))
            result["parse_ok"] = True
            result["reported_transport_loss_count"] = count
            result["status"] = "observed_zero" if count == 0 else "observed_nonzero"
    return result


def verify_transport(
    bag_dir: Path, raw_bag_dir: Path | None = None
) -> dict[str, Any]:
    recorders = {
        "main": observe(
            "rosbag", bag_dir / "run_logs" / "rosbag.log",
            "multi_topic_aggregate",
        ),
    }
    if raw_bag_dir is not None:
        recorders["raw_image"] = observe(
            "raw_image_bag",
            raw_bag_dir / "run_logs" / "raw_image_bag.log",
            "single_topic_camera_image_raw",
        )
    states = {item["status"] for item in recorders.values()}
    if "observed_nonzero" in states:
        status = "observed_nonzero"
    elif "unavailable" in states:
        status = "unavailable"
    else:
        status = "observed_zero"
    return {
        "schema_version": 1,
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "bag_dir": str(bag_dir),
        "raw_bag_dir": str(raw_bag_dir) if raw_bag_dir else None,
        "recorders": recorders,
        "quality_status": status,
        "observation_complete": "unavailable" not in states,
        "runtime_evidence_acceptable": states == {"observed_zero"},
        "note": (
            "Main count is aggregate across recorded topics; it is not a "
            "per-topic loss count or rate. No acceptable-loss threshold is assumed."
        ),
    }


def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(payload, out, indent=2, sort_keys=True)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
    except BaseException:
        os.unlink(temp)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bag-dir", required=True, type=Path)
    parser.add_argument("--raw-bag-dir", type=Path)
    args = parser.parse_args(argv)
    report = verify_transport(
        args.bag_dir.resolve(),
        args.raw_bag_dir.resolve() if args.raw_bag_dir else None,
    )
    dest = args.bag_dir.resolve() / REPORT_NAME
    _write_atomic(dest, report)
    print(f"[evidence] recorder transport quality: {report['quality_status']} ({dest})")
    return 0 if report["runtime_evidence_acceptable"] else 1


if __name__ == "__main__":
    sys.exit(main())
