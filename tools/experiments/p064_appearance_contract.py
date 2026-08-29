"""Scientific contracts for controlled Issue #64 appearance replay."""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


CANDIDATE_DIGEST_SCHEMA = "p064_frozen_candidate_stream_v1"
IMAGE_DIGEST_SCHEMA = "p064_image_stream_v1"
VARIANT_SCHEMA = "p064_appearance_variant_v1"


@dataclass(frozen=True)
class ImageFrameRecord:
    timestamp_ns: int
    width: int
    height: int
    encoding: str
    step: int
    data_sha256: str


def _bytes(digest: Any, value: bytes) -> None:
    digest.update(len(value).to_bytes(8, "big"))
    digest.update(value)


def _text(digest: Any, value: object) -> None:
    _bytes(digest, str(value).encode("utf-8"))


def _int(digest: Any, value: int) -> None:
    digest.update(int(value).to_bytes(8, "big", signed=True))


def _float32(digest: Any, value: float) -> None:
    digest.update(struct.pack(">f", float(value)))


def image_payload_sha256(message: Any) -> str:
    return hashlib.sha256(bytes(message.data)).hexdigest()


def image_record(message: Any, timestamp_ns: int) -> ImageFrameRecord:
    return ImageFrameRecord(
        timestamp_ns=int(timestamp_ns),
        width=int(message.width),
        height=int(message.height),
        encoding=str(message.encoding),
        step=int(message.step),
        data_sha256=image_payload_sha256(message),
    )


def validate_image_records(
    records: Iterable[ImageFrameRecord],
    *,
    require_single_resolution: bool = True,
) -> list[ImageFrameRecord]:
    ordered = sorted(records, key=lambda item: item.timestamp_ns)
    if not ordered:
        raise ValueError("image timeline is empty")
    timestamps = [item.timestamp_ns for item in ordered]
    if timestamps[0] <= 0:
        raise ValueError("image timestamps must be positive")
    if len(timestamps) != len(set(timestamps)):
        raise ValueError("duplicate/ambiguous image timestamp")
    if require_single_resolution:
        sizes = {(item.width, item.height) for item in ordered}
        if len(sizes) != 1:
            raise ValueError("image timeline changes resolution")
    for item in ordered:
        if item.width <= 0 or item.height <= 0 or item.step <= 0:
            raise ValueError("invalid image geometry")
        if len(item.data_sha256) != 64:
            raise ValueError("invalid image payload digest")
    return ordered


def image_stream_digest(records: Iterable[ImageFrameRecord]) -> str:
    ordered = validate_image_records(records)
    digest = hashlib.sha256()
    _text(digest, IMAGE_DIGEST_SCHEMA)
    for item in ordered:
        _int(digest, item.timestamp_ns)
        _int(digest, item.width)
        _int(digest, item.height)
        _text(digest, item.encoding)
        _int(digest, item.step)
        _text(digest, item.data_sha256)
    return digest.hexdigest()


def timestamp_digest(records: Iterable[ImageFrameRecord]) -> str:
    ordered = validate_image_records(records)
    digest = hashlib.sha256()
    _text(digest, "p064_exact_timestamp_timeline_v1")
    for item in ordered:
        _int(digest, item.timestamp_ns)
    return digest.hexdigest()


def validate_exact_correspondence(
    master: Iterable[ImageFrameRecord],
    appearance: Iterable[ImageFrameRecord],
) -> tuple[list[ImageFrameRecord], list[ImageFrameRecord]]:
    master_ordered = validate_image_records(master)
    appearance_ordered = validate_image_records(appearance)
    master_stamps = [item.timestamp_ns for item in master_ordered]
    appearance_stamps = [item.timestamp_ns for item in appearance_ordered]
    if len(master_stamps) != len(appearance_stamps):
        raise ValueError(
            "appearance/master frame-count mismatch: "
            f"{len(appearance_stamps)} != {len(master_stamps)}"
        )
    if appearance_stamps != master_stamps:
        missing = sorted(set(master_stamps) - set(appearance_stamps))
        extra = sorted(set(appearance_stamps) - set(master_stamps))
        raise ValueError(
            "appearance timestamps do not exactly match master; "
            f"missing={missing[:5]} extra={extra[:5]}"
        )
    return master_ordered, appearance_ordered


def new_candidate_stream_digest() -> Any:
    digest = hashlib.sha256()
    _text(digest, CANDIDATE_DIGEST_SCHEMA)
    return digest


def update_candidate_stream_digest(
    digest: Any,
    *,
    semantic_time_ns: int,
    bag_time_ns: int,
    message: Any,
) -> None:
    """Digest frozen transport evidence; IDs are not physical identity."""
    _int(digest, semantic_time_ns)
    _int(digest, bag_time_ns)
    header = getattr(message, "header", None)
    stamp = getattr(header, "stamp", None)
    header_ns = int(getattr(stamp, "sec", 0)) * 1_000_000_000 + int(
        getattr(stamp, "nanosec", 0)
    )
    _int(digest, header_ns)
    _text(digest, getattr(header, "frame_id", ""))
    for name in (
        "frame_id",
        "src_stamp_ns",
        "t_cam_msg_seen_ns",
        "t_track_cb_start_ns",
        "t_track_cb_end_ns",
    ):
        _int(digest, int(getattr(message, name, 0)))
    tracks = list(getattr(message, "tracks", []))
    _int(digest, len(tracks))
    for track in tracks:
        _int(digest, int(getattr(track, "id", 0)))
        for name in ("cx", "cy", "w", "h", "score"):
            _float32(digest, float(getattr(track, name, 0.0)))
        _text(digest, getattr(track, "label", ""))


def candidate_stream_digest(events: Iterable[tuple[int, int, Any]]) -> str:
    digest = new_candidate_stream_digest()
    for semantic_time_ns, bag_time_ns, message in events:
        update_candidate_stream_digest(
            digest,
            semantic_time_ns=semantic_time_ns,
            bag_time_ns=bag_time_ns,
            message=message,
        )
    return digest.hexdigest()


def validate_candidate_digest(actual: str, expected: str | None) -> None:
    if expected is None:
        return
    expected = expected.strip().lower()
    if len(expected) != 64 or any(
        ch not in "0123456789abcdef"
        for ch in expected
    ):
        raise ValueError("expected candidate-stream digest is not SHA-256")
    if actual != expected:
        raise ValueError(
            "frozen candidate-stream digest mismatch: "
            f"actual={actual} expected={expected}"
        )


def parse_resolution(value: str) -> tuple[int, int]:
    try:
        width_text, height_text = value.lower().split("x", 1)
        width, height = int(width_text), int(height_text)
    except (ValueError, AttributeError) as exc:
        raise ValueError(
            f"invalid resolution {value!r}; expected WIDTHxHEIGHT"
        ) from exc
    if width <= 0 or height <= 0:
        raise ValueError("resolution dimensions must be positive")
    return width, height


def classify_resize(
    master_width: int,
    master_height: int,
    output_width: int,
    output_height: int,
) -> str:
    if (output_width, output_height) == (master_width, master_height):
        return "same_size"
    if output_width <= master_width and output_height <= master_height:
        return "downsample"
    return "upsample_control"


def validate_resize_evidence(
    master_width: int,
    master_height: int,
    output_width: int,
    output_height: int,
    *,
    allow_upsample_control: bool,
) -> str:
    resize_class = classify_resize(
        master_width,
        master_height,
        output_width,
        output_height,
    )
    if resize_class == "upsample_control" and not allow_upsample_control:
        raise ValueError(
            f"{output_width}x{output_height} exceeds master "
            f"{master_width}x{master_height}; upsampling is not "
            "higher-resolution evidence"
        )
    return resize_class


def aspect_ratio(width: int, height: int) -> float:
    return float(width) / float(height)


def load_variant_provenance(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != VARIANT_SCHEMA:
        raise ValueError(
            "unsupported appearance provenance schema: "
            f"{payload.get('schema')!r}"
        )
    return payload


def validate_variant_streams(
    payload: dict[str, Any],
    master: Iterable[ImageFrameRecord],
    appearance: Iterable[ImageFrameRecord],
) -> None:
    master_ordered, appearance_ordered = validate_exact_correspondence(
        master, appearance
    )
    checks = (
        (
            image_stream_digest(master_ordered),
            payload["master"]["image_stream_sha256"],
            "master image stream",
        ),
        (
            image_stream_digest(appearance_ordered),
            payload["output"]["image_stream_sha256"],
            "appearance image stream",
        ),
        (
            timestamp_digest(master_ordered),
            payload["master"]["timestamp_sha256"],
            "master timestamps",
        ),
        (
            timestamp_digest(appearance_ordered),
            payload["output"]["timestamp_sha256"],
            "appearance timestamps",
        ),
    )
    for actual, expected, label in checks:
        if actual != expected:
            raise ValueError(f"variant provenance mismatch: {label}")
    if len(master_ordered) != int(payload["master"]["frame_count"]):
        raise ValueError("variant provenance mismatch: master frame count")
    if len(appearance_ordered) != int(payload["output"]["frame_count"]):
        raise ValueError("variant provenance mismatch: output frame count")
    master_size = (master_ordered[0].width, master_ordered[0].height)
    output_size = (appearance_ordered[0].width, appearance_ordered[0].height)
    if master_size != (
        int(payload["master"]["width"]),
        int(payload["master"]["height"]),
    ):
        raise ValueError("variant provenance mismatch: master dimensions")
    if output_size != (
        int(payload["output"]["width"]),
        int(payload["output"]["height"]),
    ):
        raise ValueError("variant provenance mismatch: output dimensions")


def validate_track_timestamps(
    track_timestamps_ns: Iterable[int],
    master: Iterable[ImageFrameRecord],
) -> None:
    timestamps = [int(value) for value in track_timestamps_ns]
    if not timestamps:
        raise ValueError("candidate stream is empty")
    if any(value <= 0 for value in timestamps):
        raise ValueError("controlled candidate timestamp is non-positive")
    if len(timestamps) != len(set(timestamps)):
        raise ValueError("duplicate/ambiguous candidate timestamp")
    master_timestamps = {
        item.timestamp_ns
        for item in validate_image_records(master)
    }
    missing = [
        value
        for value in timestamps
        if value not in master_timestamps
    ]
    if missing:
        raise ValueError(
            "candidate timestamp has no exact master image; "
            f"missing={missing[:5]}"
        )
