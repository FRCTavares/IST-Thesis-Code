#!/usr/bin/env python3
"""Deterministic ROS-bag replay for the Issue #58 Target-ReID baseline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import rosbag2_py
from cv_bridge import CvBridge
from rclpy.serialization import deserialize_message, serialize_message
from thesis_msgs.msg import TargetState, Track2DArray

SCRIPT_DIR = Path(__file__).resolve().parent
ANALYSIS_DIR = SCRIPT_DIR.parent / "analysis"

for path in (SCRIPT_DIR, ANALYSIS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_deterministic_tim_replay as replay_utils  # noqa: E402
from p058_target_reid_runtime import TargetReIdRuntime  # noqa: E402


TARGET_REID_TOPIC = "/target_reid"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Replay the simple Issue #58 fixed-anchor Target-ReID baseline."
        )
    )
    parser.add_argument("input_bag", type=Path)
    parser.add_argument("output_bag", type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--selected-track-id", required=True, type=int)
    parser.add_argument("--threshold", required=True, type=float)
    parser.add_argument("--image-width", required=True, type=float)
    parser.add_argument("--image-height", required=True, type=float)
    parser.add_argument(
        "--tracks-normalized",
        action="store_true",
        help="Interpret Track2D cx/cy/w/h as normalized coordinates.",
    )
    parser.add_argument("--image-topic", default="auto")
    parser.add_argument("--tracks-topic", default="/tracks")
    parser.add_argument("--max-image-age-ms", type=float, default=250.0)
    return parser.parse_args()


def make_target_message(
    tracks_message: Track2DArray,
    result: Any,
) -> TargetState:
    """Convert one Target-ReID decision into controller-facing TargetState."""
    target = TargetState()
    target.header = tracks_message.header
    target.frame_id = int(getattr(tracks_message, "frame_id", 0))
    target.src_stamp_ns = int(
        getattr(tracks_message, "src_stamp_ns", 0)
    )
    target.t_cam_msg_seen_ns = int(
        getattr(tracks_message, "t_cam_msg_seen_ns", 0)
    )
    target.t_target_cb_start_ns = 0
    target.t_target_cb_end_ns = 0

    decision = result.decision

    if not decision.published or decision.selected_candidate is None:
        return target

    selected_id = int(decision.selected_candidate.track_id)

    selected_track = next(
        (
            track
            for track in tracks_message.tracks
            if int(getattr(track, "id", 0)) == selected_id
        ),
        None,
    )

    if selected_track is None:
        return target

    target.id = selected_id
    target.cx = float(selected_track.cx)
    target.cy = float(selected_track.cy)
    target.w = float(selected_track.w)
    target.h = float(selected_track.h)

    similarity = (
        float(decision.similarity)
        if decision.similarity is not None
        else 0.0
    )
    target.score = similarity
    target.quality = similarity
    return target


def main() -> None:
    args = parse_args()

    if args.output_bag.exists():
        raise RuntimeError(
            f"Output bag already exists: {args.output_bag}"
        )

    reader = replay_utils.open_reader(args.input_bag)
    metadata = replay_utils.topic_metadata_map(reader)

    if args.tracks_topic not in metadata:
        raise RuntimeError(
            f"Tracks topic not found: {args.tracks_topic}"
        )

    image_topic = replay_utils.choose_image_topic(
        metadata,
        args.image_topic,
    )

    track_events: list[
        tuple[int, int, int, int, Track2DArray]
    ] = []

    sequence_index = 0
    image_message_count = 0

    while reader.has_next():
        topic, serialized, bag_time_ns = reader.read_next()
        sequence_index += 1

        if topic == image_topic:
            image_message_count += 1
            continue

        if topic != args.tracks_topic:
            continue

        message = deserialize_message(
            serialized,
            Track2DArray,
        )
        semantic_time_ns = replay_utils.track_time_ns(message)

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
            f"No image messages found on {image_topic}"
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

    runtime = TargetReIdRuntime(
        model_path=str(args.model),
        selected_track_id=args.selected_track_id,
        threshold=args.threshold,
        image_width=args.image_width,
        image_height=args.image_height,
        tracks_are_normalized=args.tracks_normalized,
        max_image_age_ms=args.max_image_age_ms,
    )

    bridge = CvBridge()

    generated: list[tuple[int, int, bytes]] = []
    generated_sequence = 0

    anchor_bootstrap_frame_id: int | None = None
    valid_publications = 0

    def process_event(
        event: tuple[int, int, int, int, Track2DArray],
    ) -> None:
        nonlocal generated_sequence
        nonlocal anchor_bootstrap_frame_id
        nonlocal valid_publications

        (
            _semantic_time_ns,
            frame_id,
            bag_time_ns,
            _source_sequence,
            tracks_message,
        ) = event

        anchor_before = runtime.anchor_ready
        result = runtime.process_tracks(tracks_message)

        if (
            not anchor_before
            and result.anchor_ready
            and anchor_bootstrap_frame_id is None
        ):
            anchor_bootstrap_frame_id = int(frame_id)

        target = make_target_message(
            tracks_message,
            result,
        )

        if int(target.id) > 0:
            valid_publications += 1

        generated.append(
            (
                int(bag_time_ns),
                generated_sequence,
                bytes(serialize_message(target)),
            )
        )
        generated_sequence += 1

    image_reader = replay_utils.open_reader(args.input_bag)
    image_reader.set_filter(
        rosbag2_py.StorageFilter(
            topics=[image_topic]
        )
    )

    pending_index = 0

    while image_reader.has_next():
        _topic, serialized, _bag_time_ns = image_reader.read_next()

        image_type = replay_utils.get_message(
            metadata[image_topic].type
        )
        image_message = deserialize_message(
            serialized,
            image_type,
        )

        stamp_ns = replay_utils.image_time_ns(image_message)

        if stamp_ns <= 0:
            continue

        image_bgr = bridge.imgmsg_to_cv2(
            image_message,
            desired_encoding="bgr8",
        )
        runtime.add_image(stamp_ns, image_bgr)

        while (
            pending_index < len(track_events)
            and track_events[pending_index][0] > 0
            and track_events[pending_index][0] <= stamp_ns
        ):
            process_event(track_events[pending_index])
            pending_index += 1

    while pending_index < len(track_events):
        process_event(track_events[pending_index])
        pending_index += 1

    generated.sort(
        key=lambda item: (
            item[0],
            item[1],
        )
    )

    writer = rosbag2_py.SequentialWriter()
    writer.open(
        rosbag2_py.StorageOptions(
            uri=str(args.output_bag),
            storage_id="mcap",
        ),
        rosbag2_py.ConverterOptions(
            input_serialization_format="cdr",
            output_serialization_format="cdr",
        ),
    )

    writer.create_topic(
        replay_utils.generated_topic_metadata(
            name=TARGET_REID_TOPIC,
            message_type="thesis_msgs/msg/TargetState",
        )
    )

    for bag_time_ns, _sequence, serialized in generated:
        writer.write(
            TARGET_REID_TOPIC,
            serialized,
            bag_time_ns,
        )

    del writer

    counts = replay_utils.count_output_topics(
        args.output_bag
    )

    if counts.get(TARGET_REID_TOPIC, 0) != len(track_events):
        raise RuntimeError(
            "Generated Target-ReID message count does not "
            "match processed track-message count"
        )

    summary = {
        "schema": "p058_target_reid_replay_v1",
        "input_bag": str(args.input_bag.resolve()),
        "output_bag": str(args.output_bag.resolve()),
        "image_topic": image_topic,
        "tracks_topic": args.tracks_topic,
        "target_topic": TARGET_REID_TOPIC,
        "model": str(args.model.resolve()),
        "selected_track_id": int(args.selected_track_id),
        "threshold": float(args.threshold),
        "image_width": float(args.image_width),
        "image_height": float(args.image_height),
        "tracks_normalized": bool(args.tracks_normalized),
        "max_image_age_ms": float(args.max_image_age_ms),
        "track_messages": len(track_events),
        "target_messages": counts.get(TARGET_REID_TOPIC, 0),
        "valid_publications": valid_publications,
        "anchor_bootstrap_frame_id": anchor_bootstrap_frame_id,
    }

    summary_path = Path(
        f"{args.output_bag}.p058_target_reid.json"
    )
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
