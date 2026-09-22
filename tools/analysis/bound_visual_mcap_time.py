#!/usr/bin/env python3
"""Bound ffmpeg packet-receipt UTC from retained MKV PTS; never infer capture time.

The launch clock precedes ffmpeg input. The finalized file mtime follows its
last packet write. With input wallclock PTS rebased to the first packet, these
two clocks bound packet receipt if the system wall clock was continuous and the
recorded file mtime is authentic. The dashboard's ROS source header is absent
from the MKV and the field MCAP, so this is NOT a physical-person attribution
or a certificate of zero wrong-person command duration.
"""
from __future__ import annotations

import argparse
import calendar
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import subprocess
import sys

UTC_NS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?Z$")


def parse_utc_ns(value: str) -> int:
    match = UTC_NS_RE.fullmatch(value)
    if not match:
        raise ValueError("visual started_at_utc must be a UTC timestamp ending in Z")
    second = datetime.strptime(match.group(1), "%Y-%m-%dT%H:%M:%S")
    return calendar.timegm(second.timetuple()) * 1_000_000_000 + int(
        (match.group(2) or "").ljust(9, "0") or "0"
    )


def parse_pts_ns(lines: str) -> list[int]:
    pts: list[int] = []
    for line in lines.splitlines():
        value = line.strip().rstrip(",")
        if not value:
            continue
        try:
            number = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("corrupt visual packet PTS") from exc
        if not number.is_finite() or number < 0:
            raise ValueError("invalid visual packet PTS")
        pts.append(int(number * 1_000_000_000))
    return pts


def calculate_bounds(start_ns: int, final_mtime_ns: int, pts_ns: list[int]) -> dict:
    if len(pts_ns) < 2 or any(b < a for a, b in zip(pts_ns, pts_ns[1:])):
        raise ValueError("at least two nondecreasing visual PTS are required")
    positive = [b - a for a, b in zip(pts_ns, pts_ns[1:]) if b > a]
    if not positive:
        raise ValueError("visual PTS contain no positive time advance")
    # At least one 25-Hz nominal input tick (40 ms), even if a future
    # recording shows finer packet spacing; larger observed minimum
    # increments widen the diagnostic interval. The actual frame rate
    # remains variable and is not inferred from this nominal clock tick.
    tick_ns = max(40_000_000, min(positive))
    last_delta_ns = pts_ns[-1] - pts_ns[0]
    first_latest_ns = final_mtime_ns - last_delta_ns + tick_ns
    if final_mtime_ns <= start_ns or first_latest_ns < start_ns:
        raise ValueError("visual launch, PTS and finalized file mtime conflict")
    rows = []
    for index, pts in enumerate(pts_ns):
        delta = pts - pts_ns[0]
        earliest = max(start_ns, start_ns + delta - tick_ns)
        latest = final_mtime_ns - last_delta_ns + delta + 2 * tick_ns
        if latest < earliest:
            raise ValueError("visual packet receipt bounds conflict")
        rows.append((index, pts, earliest, latest))
    return {
        "first_packet_receipt_utc_ns_conditional": [start_ns, first_latest_ns],
        "first_packet_window_s": (first_latest_ns - start_ns) / 1e9,
        "observed_min_positive_pts_tick_ns": tick_ns,
        "max_packet_receipt_window_s": max((end - begin) / 1e9 for _, _, begin, end in rows),
        "packet_count": len(rows),
        "duplicate_pts_count": len(pts_ns) - 1 - len(positive),
        "max_pts_gap_s": max(b - a for a, b in zip(pts_ns, pts_ns[1:])) / 1e9,
        "rows": rows,
        "physical_person_command_attribution": "unresolved",
        "source_capture_time_resolved": False,
    }


def inspect(bag_dir: Path, run_id: str) -> tuple[dict, list[tuple[int, int, int, int]]]:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", run_id) or ".." in run_id:
        raise ValueError("unsafe run ID")
    bag_dir = bag_dir.resolve()
    visual = bag_dir / f"visual_{run_id}.mkv"
    metadata = json.loads((bag_dir / "run_metadata.json").read_text())
    status = json.loads((bag_dir / "visual_evidence_status.json").read_text())
    if metadata.get("run_id") != run_id or status.get("run_id") != run_id:
        raise ValueError("run ID mismatch in visual evidence")
    if not status.get("passed") or not visual.is_file():
        raise ValueError("visual evidence not passed or file missing")
    details = metadata.get("visual")
    if not isinstance(details, dict) or Path(details.get("file", "")).resolve() != visual.resolve():
        raise ValueError("visual metadata file mismatch")
    if "ffmpeg input wallclock" not in details.get("timestamp_basis", ""):
        raise ValueError("visual wallclock PTS contract missing")
    start_ns = parse_utc_ns(details.get("started_at_utc", ""))
    actual_mtime_ns = visual.stat().st_mtime_ns
    saved_mtime_ns = status.get("file_mtime_ns")
    if saved_mtime_ns is not None and saved_mtime_ns != actual_mtime_ns:
        raise ValueError("visual file mtime changed since verification")
    stream_probe = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=r_frame_rate,time_base", "-of", "json", str(visual),
    ], capture_output=True, text=True, timeout=90, check=True)
    streams = json.loads(stream_probe.stdout).get("streams") or []
    if len(streams) != 1 or streams[0].get("r_frame_rate") != "25/1":
        raise ValueError("unreviewed visual nominal timebase; cannot bound quantization")
    probe = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "packet=pts_time", "-of", "csv=p=0", str(visual),
    ], capture_output=True, text=True, timeout=1800, check=True)
    pts = parse_pts_ns(probe.stdout)
    if len(pts) != status.get("timestamps", {}).get("packet_count"):
        raise ValueError("packet count differs from retained visual verification")
    result = calculate_bounds(start_ns, actual_mtime_ns, pts)
    rows = result.pop("rows")
    result.update({
        "schema_version": 1,
        "run_id": run_id,
        "visual_file": str(visual),
        "visual_file_mtime_ns": actual_mtime_ns,
        "mtime_provenance": "retained_visual_status" if saved_mtime_ns is not None else "current_filesystem_only",
        "status_file_has_original_mtime": saved_mtime_ns is not None,
        "time_domain": "system UTC nanoseconds, conditional ffmpeg packet receipt",
        "qualification": (
            "Conditional on original finalized mtime, continuous system wallclock, "
            "and current 25-Hz MJPEG input timestamp quantization. Packet receipt "
            "is later than camera capture by an unbounded amount in this evidence. "
            "No zero wrong-person command claim follows from these bounds alone."
        ),
    })
    return result, rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bag-dir", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--json-out", required=True, type=Path)
    parser.add_argument("--csv-out", required=True, type=Path)
    args = parser.parse_args()
    if args.json_out.exists() or args.csv_out.exists():
        parser.error("output already exists; inspect before retry")
    try:
        result, rows = inspect(args.bag_dir, args.run_id)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        print(f"[error] visual receipt bound unavailable: {exc}", file=sys.stderr)
        return 1
    args.json_out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    with args.csv_out.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("packet_index", "pts_ns", "receipt_earliest_utc_ns", "receipt_latest_utc_ns"))
        writer.writerows(rows)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
