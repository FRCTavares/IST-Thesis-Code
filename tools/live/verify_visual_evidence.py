#!/usr/bin/env python3
"""Verify a finalized, separate MJPEG visual file for a retained live run."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPORT_NAME = "visual_evidence_status.json"
RUN_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def _run(command: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout)


def verify_visual(
    bag_dir: Path, run_id: str, recorder_alive_at_stop: bool | None = None,
    finalization: str | None = None,
) -> dict:
    if not RUN_ID_RE.fullmatch(run_id) or ".." in run_id:
        raise ValueError("unsafe run_id")
    visual = bag_dir / f"visual_{run_id}.mkv"
    report = {
        "schema_version": 1,
        "run_id": run_id,
        "visual_file": str(visual),
        "file_present": visual.is_file(),
        "recorder_alive_at_stop": recorder_alive_at_stop,
        "finalization": finalization,
        "passed": False,
        "errors": [],
    }
    errors = report["errors"]
    if recorder_alive_at_stop is False:
        errors.append("visual recorder was not alive when stop was requested")
    if finalization not in (None, "graceful"):
        errors.append("visual recorder did not finalize gracefully")
    if not visual.is_file() or visual.stat().st_size == 0:
        errors.append("visual file missing or empty")
        return report

    report["bytes"] = visual.stat().st_size
    try:
        probe = _run([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-count_frames", "-show_entries",
            "stream=codec_name,width,height,nb_read_frames:format=duration,size:format_tags=creation_time",
            "-of", "json", str(visual),
        ], 90)
        if probe.returncode != 0:
            errors.append(f"ffprobe failed: {probe.stderr[-1000:]}")
            return report
        metadata = json.loads(probe.stdout)
        streams = metadata.get("streams") or []
        if len(streams) != 1:
            errors.append("expected one video stream")
            return report
        stream = streams[0]
        fmt = metadata.get("format") or {}
        duration = float(fmt.get("duration") or 0)
        frames = int(stream.get("nb_read_frames") or 0)
        report.update({
            "codec": stream.get("codec_name"),
            "width": stream.get("width"),
            "height": stream.get("height"),
            "duration_s": duration,
            "decoded_frames": frames,
            "measured_fps": round(frames / duration, 6) if duration > 0 else None,
            "container_creation_time": (fmt.get("tags") or {}).get("CREATION_TIME"),
        })
        if stream.get("codec_name") != "mjpeg":
            errors.append("visual codec is not MJPEG")
        if (stream.get("width"), stream.get("height")) != (640, 480):
            errors.append("visual resolution is not 640x480")
        if frames <= 0 or duration <= 0:
            errors.append("visual has no decoded frames or duration")

        packets = _run([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "packet=pts_time", "-of", "csv=p=0", str(visual),
        ], max(90, duration))
        if packets.returncode != 0:
            errors.append(f"packet timestamp probe failed: {packets.stderr[-1000:]}")
        else:
            pts = [float(line) for line in packets.stdout.splitlines() if line.strip()]
            gaps = [next_pts - pts[i] for i, next_pts in enumerate(pts[1:])]
            monotonic = bool(pts) and all(gap >= 0 for gap in gaps)
            report["timestamps"] = {
                "basis": "ffmpeg input wallclock, Matroska PTS relative to first frame",
                "packet_count": len(pts),
                "first_pts_s": pts[0] if pts else None,
                "last_pts_s": pts[-1] if pts else None,
                "nondecreasing": monotonic,
                "duplicate_count": sum(gap == 0 for gap in gaps),
                "max_gap_s": round(max(gaps), 6) if gaps else None,
            }
            if not monotonic or len(pts) != frames:
                errors.append("visual packet timestamps missing, reversed, or count mismatched")

        decoded = _run([
            "ffmpeg", "-hide_banner", "-nostdin", "-v", "warning",
            "-i", str(visual), "-f", "null", "-",
        ], max(90, min(1800, duration * 2 + 30)))
        report["decode_to_null"] = {
            "returncode": decoded.returncode,
            "warnings_tail": decoded.stderr[-2000:],
        }
        if decoded.returncode != 0:
            errors.append("ffmpeg decode-to-null failed")
    except (OSError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        errors.append(f"visual verification failed: {exc}")
    report["passed"] = not errors
    return report


def _write_atomic(path: Path, report: dict) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(report, out, indent=2, sort_keys=True)
            out.write("\n")
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bag-dir", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--recorder-alive-at-stop", choices=("true", "false"))
    parser.add_argument("--finalization", choices=("graceful", "failed"))
    args = parser.parse_args(argv)
    bag_dir = args.bag_dir.resolve()
    if not bag_dir.is_dir():
        parser.error(f"bag directory missing: {bag_dir}")
    alive = None if args.recorder_alive_at_stop is None else args.recorder_alive_at_stop == "true"
    report = verify_visual(bag_dir, args.run_id, alive, args.finalization)
    path = bag_dir / REPORT_NAME
    _write_atomic(path, report)
    print(f"[evidence] visual {'passed' if report['passed'] else 'failed'} ({path})")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
