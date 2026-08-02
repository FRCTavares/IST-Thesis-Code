#!/usr/bin/env python3
"""Sample CPU and memory for complete Linux process groups.

The sampler resolves every current member of each configured process group
from /proc. This includes both a ``ros2 run`` wrapper and the executable it
launches, avoiding wrapper-only resource measurements.

CPU percentages are process-group totals and may exceed 100% when work spans
multiple CPU cores. RSS is the sum of resident memory across current members.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import signal
import statistics
import threading
import time
from typing import Any, Iterable, Sequence


@dataclass(frozen=True)
class GroupSpec:
    """One named process group to sample."""

    name: str
    pgid: int


@dataclass(frozen=True)
class ProcessSnapshot:
    """One process contribution inside a process group."""

    pid: int
    ticks: int
    rss_kib: int
    command: str


def parse_group(raw_value: str) -> GroupSpec:
    """Parse ``NAME=PGID`` from the command line."""
    name, separator, pgid_raw = str(raw_value).partition("=")

    if not separator:
        raise ValueError(
            "process group must use NAME=PGID syntax"
        )

    resolved_name = name.strip()

    if not resolved_name:
        raise ValueError(
            "process-group name must not be empty"
        )

    try:
        pgid = int(pgid_raw)
    except ValueError as exc:
        raise ValueError(
            f"invalid process-group ID: {pgid_raw!r}"
        ) from exc

    if pgid <= 0:
        raise ValueError(
            "process-group ID must be positive"
        )

    return GroupSpec(
        name=resolved_name,
        pgid=pgid,
    )


def percentile(
    values: Sequence[float],
    quantile: float,
) -> float | None:
    """Return a linearly interpolated percentile."""
    data = sorted(
        float(value)
        for value in values
        if math.isfinite(float(value))
    )

    if not data:
        return None

    if len(data) == 1:
        return data[0]

    position = (
        max(0.0, min(1.0, float(quantile)))
        * float(len(data) - 1)
    )
    lower = int(math.floor(position))
    upper = int(math.ceil(position))

    if lower == upper:
        return data[lower]

    fraction = position - float(lower)

    return (
        data[lower] * (1.0 - fraction)
        + data[upper] * fraction
    )


def metric_summary(
    values: Iterable[float | int | None],
) -> dict[str, float | int | None]:
    """Summarise finite numeric values."""
    data = [
        float(value)
        for value in values
        if value is not None
        and math.isfinite(float(value))
    ]

    if not data:
        return {
            "count": 0,
            "mean": None,
            "p50": None,
            "p95": None,
            "maximum": None,
        }

    return {
        "count": len(data),
        "mean": statistics.fmean(data),
        "p50": percentile(data, 0.50),
        "p95": percentile(data, 0.95),
        "maximum": max(data),
    }


def _read_process_stat(
    pid: int,
) -> tuple[int, int]:
    stat_path = Path("/proc") / str(pid) / "stat"
    raw = stat_path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    closing = raw.rfind(")")

    if closing < 0:
        raise ValueError(
            f"malformed process stat for PID {pid}"
        )

    fields = raw[closing + 2 :].split()

    if len(fields) <= 21:
        raise ValueError(
            f"incomplete process stat for PID {pid}"
        )

    user_ticks = int(fields[11])
    system_ticks = int(fields[12])

    statm_path = Path("/proc") / str(pid) / "statm"
    statm_fields = statm_path.read_text(
        encoding="utf-8",
        errors="replace",
    ).split()

    if len(statm_fields) < 2:
        raise ValueError(
            f"incomplete process statm for PID {pid}"
        )

    resident_pages = int(statm_fields[1])
    page_size = int(os.sysconf("SC_PAGE_SIZE"))
    rss_kib = resident_pages * page_size // 1024

    return user_ticks + system_ticks, rss_kib


def _read_command(pid: int) -> str:
    cmdline_path = Path("/proc") / str(pid) / "cmdline"

    try:
        raw = cmdline_path.read_bytes()
    except OSError:
        return ""

    tokens = [
        token.decode(
            "utf-8",
            errors="replace",
        )
        for token in raw.split(b"\0")
        if token
    ]

    if tokens:
        return " ".join(tokens)

    comm_path = Path("/proc") / str(pid) / "comm"

    try:
        return comm_path.read_text(
            encoding="utf-8",
            errors="replace",
        ).strip()
    except OSError:
        return ""


def snapshot_group(
    pgid: int,
) -> tuple[ProcessSnapshot, ...]:
    """Read one complete process-group snapshot."""
    snapshots: list[ProcessSnapshot] = []

    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue

        pid = int(entry.name)

        try:
            current_pgid = int(os.getpgid(pid))
        except (OSError, ProcessLookupError):
            continue

        if current_pgid != int(pgid):
            continue

        try:
            ticks, rss_kib = _read_process_stat(pid)
        except (
            FileNotFoundError,
            OSError,
            ProcessLookupError,
            ValueError,
        ):
            continue

        snapshots.append(
            ProcessSnapshot(
                pid=pid,
                ticks=ticks,
                rss_kib=rss_kib,
                command=_read_command(pid),
            )
        )

    return tuple(
        sorted(
            snapshots,
            key=lambda item: item.pid,
        )
    )


def summarize_records(
    records: Sequence[dict[str, Any]],
    group_ids: dict[str, int],
) -> dict[str, Any]:
    """Build a machine-readable resource summary."""
    groups: dict[str, Any] = {}

    for name, pgid in sorted(group_ids.items()):
        group_records = [
            record
            for record in records
            if record.get("group") == name
        ]

        commands = sorted(
            {
                str(member.get("command", ""))
                for record in group_records
                for member in record.get("members", [])
                if str(member.get("command", ""))
            }
        )

        observed_pids = sorted(
            {
                int(member["pid"])
                for record in group_records
                for member in record.get("members", [])
            }
        )

        groups[name] = {
            "pgid": int(pgid),
            "sample_count": len(group_records),
            "cpu_percent": metric_summary(
                record.get("cpu_percent")
                for record in group_records
            ),
            "rss_kib": metric_summary(
                record.get("rss_kib")
                for record in group_records
            ),
            "member_count": metric_summary(
                record.get("member_count")
                for record in group_records
            ),
            "maximum_member_count": max(
                (
                    int(record.get("member_count", 0))
                    for record in group_records
                ),
                default=0,
            ),
            "observed_pids": observed_pids,
            "observed_commands": commands,
        }

    return {
        "schema": "p044_process_group_resources_v1",
        "groups": groups,
    }


def build_parser() -> argparse.ArgumentParser:
    """Create command-line parser."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--group",
        action="append",
        required=True,
        help="Named process group in NAME=PGID form.",
    )
    parser.add_argument(
        "--interval-s",
        type=float,
        default=1.0,
    )
    return parser


def main() -> int:
    """Run until interrupted and write JSONL plus a final summary."""
    args = build_parser().parse_args()

    try:
        groups = [
            parse_group(raw_value)
            for raw_value in args.group
        ]
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    names = [
        group.name
        for group in groups
    ]

    if len(set(names)) != len(names):
        raise SystemExit(
            "process-group names must be unique"
        )

    interval_s = float(args.interval_s)

    if not math.isfinite(interval_s) or interval_s <= 0.0:
        raise SystemExit(
            "interval must be finite and positive"
        )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    samples_path = output_dir / "samples.jsonl"
    summary_path = output_dir / "summary.json"

    clock_ticks = float(os.sysconf("SC_CLK_TCK"))
    stop_event = threading.Event()
    records: list[dict[str, Any]] = []
    previous: dict[
        str,
        tuple[int, int],
    ] = {}

    def request_stop(
        _signum: int,
        _frame: Any,
    ) -> None:
        stop_event.set()

    signal.signal(
        signal.SIGINT,
        request_stop,
    )
    signal.signal(
        signal.SIGTERM,
        request_stop,
    )
    signal.signal(
        signal.SIGHUP,
        request_stop,
    )

    started_ns = time.monotonic_ns()

    with samples_path.open(
        "w",
        encoding="utf-8",
    ) as output:
        while not stop_event.is_set():
            sample_started_ns = time.monotonic_ns()

            for group in groups:
                members = snapshot_group(group.pgid)
                total_ticks = sum(
                    member.ticks
                    for member in members
                )
                total_rss_kib = sum(
                    member.rss_kib
                    for member in members
                )

                cpu_percent: float | None = None
                previous_value = previous.get(
                    group.name
                )

                if previous_value is not None:
                    previous_ns, previous_ticks = (
                        previous_value
                    )
                    elapsed_s = float(
                        sample_started_ns - previous_ns
                    ) / 1e9
                    tick_delta = (
                        total_ticks - previous_ticks
                    )

                    if (
                        elapsed_s > 0.0
                        and tick_delta >= 0
                    ):
                        cpu_percent = (
                            100.0
                            * float(tick_delta)
                            / clock_ticks
                            / elapsed_s
                        )

                previous[group.name] = (
                    sample_started_ns,
                    total_ticks,
                )

                record = {
                    "schema": (
                        "p044_process_group_sample_v1"
                    ),
                    "sample_monotonic_ns": (
                        sample_started_ns
                    ),
                    "group": group.name,
                    "pgid": group.pgid,
                    "cpu_percent": cpu_percent,
                    "rss_kib": total_rss_kib,
                    "member_count": len(members),
                    "members": [
                        {
                            "pid": member.pid,
                            "ticks": member.ticks,
                            "rss_kib": (
                                member.rss_kib
                            ),
                            "command": (
                                member.command
                            ),
                        }
                        for member in members
                    ],
                }

                records.append(record)
                output.write(
                    json.dumps(
                        record,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n"
                )

            output.flush()

            elapsed = float(
                time.monotonic_ns()
                - sample_started_ns
            ) / 1e9
            remaining = max(
                0.0,
                interval_s - elapsed,
            )
            stop_event.wait(remaining)

    summary = summarize_records(
        records,
        {
            group.name: group.pgid
            for group in groups
        },
    )
    summary["started_monotonic_ns"] = (
        started_ns
    )
    summary["completed_monotonic_ns"] = (
        time.monotonic_ns()
    )
    summary["interval_s"] = interval_s

    summary_path.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
