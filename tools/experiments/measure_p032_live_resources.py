#!/usr/bin/env python3
"""Attach bounded resource measurement to an existing production live run."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROCESS_TO_GROUP = {
    "perception_camera": "detector",
    "tracker": "tracker",
    "target_memory_mars": "tim",
    "control": "controller",
}
GROUP_TO_PROCESS = {group: process for process, group in PROCESS_TO_GROUP.items()}


def process_starttime(pid: int) -> int:
    raw = (Path("/proc") / str(pid) / "stat").read_text(encoding="utf-8")
    fields = raw[raw.rfind(")") + 2 :].split()
    if fields[0] in ("Z", "X", "x"):
        raise ValueError(f"PID {pid} is no longer running")
    return int(fields[19])


def resolve_roots(pid_file: Path, groups: tuple[str, ...]) -> dict[str, tuple[int, int]]:
    if not groups or len(set(groups)) != len(groups):
        raise ValueError("architecture groups must be nonempty and unique")
    unknown = set(groups) - set(GROUP_TO_PROCESS)
    if unknown:
        raise ValueError(f"unknown architecture groups: {sorted(unknown)}")
    entries: dict[str, int] = {}
    for line in pid_file.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 2 or not parts[0].isdigit():
            raise ValueError(f"invalid PID entry: {line!r}")
        pid, name = int(parts[0]), parts[1]
        if name in entries:
            raise ValueError(f"duplicate live process name: {name}")
        entries[name] = pid
    roots: dict[str, tuple[int, int]] = {}
    for group in groups:
        process = GROUP_TO_PROCESS[group]
        if process not in entries:
            raise ValueError(f"required live process absent: {process}")
        pid = entries[process]
        try:
            roots[group] = (pid, process_starttime(pid))
        except (OSError, ValueError, IndexError) as exc:
            raise ValueError(f"required live process exited: {process} PID {pid}") from exc
    if len({pid for pid, _ in roots.values()}) != len(roots):
        raise ValueError("architecture roots must have distinct PIDs")
    return roots


def check_result(
    resource_summary: dict[str, Any],
    analysis: dict[str, Any],
    roots: dict[str, tuple[int, int]],
) -> None:
    for group, (pid, starttime) in roots.items():
        data = resource_summary["groups"].get(group)
        if data is None or (data["root_pid"], data["root_starttime_ticks"]) != (pid, starttime):
            raise ValueError(f"live root identity changed for {group}")
        if data["root_missing_count"] or data["sample_count"] < 2:
            raise ValueError(f"live root missing or too few samples for {group}")
    integrity = analysis["integrity"]
    required = (
        "resource_records_have_known_sample_schema",
        "hardware_records_have_known_sample_schema",
        "architecture_has_complete_samples",
        "live_resource_roots_present_throughout_window",
        "steady_state_resource_samples_present",
        "steady_state_hardware_samples_present",
    )
    failed = [name for name in required if not integrity[name]]
    if analysis["architecture_total"]["missing_requested_groups"]:
        failed.append("missing_requested_groups")
    if failed:
        raise ValueError(f"resource integrity checks failed: {failed}")


def sample_coverage(
    path: Path,
    timestamp_key: str,
    groups: tuple[str, ...],
    start_ns: int,
    end_ns: int,
    interval_s: float,
) -> dict[str, Any]:
    timestamps: dict[str, list[int]] = {group: [] for group in groups}
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        group = str(record.get("group", "hardware"))
        stamp = int(record[timestamp_key])
        if group in timestamps and start_ns <= stamp <= end_ns:
            timestamps[group].append(stamp)
    limit_ns = int(interval_s * 1e9)
    result: dict[str, Any] = {}
    for group, times in timestamps.items():
        times.sort()
        if len(times) < 2:
            raise ValueError(f"too few bounded samples for {group}")
        first_gap_ns = times[0] - start_ns
        last_gap_ns = end_ns - times[-1]
        maximum_gap_ns = max(b - a for a, b in zip(times, times[1:]))
        result[group] = {
            "sample_count": len(times),
            "first_gap_s": first_gap_ns / 1e9,
            "last_gap_s": last_gap_ns / 1e9,
            "maximum_gap_s": maximum_gap_ns / 1e9,
        }
        if (first_gap_ns > 2 * limit_ns or last_gap_ns > 2 * limit_ns
                or maximum_gap_ns > 3 * limit_ns):
            raise ValueError(f"sampler coverage gap for {group}: {result[group]}")
    return result


def git_value(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True,
    ).strip()


def measure(args: argparse.Namespace) -> int:
    if not math.isfinite(args.duration_s) or args.duration_s <= args.warm_up_s:
        raise ValueError("duration must exceed non-negative warm-up")
    if args.warm_up_s < 0 or not math.isfinite(args.warm_up_s):
        raise ValueError("warm-up must be finite and non-negative")
    if not math.isfinite(args.interval_s) or args.interval_s <= 0:
        raise ValueError("interval must be finite and positive")
    if not math.isfinite(args.hardware_interval_s) or args.hardware_interval_s <= 0:
        raise ValueError("hardware interval must be finite and positive")

    run_dir = args.run_dir.resolve(strict=True)
    groups = tuple(group.strip() for group in args.architecture_groups.split(","))
    roots = resolve_roots(run_dir / "pids.txt", groups)
    output = args.output_dir or run_dir / "p032_resources"
    output.mkdir(parents=True, exist_ok=False)
    resource_dir = output / "process_trees"
    hardware_dir = output / "hardware"
    commands = (
        [sys.executable, str(ROOT / "tools/experiments/sample_p032_live_process_trees.py"),
         "--output-dir", str(resource_dir), "--interval-s", str(args.interval_s),
         *(item for group, (pid, _) in roots.items() for item in ("--root", f"{group}={pid}"))],
        [sys.executable, str(ROOT / "tools/experiments/sample_p044_hardware_health.py"),
         "--output-dir", str(hardware_dir), "--interval-s", str(args.hardware_interval_s)],
    )
    provenance: dict[str, Any] = {
        "schema": "p032_live_resource_measurement_v1",
        "run_dir": str(run_dir),
        "run_id": run_dir.name,
        "git_commit": git_value("rev-parse", "HEAD"),
        "git_status_short": git_value("status", "--short"),
        "architecture_groups": groups,
        "live_process_roots": {group: {"process": GROUP_TO_PROCESS[group],
                                       "pid": pid, "starttime_ticks": starttime}
                               for group, (pid, starttime) in roots.items()},
        "resource_interval_s": args.interval_s,
        "hardware_interval_s": args.hardware_interval_s,
        "duration_s": args.duration_s,
        "warm_up_s": args.warm_up_s,
        "live_run_metadata_paths": sorted(
            [str(path) for path in run_dir.glob("*run_metadata.json")]
            + [str(path) for path in
               (ROOT / "bags/live_camera").glob(f"{run_dir.name}*/run_metadata.json")]
        ),
    }
    stop = threading.Event()
    def request_stop(_signum: int, _frame: Any) -> None:
        stop.set()
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    processes: list[subprocess.Popen[str]] = []
    try:
        for command, name in zip(commands, ("process_trees", "hardware")):
            log = (output / f"{name}.log").open("w", encoding="utf-8")
            try:
                proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, text=True)
            finally:
                log.close()
            processes.append(proc)
        startup_deadline = time.monotonic() + 10.0
        while time.monotonic() < startup_deadline:
            if any(proc.poll() is not None for proc in processes):
                raise ValueError("resource sampler exited during startup")
            if all((folder / "samples.jsonl").is_file()
                   and (folder / "samples.jsonl").stat().st_size > 0
                   for folder in (resource_dir, hardware_dir)):
                break
            if stop.wait(0.1):
                raise ValueError("measurement interrupted during startup")
        else:
            raise ValueError("resource samplers produced no startup samples")
        start_ns = time.monotonic_ns()
        provenance["analysis_start_monotonic_ns"] = start_ns
        deadline = time.monotonic() + args.duration_s
        while time.monotonic() < deadline:
            if stop.wait(min(0.25, max(0.0, deadline - time.monotonic()))):
                raise ValueError("measurement interrupted")
            if any(proc.poll() is not None for proc in processes):
                raise ValueError("resource sampler exited during measurement")
            if any(process_starttime(pid) != starttime for pid, starttime in roots.values()):
                raise ValueError("live architecture root changed during measurement")
        end_ns = time.monotonic_ns()
        provenance["analysis_end_monotonic_ns"] = end_ns
    finally:
        for proc in processes:
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)
        for proc in processes:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        provenance["sampler_return_codes"] = [proc.returncode for proc in processes]
        (output / "provenance.json").write_text(
            json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
    if any(proc.returncode != 0 for proc in processes):
        raise ValueError("resource sampler failed; inspect sampler logs")
    command = [
        sys.executable, str(ROOT / "tools/analysis/analyse_p032_final_resources.py"),
        "--resources-samples", str(resource_dir / "samples.jsonl"),
        "--hardware-samples", str(hardware_dir / "samples.jsonl"),
        "--output-json", str(output / "analysis.json"),
        "--output-markdown", str(output / "analysis.md"),
        "--warm-up-s", str(args.warm_up_s),
        "--analysis-start-monotonic-ns", str(start_ns),
        "--analysis-end-monotonic-ns", str(end_ns),
        "--architecture-groups", ",".join(groups),
    ]
    with (output / "analysis_stdout.json").open("w", encoding="utf-8") as log:
        subprocess.run(command, check=True, stdout=log)
    resource_summary = json.loads((resource_dir / "summary.json").read_text())
    analysis = json.loads((output / "analysis.json").read_text())
    check_result(resource_summary, analysis, roots)
    coverage = {
        "process_trees": sample_coverage(
            resource_dir / "samples.jsonl", "sample_monotonic_ns",
            groups, start_ns, end_ns, args.interval_s,
        ),
        "hardware": sample_coverage(
            hardware_dir / "samples.jsonl", "monotonic_ns",
            ("hardware",), start_ns, end_ns, args.hardware_interval_s,
        ),
    }
    (output / "coverage.json").write_text(
        json.dumps(coverage, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    print(json.dumps({"output_dir": str(output), "integrity": "pass"}, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--architecture-groups", default="detector,tracker,tim,controller")
    parser.add_argument("--duration-s", type=float, required=True)
    parser.add_argument("--warm-up-s", type=float, default=60.0)
    parser.add_argument("--interval-s", type=float, default=1.0)
    parser.add_argument("--hardware-interval-s", type=float, default=5.0)
    args = parser.parse_args()
    try:
        return measure(args)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"measurement failed: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
