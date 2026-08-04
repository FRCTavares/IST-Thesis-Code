#!/usr/bin/env python3
"""Periodically sample Raspberry Pi health during a P044 soak."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import signal
import statistics
import subprocess
import time
from typing import Any


SAMPLE_SCHEMA = "p044_hardware_health_sample_v1"
SUMMARY_SCHEMA = "p044_hardware_health_summary_v1"


def parse_temperature(text: str) -> float | None:
    match = re.search(
        r"temp=([-+]?[0-9]+(?:\.[0-9]+)?)",
        text,
    )
    return float(match.group(1)) if match else None


def parse_throttled(text: str) -> int | None:
    match = re.search(
        r"throttled=(0x[0-9a-fA-F]+|[0-9]+)",
        text,
    )
    return int(match.group(1), 0) if match else None


def parse_frequency(text: str) -> int | None:
    match = re.search(r"=([0-9]+)", text)
    return int(match.group(1)) if match else None


def parse_voltage(text: str) -> float | None:
    match = re.search(
        r"volt=([-+]?[0-9]+(?:\.[0-9]+)?)",
        text,
    )
    return float(match.group(1)) if match else None


def run_command(
    command: list[str],
) -> tuple[str, str | None]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=3.0,
        )
    except Exception as exc:
        return "", f"{type(exc).__name__}: {exc}"

    output = completed.stdout.strip()

    if completed.returncode != 0:
        error = completed.stderr.strip()
        return output, (
            f"returncode={completed.returncode}: {error}"
        )

    return output, None


def read_meminfo() -> dict[str, int]:
    values: dict[str, int] = {}

    try:
        for line in Path("/proc/meminfo").read_text(
            encoding="utf-8"
        ).splitlines():
            name, _, remainder = line.partition(":")
            token = remainder.strip().split()[0]
            values[name] = int(token)
    except (OSError, ValueError, IndexError):
        return {}

    return values


def finite_summary(
    values: list[float | int | None],
) -> dict[str, float | int | None]:
    finite = [
        float(value)
        for value in values
        if value is not None
        and math.isfinite(float(value))
    ]

    if not finite:
        return {
            "count": 0,
            "minimum": None,
            "mean": None,
            "maximum": None,
        }

    return {
        "count": len(finite),
        "minimum": min(finite),
        "mean": statistics.fmean(finite),
        "maximum": max(finite),
    }


class StopState:
    def __init__(self) -> None:
        self.stop = False

    def handler(self, _signal: int, _frame: Any) -> None:
        self.stop = True


def collect_sample() -> dict[str, Any]:
    temperature_raw, temperature_error = run_command(
        ["vcgencmd", "measure_temp"]
    )
    throttled_raw, throttled_error = run_command(
        ["vcgencmd", "get_throttled"]
    )
    frequency_raw, frequency_error = run_command(
        ["vcgencmd", "measure_clock", "arm"]
    )
    voltage_raw, voltage_error = run_command(
        ["vcgencmd", "measure_volts", "core"]
    )

    meminfo = read_meminfo()

    try:
        load_1, load_5, load_15 = (
            float(value)
            for value in Path("/proc/loadavg")
            .read_text(encoding="utf-8")
            .split()[:3]
        )
    except (OSError, ValueError):
        load_1 = load_5 = load_15 = None

    errors = {
        name: value
        for name, value in {
            "temperature": temperature_error,
            "throttled": throttled_error,
            "arm_frequency": frequency_error,
            "core_voltage": voltage_error,
        }.items()
        if value is not None
    }

    return {
        "schema": SAMPLE_SCHEMA,
        "wall_time_ns": time.time_ns(),
        "monotonic_ns": time.monotonic_ns(),
        "temperature_c": parse_temperature(
            temperature_raw
        ),
        "throttled": parse_throttled(throttled_raw),
        "throttled_raw": throttled_raw,
        "arm_frequency_hz": parse_frequency(
            frequency_raw
        ),
        "core_voltage_v": parse_voltage(voltage_raw),
        "mem_total_kib": meminfo.get("MemTotal"),
        "mem_available_kib": meminfo.get(
            "MemAvailable"
        ),
        "load_average": {
            "one_minute": load_1,
            "five_minutes": load_5,
            "fifteen_minutes": load_15,
        },
        "errors": errors,
    }


def build_summary(
    samples: list[dict[str, Any]],
    started_monotonic_ns: int,
) -> dict[str, Any]:
    throttle_values = [
        sample.get("throttled")
        for sample in samples
        if sample.get("throttled") is not None
    ]

    return {
        "schema": SUMMARY_SCHEMA,
        "runtime_s": (
            time.monotonic_ns()
            - started_monotonic_ns
        )
        / 1e9,
        "sample_count": len(samples),
        "temperature_c": finite_summary(
            [
                sample.get("temperature_c")
                for sample in samples
            ]
        ),
        "arm_frequency_hz": finite_summary(
            [
                sample.get("arm_frequency_hz")
                for sample in samples
            ]
        ),
        "core_voltage_v": finite_summary(
            [
                sample.get("core_voltage_v")
                for sample in samples
            ]
        ),
        "mem_available_kib": finite_summary(
            [
                sample.get("mem_available_kib")
                for sample in samples
            ]
        ),
        "throttle_sample_count": len(
            throttle_values
        ),
        "nonzero_throttle_sample_count": sum(
            int(value) != 0
            for value in throttle_values
        ),
        "maximum_throttle_value": (
            max(int(value) for value in throttle_values)
            if throttle_values
            else None
        ),
        "samples_with_errors": sum(
            bool(sample.get("errors"))
            for sample in samples
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--interval-s",
        type=float,
        default=5.0,
    )
    parser.add_argument(
        "--duration-s",
        type=float,
        default=0.0,
        help=(
            "Stop after this duration. Zero runs until a signal."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    samples_path = args.output_dir / "samples.jsonl"
    summary_path = args.output_dir / "summary.json"

    stop = StopState()
    signal.signal(signal.SIGINT, stop.handler)
    signal.signal(signal.SIGTERM, stop.handler)

    started = time.monotonic_ns()
    deadline = (
        None
        if args.duration_s <= 0
        else time.monotonic() + args.duration_s
    )

    samples: list[dict[str, Any]] = []
    interval = max(0.1, float(args.interval_s))

    with samples_path.open(
        "w",
        encoding="utf-8",
    ) as stream:
        while not stop.stop:
            if (
                deadline is not None
                and time.monotonic() >= deadline
            ):
                break

            sample = collect_sample()
            samples.append(sample)
            stream.write(
                json.dumps(sample, sort_keys=True) + "\n"
            )
            stream.flush()

            target = time.monotonic() + interval

            while (
                not stop.stop
                and time.monotonic() < target
            ):
                if (
                    deadline is not None
                    and time.monotonic() >= deadline
                ):
                    stop.stop = True
                    break

                time.sleep(
                    min(0.2, target - time.monotonic())
                )

    summary = build_summary(samples, started)
    summary_path.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
