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
import json
import shutil
from dataclasses import fields
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
        "--overwrite",
        action="store_true",
        help="Remove an existing output bag before writing.",
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


def open_reader(bag_path: Path) -> rosbag2_py.SequentialReader:
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
        compute_min_interval_ms=float(
            canonical.get(
                "appearance_compute_min_interval_ms",
                250.0,
            )
        ),
        cache_ttl_ms=float(
            canonical.get(
                "appearance_cache_ttl_ms",
                750.0,
            )
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


def make_status_message(
    *,
    runtime: TimMarsRuntime,
    tracks_message: Track2DArray,
    result: Any,
    canonical: dict[str, Any],
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
            canonical.get(
                "appearance_compute_min_interval_ms",
                250.0,
            )
        ),
        appearance_cache_ttl_ms=float(
            canonical.get(
                "appearance_cache_ttl_ms",
                750.0,
            )
        ),
        appearance_cache_size=(
            diagnostics.appearance_cache_size
        ),
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
) -> int:
    """Stream source messages and merge generated messages by bag timestamp.

    Source messages retain their original order. At a shared bag timestamp,
    every original source message is written before deterministic TIM output,
    matching the previous full-list ordering without retaining the source bag
    in memory.
    """

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

        if topic in {
            TIM_TARGET_TOPIC,
            TIM_STATUS_TOPIC,
        }:
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
    images: list[tuple[int, Any]] = []
    track_events: list[
        tuple[int, int, int, int, Track2DArray]
    ] = []

    sequence_index = 0

    while reader.has_next():
        topic, serialized, bag_time_ns = reader.read_next()
        sequence_index += 1

        if topic in {
            TIM_TARGET_TOPIC,
            TIM_STATUS_TOPIC,
        }:
            continue

        if topic == image_topic:
            message = deserialize_message(
                serialized,
                message_types[topic],
            )
            stamp_ns = image_time_ns(message)

            if stamp_ns <= 0:
                continue

            image_bgr = bridge.imgmsg_to_cv2(
                message,
                desired_encoding="bgr8",
            )
            images.append((stamp_ns, image_bgr))

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

    if not images:
        raise RuntimeError(
            f"No valid images found on {image_topic}"
        )

    if not track_events:
        raise RuntimeError(
            f"No track messages found on {args.tracks_topic}"
        )

    runtime.replace_images(images)

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

    for (
        _semantic_time_ns,
        _frame_id,
        bag_time_ns,
        _source_sequence,
        tracks_message,
    ) in track_events:
        result = runtime.process_tracks(tracks_message)

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
            canonical=canonical,
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

    for metadata in metadata_by_topic.values():
        if metadata.name in {
            TIM_TARGET_TOPIC,
            TIM_STATUS_TOPIC,
        }:
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

    source_reader = open_reader(input_bag)
    source_messages_written = write_streamed_output(
        writer=writer,
        source_reader=source_reader,
        generated_messages=generated_messages,
    )

    writer.close()

    summary = {
        "input_bag": str(input_bag),
        "output_bag": str(output_bag),
        "image_topic": image_topic,
        "images_loaded": len(images),
        "source_messages_streamed": source_messages_written,
        "track_messages_processed": len(track_events),
        "tim_target_messages_written": len(track_events),
        "tim_status_messages_written": len(track_events),
        "selected_track_id": int(args.selected_track_id),
        "appearance_enabled": bool(
            runtime.config.appearance.enabled
        ),
        "algorithm_processing_order": [
            "trustworthy_track_timestamp",
            "frame_id",
            "original_bag_timestamp",
            "original_sequence_index",
        ],
        "bag_write_order": [
            "original_bag_timestamp",
            "original_source_order",
            "generated_target_then_status",
        ],
        "source_copy_mode": "streamed_second_pass",
    }

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
