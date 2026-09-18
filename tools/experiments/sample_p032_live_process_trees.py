#!/usr/bin/env python3
"""Sample CPU/RSS for live-stack processes and their descendant trees.

Unlike the historical P044 process-group sampler, this collector does not
require the production live launcher to alter process-group/session ownership.
Each configured root is pinned by PID plus Linux process start-time identity;
the sampler then follows its current descendant tree from /proc.

Output is intentionally a new raw schema:
    p032_live_process_tree_sample_v1
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


SAMPLE_SCHEMA = "p032_live_process_tree_sample_v1"
SUMMARY_SCHEMA = "p032_live_process_tree_resources_v1"


@dataclass(frozen=True)
class RootSpec:
    name: str
    pid: int


@dataclass(frozen=True)
class Proc:
    pid: int
    ppid: int
    starttime_ticks: int
    ticks: int
    rss_kib: int
    command: str
    state: str = "R"


def parse_root(raw_value: str) -> RootSpec:
    name, separator, pid_raw = str(raw_value).partition("=")
    if not separator:
        raise ValueError("root process must use NAME=PID syntax")

    name = name.strip()
    if not name:
        raise ValueError("root-process name must not be empty")

    try:
        pid = int(pid_raw)
    except ValueError as exc:
        raise ValueError(f"invalid root PID: {pid_raw!r}") from exc

    if pid <= 0:
        raise ValueError("root PID must be positive")

    return RootSpec(name=name, pid=pid)


def percentile(values: Sequence[float], fraction: float) -> float | None:
    data = sorted(
        float(value)
        for value in values
        if math.isfinite(float(value))
    )
    if not data:
        return None
    if len(data) == 1:
        return data[0]

    position = max(0.0, min(1.0, fraction)) * (len(data) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return data[lower]

    weight = position - lower
    return data[lower] * (1.0 - weight) + data[upper] * weight


def metric_summary(
    values: Iterable[float | int | None],
) -> dict[str, float | int | None]:
    finite = [
        float(value)
        for value in values
        if value is not None and math.isfinite(float(value))
    ]
    if not finite:
        return {
            "count": 0,
            "mean": None,
            "p50": None,
            "p95": None,
            "maximum": None,
        }
    return {
        "count": len(finite),
        "mean": statistics.fmean(finite),
        "p50": percentile(finite, 0.50),
        "p95": percentile(finite, 0.95),
        "maximum": max(finite),
    }


def _read_command(pid: int) -> str:
    try:
        raw = (Path("/proc") / str(pid) / "cmdline").read_bytes()
    except OSError:
        return ""

    tokens = [
        token.decode("utf-8", errors="replace")
        for token in raw.split(b"\0")
        if token
    ]
    if tokens:
        return " ".join(tokens)

    try:
        return (
            Path("/proc") / str(pid) / "comm"
        ).read_text(
            encoding="utf-8",
            errors="replace",
        ).strip()
    except OSError:
        return ""


def _read_proc(pid: int) -> Proc:
    proc_dir = Path("/proc") / str(pid)
    raw = (proc_dir / "stat").read_text(
        encoding="utf-8",
        errors="replace",
    )
    closing = raw.rfind(")")
    if closing < 0:
        raise ValueError(f"malformed process stat for PID {pid}")

    fields = raw[closing + 2 :].split()
    if len(fields) <= 19:
        raise ValueError(f"incomplete process stat for PID {pid}")

    ppid = int(fields[1])
    user_ticks = int(fields[11])
    system_ticks = int(fields[12])
    starttime_ticks = int(fields[19])

    statm = (proc_dir / "statm").read_text(
        encoding="utf-8",
        errors="replace",
    ).split()
    if len(statm) < 2:
        raise ValueError(f"incomplete process statm for PID {pid}")

    resident_pages = int(statm[1])
    page_size = int(os.sysconf("SC_PAGE_SIZE"))

    return Proc(
        pid=pid,
        ppid=ppid,
        starttime_ticks=starttime_ticks,
        ticks=user_ticks + system_ticks,
        rss_kib=resident_pages * page_size // 1024,
        command=_read_command(pid),
        state=fields[0],
    )


def snapshot_all() -> dict[int, Proc]:
    result: dict[int, Proc] = {}
    try:
        entries = tuple(Path("/proc").iterdir())
    except OSError:
        return result

    for entry in entries:
        if not entry.name.isdigit():
            continue

        pid = int(entry.name)
        try:
            result[pid] = _read_proc(pid)
        except (
            FileNotFoundError,
            OSError,
            ProcessLookupError,
            ValueError,
        ):
            continue

    return result


def tree_members(
    processes: dict[int, Proc],
    root_pid: int,
    root_starttime_ticks: int,
) -> tuple[Proc, ...]:
    root = processes.get(root_pid)
    if (root is None or root.starttime_ticks != root_starttime_ticks
            or root.state in ("Z", "X", "x")):
        return ()

    children: dict[int, list[int]] = {}
    for proc in processes.values():
        children.setdefault(proc.ppid, []).append(proc.pid)

    pending = [root_pid]
    seen: set[int] = set()
    members: list[Proc] = []

    while pending:
        pid = pending.pop()
        if pid in seen:
            continue
        seen.add(pid)

        proc = processes.get(pid)
        if proc is None:
            continue

        members.append(proc)
        pending.extend(
            child_pid
            for child_pid in children.get(pid, ())
            if processes[child_pid].starttime_ticks >= proc.starttime_ticks
        )

    return tuple(sorted(members, key=lambda item: item.pid))


def require_disjoint_trees(members_by_group: dict[str, tuple[Proc, ...]]) -> None:
    owners: dict[tuple[int, int], str] = {}
    for group, members in members_by_group.items():
        for member in members:
            identity = (member.pid, member.starttime_ticks)
            previous = owners.setdefault(identity, group)
            if previous != group:
                raise ValueError(
                    f"live process {identity} belongs to both {previous} and {group}"
                )


def summarize_records(
    records: Sequence[dict[str, Any]],
    roots: dict[str, tuple[int, int]],
) -> dict[str, Any]:
    groups: dict[str, Any] = {}

    for name, (root_pid, root_starttime) in sorted(roots.items()):
        subset = [
            record
            for record in records
            if record.get("group") == name
        ]

        groups[name] = {
            "root_pid": root_pid,
            "root_starttime_ticks": root_starttime,
            "sample_count": len(subset),
            "cpu_percent": metric_summary(
                record.get("cpu_percent")
                for record in subset
            ),
            "rss_kib": metric_summary(
                record.get("rss_kib")
                for record in subset
            ),
            "member_count": metric_summary(
                record.get("member_count")
                for record in subset
            ),
            "root_missing_count": sum(
                not bool(record.get("root_identity_alive"))
                for record in subset
            ),
        }

    return {
        "schema": SUMMARY_SCHEMA,
        "groups": groups,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--root",
        action="append",
        required=True,
        help="Named live-stack root process in NAME=PID form.",
    )
    parser.add_argument(
        "--interval-s",
        type=float,
        default=1.0,
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    try:
        specs = [parse_root(value) for value in args.root]
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    names = [spec.name for spec in specs]
    if len(set(names)) != len(names):
        raise SystemExit("root-process names must be unique")

    interval_s = float(args.interval_s)
    if not math.isfinite(interval_s) or interval_s <= 0.0:
        raise SystemExit("interval must be finite and positive")

    initial = snapshot_all()
    roots: dict[str, tuple[int, int]] = {}
    for spec in specs:
        proc = initial.get(spec.pid)
        if proc is None or proc.state in ("Z", "X", "x"):
            raise SystemExit(
                f"root process {spec.name!r} PID {spec.pid} is not alive"
            )
        roots[spec.name] = (spec.pid, proc.starttime_ticks)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    samples_path = output_dir / "samples.jsonl"
    summary_path = output_dir / "summary.json"

    clock_ticks = float(os.sysconf("SC_CLK_TCK"))
    stop_event = threading.Event()
    # Keep only scalar values for the final summary; full member details live
    # in the JSONL stream and need not grow in memory throughout a long run.
    summary_records: list[dict[str, Any]] = []
    previous: dict[str, tuple[int, dict[tuple[int, int], int]]] = {}

    def request_stop(_signum: int, _frame: Any) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGHUP, request_stop)

    with samples_path.open("w", encoding="utf-8") as stream:
        while not stop_event.is_set():
            sample_started_ns = time.monotonic_ns()
            processes = snapshot_all()
            members_by_group = {
                name: tree_members(processes, root_pid, root_starttime)
                for name, (root_pid, root_starttime) in roots.items()
            }
            require_disjoint_trees(members_by_group)

            for name, (root_pid, root_starttime) in roots.items():
                members = members_by_group[name]
                current_ticks = {
                    (member.pid, member.starttime_ticks): member.ticks
                    for member in members
                }

                cpu_percent: float | None = None
                previous_value = previous.get(name)
                if previous_value is not None:
                    previous_ns, previous_ticks = previous_value
                    elapsed_s = (
                        sample_started_ns - previous_ns
                    ) / 1e9

                    tick_delta = sum(
                        ticks - previous_ticks[identity]
                        for identity, ticks in current_ticks.items()
                        if identity in previous_ticks
                        and ticks >= previous_ticks[identity]
                    )

                    if elapsed_s > 0.0:
                        cpu_percent = (
                            100.0
                            * float(tick_delta)
                            / clock_ticks
                            / elapsed_s
                        )

                if members:
                    previous[name] = (sample_started_ns, current_ticks)
                else:
                    previous.pop(name, None)
                    cpu_percent = None

                record = {
                    "schema": SAMPLE_SCHEMA,
                    "sample_monotonic_ns": sample_started_ns,
                    "group": name,
                    "root_pid": root_pid,
                    "root_starttime_ticks": root_starttime,
                    "root_identity_alive": bool(members),
                    "cpu_percent": cpu_percent,
                    "rss_kib": (
                        sum(member.rss_kib for member in members)
                        if members else None
                    ),
                    "member_count": len(members),
                    "members": [
                        {
                            "pid": member.pid,
                            "ppid": member.ppid,
                            "starttime_ticks": member.starttime_ticks,
                            "ticks": member.ticks,
                            "rss_kib": member.rss_kib,
                            "command": member.command,
                        }
                        for member in members
                    ],
                }

                summary_records.append({
                    key: record[key]
                    for key in (
                        "group", "cpu_percent", "rss_kib",
                        "member_count", "root_identity_alive",
                    )
                })
                stream.write(
                    json.dumps(
                        record,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    + "\n"
                )

            stream.flush()

            elapsed_s = (
                time.monotonic_ns() - sample_started_ns
            ) / 1e9
            stop_event.wait(max(0.0, interval_s - elapsed_s))

    summary_path.write_text(
        json.dumps(
            summarize_records(summary_records, roots),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
