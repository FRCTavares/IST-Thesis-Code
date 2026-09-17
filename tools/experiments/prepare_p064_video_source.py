#!/usr/bin/env python3
"""Prepare a compressed exact-timestamp video source bag for Issue #64.

The source video is decoded once with FFmpeg.  Per-frame timestamps come from
FFprobe integer best-effort timestamps and the stream time base, never from
wall-clock replay timing or a nominal average frame rate.

The resulting /camera/image_raw bag uses MCAP's native zstd_fast storage preset.
Source presentation times are shifted by one fixed positive offset because the
Issue #64 appearance contract deliberately rejects non-positive image stamps.
The shift changes no inter-frame interval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import subprocess
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable


SCHEMA = "p064_video_source_v1"
DEFAULT_TIMESTAMP_OFFSET_NS = 1_000_000_000
STORAGE_PRESET = "zstd_fast"
DEFAULT_TOPIC = "/camera/image_raw"
DEFAULT_FRAME_ID = "camera"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def timestamp_digest(values: Iterable[int]) -> str:
    digest = hashlib.sha256()
    digest.update(b"p064_video_timestamp_sequence_v1\0")
    for value in values:
        digest.update(struct.pack(">q", int(value)))
    return digest.hexdigest()


def parse_time_base(value: str) -> Fraction:
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError(f"invalid video time base: {value!r}") from exc

    if result <= 0:
        raise ValueError("video time base must be positive")

    return result


def exact_pts_ns(tick: int, time_base: Fraction) -> int:
    value = Fraction(int(tick)) * time_base * 1_000_000_000

    if value.denominator != 1:
        raise ValueError(
            "video PTS cannot be represented exactly in integer nanoseconds: "
            f"tick={tick} time_base={time_base}"
        )

    return int(value)


def map_source_timestamps(
    frame_ticks: Iterable[int],
    *,
    time_base: Fraction,
    timestamp_offset_ns: int,
) -> tuple[list[int], list[int]]:
    ticks = [int(value) for value in frame_ticks]

    if not ticks:
        raise ValueError("video contains no timestamped frames")

    source_pts_ns = [
        exact_pts_ns(value, time_base)
        for value in ticks
    ]

    if any(
        later <= earlier
        for earlier, later in zip(source_pts_ns, source_pts_ns[1:])
    ):
        raise ValueError("video frame PTS must be strictly increasing")

    mapped = [
        int(timestamp_offset_ns) + value
        for value in source_pts_ns
    ]

    if mapped[0] <= 0:
        raise ValueError(
            "timestamp offset does not make the first mapped timestamp positive"
        )

    if any(
        later <= earlier
        for earlier, later in zip(mapped, mapped[1:])
    ):
        raise ValueError("mapped timestamps must be strictly increasing")

    return source_pts_ns, mapped


def probe_video(video_path: Path) -> dict[str, Any]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name,width,height,time_base",
        "-show_entries",
        "frame=best_effort_timestamp",
        "-of",
        "json",
        str(video_path),
    ]

    result = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(result.stdout)
    streams = payload.get("streams", [])

    if len(streams) != 1:
        raise RuntimeError(
            f"expected exactly one selected video stream, found {len(streams)}"
        )

    stream = streams[0]

    width = int(stream.get("width", 0))
    height = int(stream.get("height", 0))

    if width <= 0 or height <= 0:
        raise RuntimeError("ffprobe returned invalid video dimensions")

    time_base_text = str(stream.get("time_base", ""))
    time_base = parse_time_base(time_base_text)

    frames = payload.get("frames", [])
    ticks = []

    for index, frame in enumerate(frames):
        value = frame.get("best_effort_timestamp")

        if value is None:
            raise RuntimeError(
                f"frame {index} has no best_effort_timestamp"
            )

        ticks.append(int(value))

    if not ticks:
        raise RuntimeError("ffprobe returned no video frames")

    return {
        "codec_name": str(stream.get("codec_name", "")),
        "width": width,
        "height": height,
        "time_base_text": time_base_text,
        "time_base": time_base,
        "frame_ticks": ticks,
    }


def ffmpeg_decode_command(video_path: Path) -> list[str]:
    return [
        "ffmpeg",
        "-nostdin",
        "-v",
        "error",
        "-i",
        str(video_path),
        "-map",
        "0:v:0",
        "-fps_mode",
        "passthrough",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "pipe:1",
    ]


def read_exact(stream: Any, size: int) -> bytes:
    chunks = []
    remaining = size

    while remaining > 0:
        chunk = stream.read(remaining)

        if not chunk:
            break

        chunks.append(chunk)
        remaining -= len(chunk)

    return b"".join(chunks)


def make_storage_options(output_bag: Path) -> Any:
    import rosbag2_py

    options = rosbag2_py.StorageOptions(
        uri=str(output_bag),
        storage_id="mcap",
    )
    options.storage_preset_profile = STORAGE_PRESET
    return options


def artifact_manifest(output_bag: Path) -> list[dict[str, Any]]:
    artifacts = []

    for path in sorted(output_bag.iterdir()):
        if not path.is_file():
            continue

        artifacts.append(
            {
                "file": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )

    return artifacts


def write_video_source(
    *,
    video_path: Path,
    output_bag: Path,
    timestamp_offset_ns: int,
    topic: str,
    frame_id: str,
    expected_video_sha256: str | None,
) -> dict[str, Any]:
    import rosbag2_py
    from rclpy.serialization import serialize_message
    from rclpy.time import Time as RclpyTime
    from sensor_msgs.msg import Image

    source_sha256 = sha256_file(video_path)

    if expected_video_sha256 is not None:
        expected = expected_video_sha256.strip().lower()

        if source_sha256 != expected:
            raise RuntimeError(
                "source video SHA-256 mismatch: "
                f"actual={source_sha256} expected={expected}"
            )

    probe = probe_video(video_path)

    source_pts_ns, mapped_timestamps_ns = map_source_timestamps(
        probe["frame_ticks"],
        time_base=probe["time_base"],
        timestamp_offset_ns=timestamp_offset_ns,
    )

    writer = rosbag2_py.SequentialWriter()
    writer.open(
        make_storage_options(output_bag),
        rosbag2_py.ConverterOptions(
            input_serialization_format="cdr",
            output_serialization_format="cdr",
        ),
    )
    writer.create_topic(
        rosbag2_py.TopicMetadata(
            id=0,
            name=topic,
            type="sensor_msgs/msg/Image",
            serialization_format="cdr",
        )
    )

    width = int(probe["width"])
    height = int(probe["height"])
    frame_size = width * height * 3
    command = ffmpeg_decode_command(video_path)

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if process.stdout is None or process.stderr is None:
        raise RuntimeError("failed to open FFmpeg pipes")

    written = 0

    try:
        for index, timestamp_ns in enumerate(mapped_timestamps_ns):
            frame = read_exact(process.stdout, frame_size)

            if len(frame) != frame_size:
                raise RuntimeError(
                    "FFmpeg ended before the probed frame timeline: "
                    f"frame={index} bytes={len(frame)} expected={frame_size}"
                )

            message = Image()
            message.header.stamp = RclpyTime(
                nanoseconds=timestamp_ns
            ).to_msg()
            message.header.frame_id = frame_id
            message.height = height
            message.width = width
            message.encoding = "bgr8"
            message.is_bigendian = 0
            message.step = width * 3
            message.data = frame

            writer.write(
                topic,
                serialize_message(message),
                timestamp_ns,
            )
            written += 1

        extra = process.stdout.read(1)
        stderr = process.stderr.read().decode("utf-8", "replace")
        return_code = process.wait()

        if return_code != 0:
            raise RuntimeError(
                f"FFmpeg decode failed with status {return_code}: {stderr}"
            )

        if extra:
            raise RuntimeError(
                "FFmpeg produced more frames than the ffprobe timeline"
            )

    finally:
        if process.poll() is None:
            process.kill()
            process.wait()

        del writer

    if written != len(mapped_timestamps_ns):
        raise RuntimeError(
            f"written frame mismatch: {written} != {len(mapped_timestamps_ns)}"
        )

    provenance = {
        "schema": SCHEMA,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "scientific_status": "development_only_issue_64_source_preparation",
        "source_video": {
            "path": str(video_path),
            "sha256": source_sha256,
            "codec_name": probe["codec_name"],
            "width": width,
            "height": height,
            "frame_count": len(mapped_timestamps_ns),
            "time_base": probe["time_base_text"],
            "first_pts_ns": source_pts_ns[0],
            "last_pts_ns": source_pts_ns[-1],
            "pts_sha256": timestamp_digest(source_pts_ns),
        },
        "timestamp_mapping": {
            "rule": "mapped_timestamp_ns = timestamp_offset_ns + exact_source_pts_ns",
            "timestamp_offset_ns": int(timestamp_offset_ns),
            "first_timestamp_ns": mapped_timestamps_ns[0],
            "last_timestamp_ns": mapped_timestamps_ns[-1],
            "timestamp_sha256": timestamp_digest(mapped_timestamps_ns),
            "strictly_increasing": True,
            "inter_frame_intervals_preserved_exactly": True,
        },
        "output": {
            "bag": str(output_bag),
            "topic": topic,
            "frame_id": frame_id,
            "encoding": "bgr8",
            "width": width,
            "height": height,
            "frame_count": written,
            "storage_id": "mcap",
            "storage_preset_profile": STORAGE_PRESET,
            "ffmpeg_command": command,
            "artifact_files": artifact_manifest(output_bag),
        },
    }

    provenance_path = output_bag / "p064_video_source.json"
    provenance_path.write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(provenance, indent=2, sort_keys=True))
    return provenance


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("video_path", type=Path)
    parser.add_argument("output_bag", type=Path)
    parser.add_argument(
        "--timestamp-offset-ns",
        type=int,
        default=DEFAULT_TIMESTAMP_OFFSET_NS,
    )
    parser.add_argument("--topic", default=DEFAULT_TOPIC)
    parser.add_argument("--frame-id", default=DEFAULT_FRAME_ID)
    parser.add_argument("--expected-video-sha256")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    video_path = args.video_path.expanduser().resolve()
    output_bag = args.output_bag.expanduser().resolve()

    if not video_path.is_file():
        raise SystemExit(f"source video does not exist: {video_path}")

    if output_bag.exists():
        if not args.overwrite:
            raise SystemExit(
                f"output bag exists: {output_bag} (pass --overwrite)"
            )
        shutil.rmtree(output_bag)

    try:
        write_video_source(
            video_path=video_path,
            output_bag=output_bag,
            timestamp_offset_ns=args.timestamp_offset_ns,
            topic=args.topic,
            frame_id=args.frame_id,
            expected_video_sha256=args.expected_video_sha256,
        )
    except Exception:
        if output_bag.exists():
            shutil.rmtree(output_bag)
        raise

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
