#!/usr/bin/env python3
"""Run TIM-MARS deterministically from a complete ROS bag timeline.

This tool avoids ROS callback scheduling entirely:

1. read the complete appearance-image and track timelines;
2. preload every valid image into the shared ROS-free TimMarsRuntime;
3. process tracks in deterministic message-time order;
4. write original evidence plus deterministic TIM target and status messages.

It is intended for controlled offline evaluation, not live operation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import subprocess
import sys
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import rosbag2_py
import yaml
from cv_bridge import CvBridge
from rclpy.serialization import deserialize_message, serialize_message
from rosidl_runtime_py.utilities import get_message
from std_msgs.msg import String
from thesis_msgs.msg import TargetState, Track2DArray

from thesis_bringup.tim_mars.appearance_attachment import (
    AppearanceAttachmentConfig,
)
from thesis_bringup.tim_mars.appearance_request_policy import (
    AppearanceRequestPolicy,
)
from thesis_bringup.tim_mars.crop_quality import (
    CropQualityThresholds,
)
from thesis_bringup.tim_mars.mars_reid_backend import MarsReIdBackend
from thesis_bringup.tim_mars.ros_messages import (
    status_json_from_output,
    target_msg_from_output,
)
from thesis_bringup.tim_mars.runtime import (
    TimMarsRuntime,
    TimMarsRuntimeConfig,
)
from thesis_bringup.tim_mars.types import TargetMemoryConfig


TIM_TARGET_TOPIC = "/target_memory_mars"
TIM_STATUS_TOPIC = "/target_memory_mars/status"
SEMANTIC_DIGEST_SCHEMA = (
    "tim_mars_replay_generated_fields_v4"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run TIM-MARS deterministically from complete image and track "
            "timelines without ROS playback or callback scheduling."
        )
    )
    parser.add_argument("input_bag", type=Path)
    parser.add_argument("output_bag", type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--selected-track-id", required=True, type=int)
    parser.add_argument(
        "--image-topic",
        default="auto",
        help=(
            "Appearance image topic. 'auto' prefers /camera/image_raw and "
            "then /camera/dashboard."
        ),
    )
    parser.add_argument("--tracks-topic", default="/tracks")
    parser.add_argument("--raw-target-topic", default="/target")
    parser.add_argument(
        "--raw-target-mode",
        choices=("source", "selected_id"),
        default="source",
        help=(
            "Use the source raw-target topic unchanged or replace it "
            "deterministically from --selected-track-id."
        ),
    )
    parser.add_argument("--image-width", type=float, default=640.0)
    parser.add_argument("--image-height", type=float, default=640.0)
    parser.add_argument(
        "--tracks-are-normalized",
        action="store_true",
    )
    parser.add_argument(
        "--zero-id-when-not-visible",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--appearance-enabled",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Override canonical appearance_enabled. By default the canonical "
            "configuration value is used."
        ),
    )
    parser.add_argument(
        "--appearance-request-policy",
        choices=tuple(
            policy.value
            for policy in AppearanceRequestPolicy
        ),
        default=None,
        help=(
            "Override canonical appearance_request_policy for controlled "
            "Issue #44 experiments."
        ),
    )
    parser.add_argument(
        "--appearance-compute-min-interval-ms",
        type=float,
        default=None,
        help=(
            "Override canonical appearance_compute_min_interval_ms. "
            "Use 0 for forced-frequent controlled experiments."
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Remove an existing output bag before writing.",
    )
    parser.add_argument(
        "--skip-source-hash",
        action="store_true",
        help=(
            "Record source file sizes without hashing source "
            "files. Canonical evidence should not use this."
        ),
    )
    parser.add_argument(
        "--compact-output",
        action="store_true",
        help=(
            "Keep only tracks, raw target, and generated TIM topics in the "
            "output bag. Source images are still consumed by TIM-MARS and "
            "fully recorded in provenance, but are not duplicated."
        ),
    )
    return parser.parse_args()


def detect_storage_id(bag_path: Path) -> str:
    metadata = bag_path / "metadata.yaml"

    if metadata.is_file():
        text = metadata.read_text(encoding="utf-8", errors="ignore")

        if "storage_identifier: mcap" in text or "storage_id: mcap" in text:
            return "mcap"

        if "storage_identifier: sqlite3" in text or "storage_id: sqlite3" in text:
            return "sqlite3"

    if list(bag_path.glob("*.mcap")):
        return "mcap"

    if list(bag_path.glob("*.db3")):
        return "sqlite3"

    raise RuntimeError(f"Could not determine bag storage type: {bag_path}")


def is_compressed_bag(bag_path: Path) -> bool:
    """Detect file/message-level bag compression from metadata.yaml.

    A plain ``SequentialReader`` cannot open a compressed mcap file (it
    fails trying to parse compressed bytes as an uncompressed mcap stream);
    a compressed bag needs ``SequentialCompressionReader`` instead. The
    ``ros2 bag`` CLI handles this transparently; the raw Python bindings do
    not.
    """

    metadata = bag_path / "metadata.yaml"

    if not metadata.is_file():
        return False

    text = metadata.read_text(encoding="utf-8", errors="ignore")

    return (
        "compression_mode: FILE" in text
        or "compression_mode: MESSAGE" in text
    )


def open_reader(bag_path: Path) -> rosbag2_py.SequentialReader:
    if is_compressed_bag(bag_path):
        # rosbag2_py.SequentialCompressionReader decompresses the entire
        # mcap file up front (observed: a 1.7 GB compressed capture produced
        # a 7.5 GB decompressed file). On the 8 GB RAM / zero-swap
        # development Pi this contributed to an out-of-memory crash and full
        # reboot on 2026-08-07. Callers must decompress explicitly first
        # (see resolve_external_candidate_stream.ensure_uncompressed_bag,
        # which streams via the zstd CLI instead) rather than relying on
        # this tool to do it implicitly.
        raise RuntimeError(
            f"{bag_path} is compressed; decompress it explicitly before "
            "passing it to run_deterministic_tim_replay.py (see "
            "resolve_external_candidate_stream.ensure_uncompressed_bag) "
            "rather than relying on SequentialCompressionReader, which has "
            "caused an out-of-memory crash on this hardware"
        )

    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(
            uri=str(bag_path),
            storage_id=detect_storage_id(bag_path),
        ),
        rosbag2_py.ConverterOptions(
            input_serialization_format="cdr",
            output_serialization_format="cdr",
        ),
    )
    return reader


def topic_metadata_map(
    reader: rosbag2_py.SequentialReader,
) -> dict[str, Any]:
    return {
        metadata.name: metadata
        for metadata in reader.get_all_topics_and_types()
    }


def choose_image_topic(
    available: dict[str, Any],
    requested: str,
) -> str:
    if requested != "auto":
        if requested not in available:
            raise RuntimeError(
                f"Requested image topic is not present: {requested}"
            )
        return requested

    for candidate in (
        "/camera/image_raw",
        "/camera/dashboard",
    ):
        if candidate in available:
            return candidate

    raise RuntimeError(
        "Input bag has neither /camera/image_raw nor /camera/dashboard"
    )


def stamp_to_ns(stamp: Any) -> int:
    return (
        int(getattr(stamp, "sec", 0)) * 1_000_000_000
        + int(getattr(stamp, "nanosec", 0))
    )


def image_time_ns(message: Any) -> int:
    header = getattr(message, "header", None)
    stamp = getattr(header, "stamp", None)

    if stamp is None:
        return 0

    return stamp_to_ns(stamp)


def track_time_ns(message: Track2DArray) -> int:
    header_ns = image_time_ns(message)

    if header_ns > 0:
        return header_ns

    source_ns = int(getattr(message, "src_stamp_ns", 0))

    if source_ns > 0:
        return source_ns

    return 0


def load_canonical_parameters(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        document = yaml.safe_load(stream)

    try:
        parameters = document[
            "target_memory_mars_node"
        ]["ros__parameters"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(
            f"Invalid TIM-MARS canonical YAML structure: {path}"
        ) from exc

    if not isinstance(parameters, dict):
        raise RuntimeError(
            f"Canonical ROS parameter mapping is not a dictionary: {path}"
        )

    return dict(parameters)


def build_memory_config(
    canonical: dict[str, Any],
    *,
    image_width: float,
    image_height: float,
    appearance_enabled: bool,
) -> TargetMemoryConfig:
    allowed = {
        field.name
        for field in fields(TargetMemoryConfig)
    }

    values = {
        key: value
        for key, value in canonical.items()
        if key in allowed
    }

    values["image_width"] = float(image_width)
    values["image_height"] = float(image_height)
    values["appearance_enabled"] = bool(appearance_enabled)

    return TargetMemoryConfig(**values)


def build_crop_quality_thresholds(
    canonical: dict[str, Any],
) -> CropQualityThresholds:
    """Build crop-quality thresholds from the canonical configuration."""

    return CropQualityThresholds(
        min_width_px=float(
            canonical.get(
                "appearance_crop_min_width_px",
                12.0,
            )
        ),
        min_height_px=float(
            canonical.get(
                "appearance_crop_min_height_px",
                24.0,
            )
        ),
        max_clipping_fraction=float(
            canonical.get(
                "appearance_crop_max_clipping_fraction",
                0.10,
            )
        ),
        min_aspect_ratio=float(
            canonical.get(
                "appearance_crop_min_aspect_ratio",
                0.20,
            )
        ),
        max_aspect_ratio=float(
            canonical.get(
                "appearance_crop_max_aspect_ratio",
                1.00,
            )
        ),
        max_overlap_iou_for_memory=float(
            canonical.get(
                "appearance_crop_max_overlap_iou_for_memory",
                0.10,
            )
        ),
        min_centre_distance_norm_for_memory=float(
            canonical.get(
                "appearance_crop_min_centre_distance_norm_for_memory",
                0.04,
            )
        ),
    )


def resolve_appearance_request_policy(
    canonical: dict[str, Any],
    args: argparse.Namespace,
) -> str:
    """Resolve and validate the replay candidate-request policy."""
    override = getattr(
        args,
        "appearance_request_policy",
        None,
    )
    raw_value = (
        canonical.get(
            "appearance_request_policy",
            AppearanceRequestPolicy.ALL_CANDIDATES.value,
        )
        if override is None
        else override
    )

    try:
        return AppearanceRequestPolicy(str(raw_value)).value
    except ValueError as exc:
        supported = ", ".join(
            policy.value
            for policy in AppearanceRequestPolicy
        )
        raise ValueError(
            "Unsupported appearance_request_policy "
            f"{raw_value!r}; expected one of: {supported}"
        ) from exc


def resolve_appearance_compute_min_interval_ms(
    canonical: dict[str, Any],
    args: argparse.Namespace,
) -> float:
    """Resolve a non-negative appearance compute interval."""
    override = getattr(
        args,
        "appearance_compute_min_interval_ms",
        None,
    )
    value = float(
        canonical.get(
            "appearance_compute_min_interval_ms",
            250.0,
        )
        if override is None
        else override
    )

    if value < 0.0:
        raise ValueError(
            "appearance_compute_min_interval_ms must be non-negative"
        )

    return value


def build_runtime(
    canonical: dict[str, Any],
    args: argparse.Namespace,
) -> TimMarsRuntime:
    canonical_appearance = bool(
        canonical.get("appearance_enabled", True)
    )
    appearance_enabled = (
        canonical_appearance
        if args.appearance_enabled is None
        else bool(args.appearance_enabled)
    )
    appearance_request_policy = (
        resolve_appearance_request_policy(
            canonical,
            args,
        )
    )
    appearance_compute_min_interval_ms = (
        resolve_appearance_compute_min_interval_ms(
            canonical,
            args,
        )
    )

    memory = build_memory_config(
        canonical,
        image_width=args.image_width,
        image_height=args.image_height,
        appearance_enabled=appearance_enabled,
    )

    appearance = AppearanceAttachmentConfig(
        enabled=appearance_enabled,
        max_image_age_ms=float(
            canonical.get(
                "appearance_max_image_age_ms",
                250.0,
            )
        ),
        compute_min_interval_ms=(
            appearance_compute_min_interval_ms
        ),
        cache_ttl_ms=float(
            canonical.get(
                "appearance_cache_ttl_ms",
                750.0,
            )
        ),
        cache_max_centre_distance_norm=float(
            canonical.get(
                "appearance_cache_max_centre_distance_norm",
                0.25,
            )
        ),
        cache_min_scale_ratio=float(
            canonical.get(
                "appearance_cache_min_scale_ratio",
                0.25,
            )
        ),
        crop_quality=build_crop_quality_thresholds(
            canonical
        ),
    )

    backend = None

    if appearance_enabled:
        if not args.model.is_file():
            raise RuntimeError(
                f"MARS model does not exist: {args.model}"
            )

        backend = MarsReIdBackend(
            args.model,
            batch_size=int(
                canonical.get("mars_batch_size", 32)
            ),
        )

    return TimMarsRuntime(
        config=TimMarsRuntimeConfig(
            memory=memory,
            appearance=appearance,
            image_width=float(args.image_width),
            image_height=float(args.image_height),
            appearance_request_policy=(
                appearance_request_policy
            ),
            tracks_are_normalized=bool(
                args.tracks_are_normalized
            ),
            selected_track_id=int(args.selected_track_id),
            auto_select_largest=False,
            image_buffer_size=64,
        ),
        mars_backend=backend,
    )


def copy_topic_metadata(
    metadata: Any,
) -> rosbag2_py.TopicMetadata:
    return rosbag2_py.TopicMetadata(
        id=0,
        name=str(metadata.name),
        type=str(metadata.type),
        serialization_format=(
            str(metadata.serialization_format)
            if metadata.serialization_format
            else "cdr"
        ),
        offered_qos_profiles=list(
            metadata.offered_qos_profiles
        ),
        type_description_hash=str(
            metadata.type_description_hash
        ),
    )


def generated_topic_metadata(
    *,
    name: str,
    message_type: str,
) -> rosbag2_py.TopicMetadata:
    return rosbag2_py.TopicMetadata(
        id=0,
        name=name,
        type=message_type,
        serialization_format="cdr",
        offered_qos_profiles=[],
        type_description_hash="",
    )


def make_target_message(
    *,
    runtime: TimMarsRuntime,
    tracks_message: Track2DArray,
    result: Any,
    zero_id_when_not_visible: bool,
) -> TargetState:
    target = target_msg_from_output(
        result.output,
        image_width=runtime.config.image_width,
        image_height=runtime.config.image_height,
        tracks_are_normalized=(
            runtime.config.tracks_are_normalized
        ),
        zero_id_when_not_visible=zero_id_when_not_visible,
    )

    target.header = tracks_message.header
    target.frame_id = int(
        getattr(tracks_message, "frame_id", 0)
    )
    target.src_stamp_ns = int(
        getattr(tracks_message, "src_stamp_ns", 0)
    )
    target.t_cam_msg_seen_ns = int(
        getattr(tracks_message, "t_cam_msg_seen_ns", 0)
    )
    target.t_target_cb_start_ns = 0
    target.t_target_cb_end_ns = 0

    return target


def make_fixed_id_raw_target_message(
    *,
    tracks_message: Track2DArray,
    selected_track_id: int,
) -> TargetState:
    """Create the controlled raw target for one fixed tracker ID."""
    target = TargetState()
    target.header = tracks_message.header
    target.frame_id = int(
        getattr(tracks_message, "frame_id", 0)
    )
    target.src_stamp_ns = int(
        getattr(tracks_message, "src_stamp_ns", 0)
    )
    target.t_cam_msg_seen_ns = int(
        getattr(tracks_message, "t_cam_msg_seen_ns", 0)
    )
    target.t_target_cb_start_ns = 0
    target.t_target_cb_end_ns = 0

    selected = next(
        (
            track
            for track in tracks_message.tracks
            if int(getattr(track, "id", 0))
            == int(selected_track_id)
        ),
        None,
    )

    if selected is None:
        return target

    target.id = int(selected.id)
    target.cx = float(selected.cx)
    target.cy = float(selected.cy)
    target.w = float(selected.w)
    target.h = float(selected.h)
    target.score = float(
        getattr(selected, "score", 1.0)
    )
    target.quality = target.score
    return target


def make_status_message(
    *,
    runtime: TimMarsRuntime,
    tracks_message: Track2DArray,
    result: Any,
) -> String:
    diagnostics = result.diagnostics
    message = String()

    message.data = status_json_from_output(
        result.output,
        frame_id=int(
            getattr(tracks_message, "frame_id", 0)
        ),
        lat_ms=0.0,
        num_tracks=len(tracks_message.tracks),
        appearance_enabled=bool(
            runtime.config.appearance.enabled
        ),
        appearance_candidates=(
            diagnostics.appearance_candidates
        ),
        appearance_request_policy=(
            diagnostics.appearance_request_policy
        ),
        appearance_request_reason=(
            diagnostics.appearance_request_reason
        ),
        appearance_request_candidates=(
            diagnostics.appearance_request_candidates
        ),
        appearance_request_track_ids=(
            diagnostics.appearance_request_track_ids
        ),
        appearance_request_encoding_eligible=(
            diagnostics
            .appearance_request_encoding_eligible
        ),
        appearance_features_valid=(
            diagnostics.appearance_features_valid
        ),
        appearance_image_age_ms=(
            diagnostics.image_track_offset_ms
        ),
        appearance_skip_reason=(
            diagnostics.appearance_skip_reason
        ),
        track_timestamp_ns=(
            diagnostics.track_timestamp_ns
        ),
        selected_image_timestamp_ns=(
            diagnostics.selected_image_timestamp_ns
        ),
        image_track_offset_ms=(
            diagnostics.image_track_offset_ms
        ),
        appearance_warning=(
            diagnostics.appearance_warning
        ),
        candidate_track_ids=(
            diagnostics.candidate_track_ids
        ),
        appearance_compute_min_interval_ms=float(
            runtime.config.appearance.compute_min_interval_ms
        ),
        appearance_cache_ttl_ms=float(
            runtime.config.appearance.cache_ttl_ms
        ),
        appearance_cache_size=(
            diagnostics.appearance_cache_size
        ),
        appearance_embedding_age_ms_by_track_id=(
            diagnostics.appearance_embedding_age_ms_by_track_id
        ),
        appearance_crop_quality_by_track_id=(
            diagnostics.appearance_crop_quality_by_track_id
        ),
        appearance_encoding_rejected=(
            diagnostics.appearance_encoding_rejected
        ),
        appearance_memory_update_ineligible=(
            diagnostics.appearance_memory_update_ineligible
        ),
        appearance_encoding_eligible=(
            diagnostics.appearance_encoding_eligible
        ),
        appearance_backend_calls=(
            diagnostics.appearance_backend_calls
        ),
        appearance_backend_requested=(
            diagnostics.appearance_backend_requested
        ),
        appearance_backend_returned=(
            diagnostics.appearance_backend_returned
        ),
        appearance_backend_valid=(
            diagnostics.appearance_backend_valid
        ),
        # The complete status JSON is included in the semantic digest.
        # Normalize wall-clock duration to preserve replay determinism.
        appearance_backend_wall_ms=0.0,
        appearance_update_cooldown_remaining=(
            diagnostics
            .appearance_update_cooldown_remaining
        ),
    )

    return message


def write_streamed_output(
    *,
    writer: Any,
    source_reader: Any,
    generated_messages: list[tuple[int, int, str, bytes]],
    skipped_source_topics: set[str] | None = None,
) -> int:
    """Stream source messages and merge generated messages by bag timestamp.

    Source messages retain their original order. At a shared bag timestamp,
    every original source message is written before deterministic TIM output,
    matching the previous full-list ordering without retaining the source bag
    in memory.
    """

    skipped_topics = {
        TIM_TARGET_TOPIC,
        TIM_STATUS_TOPIC,
    }
    skipped_topics.update(
        skipped_source_topics or set()
    )

    generated_index = 0
    source_messages_written = 0
    generated_count = len(generated_messages)

    generated_messages.sort(
        key=lambda item: (
            item[0],
            item[1],
            item[2],
        )
    )

    current_time_ns: int | None = None
    current_source_group: list[tuple[str, bytes, int]] = []

    def flush_source_group() -> None:
        nonlocal generated_index
        nonlocal source_messages_written
        nonlocal current_source_group
        nonlocal current_time_ns

        if current_time_ns is None:
            return

        while (
            generated_index < generated_count
            and generated_messages[generated_index][0] < current_time_ns
        ):
            (
                generated_time_ns,
                _generated_sequence,
                generated_topic,
                generated_serialized,
            ) = generated_messages[generated_index]
            writer.write(
                generated_topic,
                generated_serialized,
                generated_time_ns,
            )
            generated_index += 1

        for topic, serialized, bag_time_ns in current_source_group:
            writer.write(
                topic,
                serialized,
                bag_time_ns,
            )
            source_messages_written += 1

        while (
            generated_index < generated_count
            and generated_messages[generated_index][0] == current_time_ns
        ):
            (
                generated_time_ns,
                _generated_sequence,
                generated_topic,
                generated_serialized,
            ) = generated_messages[generated_index]
            writer.write(
                generated_topic,
                generated_serialized,
                generated_time_ns,
            )
            generated_index += 1

        current_source_group = []

    while source_reader.has_next():
        topic, serialized, bag_time_ns = source_reader.read_next()
        bag_time_ns = int(bag_time_ns)

        if topic in skipped_topics:
            continue

        if current_time_ns is None:
            current_time_ns = bag_time_ns
        elif bag_time_ns != current_time_ns:
            flush_source_group()
            current_time_ns = bag_time_ns

        current_source_group.append(
            (
                topic,
                bytes(serialized),
                bag_time_ns,
            )
        )

    flush_source_group()

    while generated_index < generated_count:
        (
            generated_time_ns,
            _generated_sequence,
            generated_topic,
            generated_serialized,
        ) = generated_messages[generated_index]
        writer.write(
            generated_topic,
            generated_serialized,
            generated_time_ns,
        )
        generated_index += 1

    return source_messages_written


def skipped_source_topics_for_output(
    available_topics: set[str],
    *,
    tracks_topic: str,
    raw_target_topic: str,
    replace_raw_target: bool,
    compact_output: bool,
) -> set[str]:
    """Return source topics omitted from the deterministic output bag."""
    skipped = {
        TIM_TARGET_TOPIC,
        TIM_STATUS_TOPIC,
    }

    if compact_output:
        retained = {tracks_topic}
        if not replace_raw_target:
            retained.add(raw_target_topic)
        skipped.update(available_topics - retained)
    elif replace_raw_target:
        skipped.add(raw_target_topic)

    return skipped


def new_generated_semantic_digest():
    """Create a domain-separated generated-message digest."""
    digest = hashlib.sha256()
    digest.update(
        SEMANTIC_DIGEST_SCHEMA.encode("utf-8")
    )
    digest.update(b"\0")
    return digest


def _digest_bytes(
    digest: Any,
    value: bytes,
) -> None:
    """Append length-prefixed bytes to a digest."""
    digest.update(
        len(value).to_bytes(
            8,
            "big",
        )
    )
    digest.update(value)


def _digest_text(
    digest: Any,
    value: str,
) -> None:
    """Append one UTF-8 string to a digest."""
    _digest_bytes(
        digest,
        str(value).encode("utf-8"),
    )


def _digest_uint(
    digest: Any,
    value: int,
) -> None:
    """Append one non-negative integer to a digest."""
    digest.update(
        int(value).to_bytes(
            8,
            "big",
            signed=False,
        )
    )


def _digest_int(
    digest: Any,
    value: int,
) -> None:
    """Append one signed integer to a digest."""
    digest.update(
        int(value).to_bytes(
            8,
            "big",
            signed=True,
        )
    )


def _digest_float32(
    digest: Any,
    value: float,
) -> None:
    """Append one canonical IEEE-754 float32 value."""
    digest.update(
        struct.pack(
            ">f",
            float(value),
        )
    )


def update_generated_semantic_digest(
    digest: Any,
    topic: str,
    bag_time_ns: int,
    message: Any,
    *,
    raw_target_topic: str | None = None,
) -> None:
    """Append declared fields for one generated message."""
    _digest_text(digest, topic)
    _digest_int(digest, bag_time_ns)

    if (
        topic == TIM_TARGET_TOPIC
        or (
            raw_target_topic is not None
            and topic == raw_target_topic
        )
    ):
        header = message.header

        _digest_int(
            digest,
            int(header.stamp.sec),
        )
        _digest_uint(
            digest,
            int(header.stamp.nanosec),
        )
        _digest_text(
            digest,
            str(header.frame_id),
        )

        _digest_uint(
            digest,
            int(message.frame_id),
        )
        _digest_int(
            digest,
            int(message.src_stamp_ns),
        )
        _digest_int(
            digest,
            int(message.t_cam_msg_seen_ns),
        )
        _digest_int(
            digest,
            int(message.t_target_cb_start_ns),
        )
        _digest_int(
            digest,
            int(message.t_target_cb_end_ns),
        )
        _digest_uint(
            digest,
            int(message.id),
        )
        _digest_float32(
            digest,
            float(message.cx),
        )
        _digest_float32(
            digest,
            float(message.cy),
        )
        _digest_float32(
            digest,
            float(message.w),
        )
        _digest_float32(
            digest,
            float(message.h),
        )
        _digest_float32(
            digest,
            float(message.score),
        )
        _digest_float32(
            digest,
            float(message.quality),
        )
        return

    if topic == TIM_STATUS_TOPIC:
        _digest_text(
            digest,
            str(message.data),
        )
        return

    raise ValueError(
        "Unsupported TIM semantic-digest topic "
        f"{topic!r}; expected {TIM_TARGET_TOPIC!r}, "
        f"{TIM_STATUS_TOPIC!r}, or the declared "
        "generated raw-target topic"
    )


def sha256_file(path: Path) -> str:
    """Calculate SHA-256 for one file."""
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(
                1024 * 1024
            ),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def source_manifest(
    bag_path: Path,
    hash_files: bool,
) -> list[dict[str, Any]]:
    """Describe files that define one source bag."""
    rows = []

    for path in sorted(
        item
        for item in bag_path.iterdir()
        if item.is_file()
    ):
        row = {
            "name": path.name,
            "size_bytes": path.stat().st_size,
        }

        if hash_files:
            row["sha256"] = sha256_file(path)

        rows.append(row)

    return rows


def git_value(
    repo_root: Path,
    *arguments: str,
) -> str:
    """Read one Git value without making replay fatal."""
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                *arguments,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except (
        OSError,
        subprocess.CalledProcessError,
    ):
        return ""

    return result.stdout.rstrip("\n")


def count_output_topics(
    bag_path: Path,
) -> dict[str, int]:
    """Count messages written on every output topic."""
    reader = open_reader(bag_path)
    counts: dict[str, int] = {}

    while reader.has_next():
        topic, _serialized, _time_ns = (
            reader.read_next()
        )
        counts[topic] = (
            counts.get(topic, 0) + 1
        )

    return dict(sorted(counts.items()))


def write_replay_metadata(
    output_bag: Path,
    summary: dict[str, Any],
) -> tuple[Path, Path]:
    """Write metadata and its SHA-256 fingerprint."""
    metadata_path = (
        output_bag
        / "tim_replay_metadata.json"
    )
    fingerprint_path = (
        output_bag
        / "tim_replay_metadata.sha256"
    )

    metadata_path.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    metadata_sha256 = sha256_file(
        metadata_path
    )

    fingerprint_path.write_text(
        f"{metadata_sha256}  "
        f"{metadata_path.name}\n",
        encoding="utf-8",
    )

    return metadata_path, fingerprint_path


def write_resolved_runtime(
    output_bag: Path,
    payload: dict[str, Any],
) -> tuple[Path, Path, str]:
    """Write resolved runtime provenance and its SHA-256 fingerprint."""
    runtime_path = (
        output_bag / "tim_mars_resolved_runtime.json"
    )
    fingerprint_path = (
        output_bag / "tim_mars_resolved_runtime.sha256"
    )

    serialized_payload = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    )
    runtime_path.write_text(
        f"{serialized_payload}\n",
        encoding="utf-8",
    )

    runtime_sha256 = sha256_file(
        runtime_path
    )

    fingerprint_path.write_text(
        f"{runtime_sha256}  "
        f"{runtime_path.name}\n",
        encoding="utf-8",
    )

    return (
        runtime_path,
        fingerprint_path,
        runtime_sha256,
    )


def argument_source(
    *option_names: str,
) -> str:
    """Identify whether an optional value came from CLI or its default."""
    arguments = sys.argv[1:]

    for argument in arguments:
        for option_name in option_names:
            if argument == option_name or argument.startswith(
                f"{option_name}="
            ):
                return "command_line"

    return "runner_default"


def build_resolved_runtime_payload(
    *,
    summary: dict[str, Any],
    args: argparse.Namespace,
    appearance_enabled: bool,
    appearance_request_policy: str,
    appearance_compute_min_interval_ms: float,
    image_topic: str,
    input_bag: Path,
    output_bag: Path,
) -> dict[str, Any]:
    """Build exact deterministic replay runtime provenance."""
    return {
        "schema_version": 3,
        "canonical_config": dict(
            summary["canonical_config"]
        ),
        "runtime_overrides": {
            "selected_track_id": int(
                args.selected_track_id
            ),
            "image_width": float(
                args.image_width
            ),
            "image_height": float(
                args.image_height
            ),
            "tracks_are_normalized": bool(
                args.tracks_are_normalized
            ),
            "zero_id_when_not_visible": bool(
                args.zero_id_when_not_visible
            ),
            "appearance_enabled": bool(
                appearance_enabled
            ),
            "appearance_request_policy": str(
                appearance_request_policy
            ),
            "appearance_compute_min_interval_ms": float(
                appearance_compute_min_interval_ms
            ),
            "compact_output": bool(
                args.compact_output
            ),
        },
        "experiment_fields": {
            "raw_target_mode": (
                args.raw_target_mode
            ),
            "image_topic": image_topic,
            "tracks_topic": args.tracks_topic,
            "raw_target_topic": (
                args.raw_target_topic
            ),
            "compact_output": bool(
                args.compact_output
            ),
            "input_bag": str(input_bag),
            "output_bag": str(output_bag),
        },
        "value_sources": {
            "input_bag": (
                "command_line_required"
            ),
            "output_bag": (
                "command_line_required"
            ),
            "selected_track_id": (
                "command_line_required"
            ),
            "image_width": argument_source(
                "--image-width"
            ),
            "image_height": argument_source(
                "--image-height"
            ),
            "tracks_are_normalized": argument_source(
                "--tracks-are-normalized"
            ),
            "zero_id_when_not_visible": argument_source(
                "--zero-id-when-not-visible",
                "--no-zero-id-when-not-visible",
            ),
            "appearance_enabled": (
                "canonical_config"
                if args.appearance_enabled is None
                else "command_line"
            ),
            "appearance_request_policy": (
                "canonical_config"
                if getattr(
                    args,
                    "appearance_request_policy",
                    None,
                ) is None
                else "command_line"
            ),
            "appearance_compute_min_interval_ms": (
                "canonical_config"
                if getattr(
                    args,
                    "appearance_compute_min_interval_ms",
                    None,
                ) is None
                else "command_line"
            ),
            "raw_target_mode": argument_source(
                "--raw-target-mode"
            ),
            "image_topic": (
                "bag_auto_detect"
                if args.image_topic == "auto"
                else "command_line"
            ),
            "tracks_topic": argument_source(
                "--tracks-topic"
            ),
            "raw_target_topic": argument_source(
                "--raw-target-topic"
            ),
            "compact_output": argument_source(
                "--compact-output"
            ),
        },
    }


def main() -> int:
    args = parse_args()

    input_bag = args.input_bag.expanduser().resolve()
    output_bag = args.output_bag.expanduser().resolve()
    args.config = args.config.expanduser().resolve()
    args.model = args.model.expanduser().resolve()

    if not (input_bag / "metadata.yaml").is_file():
        raise RuntimeError(
            f"Input bag is invalid: {input_bag}"
        )

    if not args.config.is_file():
        raise RuntimeError(
            f"Canonical configuration does not exist: {args.config}"
        )

    if output_bag.exists():
        if not args.overwrite:
            raise RuntimeError(
                f"Output bag already exists: {output_bag}"
            )

        shutil.rmtree(output_bag)

    output_bag.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    canonical = load_canonical_parameters(args.config)
    runtime = build_runtime(canonical, args)

    if (
        args.raw_target_mode == "selected_id"
        and int(args.selected_track_id) <= 0
    ):
        raise RuntimeError(
            "selected_id raw-target mode requires "
            "--selected-track-id > 0"
        )

    if args.raw_target_topic in {
        args.tracks_topic,
        TIM_TARGET_TOPIC,
        TIM_STATUS_TOPIC,
    }:
        raise RuntimeError(
            "Raw-target topic must be distinct from "
            "tracks and TIM generated topics"
        )

    reader = open_reader(input_bag)
    metadata_by_topic = topic_metadata_map(reader)

    image_topic = choose_image_topic(
        metadata_by_topic,
        args.image_topic,
    )

    required_topics = {
        image_topic,
        args.tracks_topic,
    }

    missing = required_topics - metadata_by_topic.keys()

    if missing:
        raise RuntimeError(
            "Input bag is missing required topics: "
            + ", ".join(sorted(missing))
        )

    message_types = {
        topic: get_message(metadata.type)
        for topic, metadata in metadata_by_topic.items()
    }

    bridge = CvBridge()
    track_events: list[
        tuple[int, int, int, int, Track2DArray]
    ] = []

    sequence_index = 0
    image_message_count = 0

    while reader.has_next():
        topic, serialized, bag_time_ns = reader.read_next()
        sequence_index += 1

        if topic in {
            TIM_TARGET_TOPIC,
            TIM_STATUS_TOPIC,
        }:
            continue

        if topic == image_topic:
            # Pass 1 deliberately does not decode or retain image pixel
            # data (see the streaming pass below): it only needs to know
            # at least one valid image exists, and must still advance
            # sequence_index identically to before so track_events'
            # tie-break ordering is unchanged.
            message = deserialize_message(
                serialized,
                message_types[topic],
            )
            stamp_ns = image_time_ns(message)

            if stamp_ns <= 0:
                continue

            image_message_count += 1

        elif topic == args.tracks_topic:
            message = deserialize_message(
                serialized,
                Track2DArray,
            )
            semantic_time_ns = track_time_ns(message)

            track_events.append(
                (
                    semantic_time_ns,
                    int(getattr(message, "frame_id", 0)),
                    int(bag_time_ns),
                    sequence_index,
                    message,
                )
            )

    if image_message_count == 0:
        raise RuntimeError(
            f"No valid images found on {image_topic}"
        )

    if not track_events:
        raise RuntimeError(
            f"No track messages found on {args.tracks_topic}"
        )

    track_events.sort(
        key=lambda event: (
            1 if event[0] <= 0 else 0,
            event[0] if event[0] > 0 else 0,
            event[1],
            event[2],
            event[3],
        )
    )

    generated_messages: list[
        tuple[int, int, str, bytes]
    ] = []

    generated_sequence = sequence_index + 1
    generated_semantic_digest = (
        new_generated_semantic_digest()
    )
    replace_raw_target = (
        args.raw_target_mode == "selected_id"
    )
    raw_target_messages_written = 0
    raw_target_valid_messages_written = 0

    def process_one_track_event(
        event: tuple[int, int, int, int, Track2DArray],
    ) -> None:
        nonlocal generated_sequence
        nonlocal raw_target_messages_written
        nonlocal raw_target_valid_messages_written

        (
            _semantic_time_ns,
            _frame_id,
            bag_time_ns,
            _source_sequence,
            tracks_message,
        ) = event

        result = runtime.process_tracks(tracks_message)

        if replace_raw_target:
            raw_target_message = (
                make_fixed_id_raw_target_message(
                    tracks_message=tracks_message,
                    selected_track_id=(
                        args.selected_track_id
                    ),
                )
            )

            update_generated_semantic_digest(
                generated_semantic_digest,
                args.raw_target_topic,
                bag_time_ns,
                raw_target_message,
                raw_target_topic=(
                    args.raw_target_topic
                ),
            )
            generated_messages.append(
                (
                    bag_time_ns,
                    generated_sequence,
                    args.raw_target_topic,
                    bytes(
                        serialize_message(
                            raw_target_message
                        )
                    ),
                )
            )
            generated_sequence += 1
            raw_target_messages_written += 1

            if int(raw_target_message.id) > 0:
                raw_target_valid_messages_written += 1

        target_message = make_target_message(
            runtime=runtime,
            tracks_message=tracks_message,
            result=result,
            zero_id_when_not_visible=(
                args.zero_id_when_not_visible
            ),
        )
        status_message = make_status_message(
            runtime=runtime,
            tracks_message=tracks_message,
            result=result,
        )

        update_generated_semantic_digest(
            generated_semantic_digest,
            TIM_TARGET_TOPIC,
            bag_time_ns,
            target_message,
        )
        update_generated_semantic_digest(
            generated_semantic_digest,
            TIM_STATUS_TOPIC,
            bag_time_ns,
            status_message,
        )

        generated_messages.append(
            (
                bag_time_ns,
                generated_sequence,
                TIM_TARGET_TOPIC,
                bytes(serialize_message(target_message)),
            )
        )
        generated_sequence += 1

        generated_messages.append(
            (
                bag_time_ns,
                generated_sequence,
                TIM_STATUS_TOPIC,
                bytes(serialize_message(status_message)),
            )
        )
        generated_sequence += 1

    # Stream images from a fresh, image-topic-only reader pass, feeding
    # them into the runtime's bounded causal-image buffer (add_image,
    # the same method the live ROS node uses) one at a time instead of
    # decoding the complete timeline into memory up front
    # (replace_images). On the 8 GB RAM / zero-swap development host,
    # preloading every decoded frame for a long, high-resolution external
    # sequence (e.g. 1203 frames at 1920x1080, ~7.1 GB) exhausted memory
    # and crashed the host; see Slice 23.
    #
    # Correctness: track_events is sorted by non-decreasing semantic
    # time, and select_causal_image always returns the single latest
    # image at or before a query time, so the sequence of causally
    # selected images is itself non-decreasing. Adding images in
    # timestamp order and releasing each track event only once every
    # image at or before its semantic time has been added therefore
    # produces results identical to preloading the complete timeline,
    # without ever needing to hold more than the buffer's worth of
    # decoded images at once.
    image_reader = open_reader(input_bag)
    image_reader.set_filter(
        rosbag2_py.StorageFilter(topics=[image_topic])
    )

    pending_index = 0
    images_loaded = 0

    while image_reader.has_next():
        _topic, serialized, _bag_time_ns = (
            image_reader.read_next()
        )
        message = deserialize_message(
            serialized,
            message_types[image_topic],
        )
        stamp_ns = image_time_ns(message)

        if stamp_ns <= 0:
            continue

        image_bgr = bridge.imgmsg_to_cv2(
            message,
            desired_encoding="bgr8",
        )
        runtime.add_image(stamp_ns, image_bgr)
        images_loaded += 1
        del image_bgr
        del message

        while (
            pending_index < len(track_events)
            and track_events[pending_index][0] <= stamp_ns
        ):
            process_one_track_event(
                track_events[pending_index]
            )
            pending_index += 1

    del image_reader

    # Any remaining track events (semantic time after the last image, or
    # a non-positive/unavailable semantic time, sorted first) are
    # processed against whatever is currently the latest buffered image,
    # exactly as select_causal_image would resolve them against the
    # complete preloaded timeline.
    while pending_index < len(track_events):
        process_one_track_event(track_events[pending_index])
        pending_index += 1

    writer = rosbag2_py.SequentialWriter()
    writer.open(
        rosbag2_py.StorageOptions(
            uri=str(output_bag),
            storage_id="mcap",
        ),
        rosbag2_py.ConverterOptions(
            input_serialization_format="cdr",
            output_serialization_format="cdr",
        ),
    )

    skipped_source_topics = (
        skipped_source_topics_for_output(
            set(metadata_by_topic),
            tracks_topic=args.tracks_topic,
            raw_target_topic=args.raw_target_topic,
            replace_raw_target=replace_raw_target,
            compact_output=bool(args.compact_output),
        )
    )

    for metadata in metadata_by_topic.values():
        if (
            metadata.name
            in {
                TIM_TARGET_TOPIC,
                TIM_STATUS_TOPIC,
            }
            or metadata.name
            in skipped_source_topics
        ):
            continue

        writer.create_topic(
            copy_topic_metadata(metadata)
        )

    writer.create_topic(
        generated_topic_metadata(
            name=TIM_TARGET_TOPIC,
            message_type="thesis_msgs/msg/TargetState",
        )
    )
    writer.create_topic(
        generated_topic_metadata(
            name=TIM_STATUS_TOPIC,
            message_type="std_msgs/msg/String",
        )
    )

    if replace_raw_target:
        writer.create_topic(
            generated_topic_metadata(
                name=args.raw_target_topic,
                message_type=(
                    "thesis_msgs/msg/TargetState"
                ),
            )
        )

    source_reader = open_reader(input_bag)
    source_messages_written = write_streamed_output(
        writer=writer,
        source_reader=source_reader,
        generated_messages=generated_messages,
        skipped_source_topics=(
            skipped_source_topics
        ),
    )

    writer.close()

    repo_root = (
        Path(__file__).resolve().parents[2]
    )
    repository_status = git_value(
        repo_root,
        "status",
        "--short",
    ).splitlines()

    config_copy = (
        output_bag
        / "tim_mars_canonical_config.yaml"
    )
    shutil.copy2(
        args.config,
        config_copy,
    )

    output_topic_counts = (
        count_output_topics(output_bag)
    )

    expected_generated_count = len(track_events)

    for topic in (
        TIM_TARGET_TOPIC,
        TIM_STATUS_TOPIC,
    ):
        if (
            output_topic_counts.get(topic, 0)
            != expected_generated_count
        ):
            raise RuntimeError(
                "Output generated-topic count mismatch "
                f"for {topic}"
            )

    if (
        replace_raw_target
        and output_topic_counts.get(
            args.raw_target_topic,
            0,
        )
        != expected_generated_count
    ):
        raise RuntimeError(
            "Output fixed-ID raw-target count does not "
            "match processed track count"
        )

    summary = {
        "schema_version": 2,
        "created_at_utc": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
        "repository": {
            "root": str(repo_root),
            "branch": git_value(
                repo_root,
                "branch",
                "--show-current",
            ),
            "commit": git_value(
                repo_root,
                "rev-parse",
                "HEAD",
            ),
            "status_short": repository_status,
        },
        "command": " ".join(sys.argv),
        "input_bag": str(input_bag),
        "output_bag": str(output_bag),
        "source_manifest": source_manifest(
            input_bag,
            hash_files=(
                not args.skip_source_hash
            ),
        ),
        "canonical_config": {
            "source": str(args.config),
            "copy": config_copy.name,
            "sha256": sha256_file(
                config_copy
            ),
        },
        "model": {
            "source": str(args.model),
            "size_bytes": (
                args.model.stat().st_size
            ),
            "sha256": sha256_file(
                args.model
            ),
        },
        "runtime": {
            "selected_track_id": int(
                args.selected_track_id
            ),
            "image_width": float(
                args.image_width
            ),
            "image_height": float(
                args.image_height
            ),
            "tracks_are_normalized": bool(
                args.tracks_are_normalized
            ),
            "zero_id_when_not_visible": bool(
                args.zero_id_when_not_visible
            ),
            "appearance_enabled": bool(
                runtime.config.appearance.enabled
            ),
            "appearance_request_policy": str(
                runtime.config.appearance_request_policy.value
                if isinstance(
                    runtime.config.appearance_request_policy,
                    AppearanceRequestPolicy,
                )
                else runtime.config.appearance_request_policy
            ),
            "appearance_compute_min_interval_ms": float(
                runtime.config.appearance.compute_min_interval_ms
            ),
            "raw_target_mode": (
                args.raw_target_mode
            ),
            "compact_output": bool(
                args.compact_output
            ),
        },
        "topics": {
            "image": image_topic,
            "tracks": args.tracks_topic,
            "raw_target": (
                args.raw_target_topic
            ),
            "tim_target": TIM_TARGET_TOPIC,
            "tim_status": TIM_STATUS_TOPIC,
            "raw_target_source": (
                "generated_fixed_selected_id"
                if replace_raw_target
                else "source_copy"
            ),
            "source_topics_retained": sorted(
                set(metadata_by_topic)
                - skipped_source_topics
                - {
                    TIM_TARGET_TOPIC,
                    TIM_STATUS_TOPIC,
                }
            ),
            "source_topics_omitted": sorted(
                skipped_source_topics
                - {
                    TIM_TARGET_TOPIC,
                    TIM_STATUS_TOPIC,
                }
            ),
        },
        "raw_target_generation": {
            "mode": args.raw_target_mode,
            "selected_track_id": (
                int(args.selected_track_id)
                if replace_raw_target
                else None
            ),
            "source_topic_replaced": (
                replace_raw_target
            ),
            "fixed_after_initialization": (
                True if replace_raw_target else None
            ),
            "reselection_enabled": (
                False if replace_raw_target else None
            ),
        },
        "counts": {
            "images_loaded": images_loaded,
            "source_messages_streamed": (
                source_messages_written
            ),
            "track_messages_processed": (
                len(track_events)
            ),
            "tim_target_messages_written": (
                len(track_events)
            ),
            "tim_status_messages_written": (
                len(track_events)
            ),
            "raw_target_messages_written": (
                raw_target_messages_written
            ),
            "raw_target_valid_messages_written": (
                raw_target_valid_messages_written
            ),
            "output_topic_counts": (
                output_topic_counts
            ),
        },
        "processing_contract": {
            "algorithm_processing_order": [
                "trustworthy_track_timestamp",
                "frame_id",
                "original_bag_timestamp",
                "original_sequence_index",
            ],
            "bag_write_order": [
                "original_bag_timestamp",
                "original_source_order",
                (
                    "generated_raw_target_then_"
                    "tim_target_then_status"
                    if replace_raw_target
                    else
                    "generated_tim_target_then_status"
                ),
            ],
            "source_copy_mode": (
                "streamed_compact_second_pass"
                if args.compact_output
                else "streamed_second_pass"
            ),
            "complete_image_timeline_preloaded": (
                True
            ),
        },
        "determinism": {
            "semantic_digest_schema": (
                SEMANTIC_DIGEST_SCHEMA
            ),
            "generated_semantic_sha256": (
                generated_semantic_digest.hexdigest()
            ),
            "raw_cdr_payload_bytes_are_contract": (
                False
            ),
            "raw_mcap_file_bytes_are_contract": (
                False
            ),
            "reason": (
                "ROS CDR payloads may contain "
                "non-semantic alignment-padding "
                "bytes; determinism is defined "
                "over declared generated message "
                "fields and write order."
            ),
        },
        "metadata_artifacts": {
            "metadata_file": (
                "tim_replay_metadata.json"
            ),
            "fingerprint_file": (
                "tim_replay_metadata.sha256"
            ),
        },
    }

    resolved_runtime_payload = (
        build_resolved_runtime_payload(
            summary=summary,
            args=args,
            appearance_enabled=bool(
                runtime.config.appearance.enabled
            ),
            appearance_request_policy=str(
                runtime.config.appearance_request_policy.value
                if isinstance(
                    runtime.config.appearance_request_policy,
                    AppearanceRequestPolicy,
                )
                else runtime.config.appearance_request_policy
            ),
            appearance_compute_min_interval_ms=float(
                runtime.config.appearance.compute_min_interval_ms
            ),
            image_topic=image_topic,
            input_bag=input_bag,
            output_bag=output_bag,
        )
    )

    (
        resolved_runtime_path,
        resolved_runtime_fingerprint_path,
        resolved_runtime_sha256,
    ) = write_resolved_runtime(
        output_bag,
        resolved_runtime_payload,
    )

    summary["schema_version"] = 3
    summary["resolved_runtime"] = {
        "file": resolved_runtime_path.name,
        "fingerprint_file": (
            resolved_runtime_fingerprint_path.name
        ),
        "sha256": resolved_runtime_sha256,
    }
    summary["metadata_artifacts"].update(
        {
            "resolved_runtime_file": (
                resolved_runtime_path.name
            ),
            "resolved_runtime_fingerprint_file": (
                resolved_runtime_fingerprint_path.name
            ),
        }
    )

    write_replay_metadata(
        output_bag,
        summary,
    )

    print(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
