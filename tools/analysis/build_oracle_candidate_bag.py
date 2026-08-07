#!/usr/bin/env python3
"""Build an oracle-candidate bag: real images + ground-truth-derived tracks.

Oracle-candidate mode (Issue #30) replaces the detector and tracker with an
idealized candidate stream built directly from official ground-truth boxes,
to evaluate TIM-MARS identity-memory and recovery behaviour independently of
detector/tracker failures.

The physical identity is never exposed to TIM-MARS as a shortcut: every
physical person (target and distractors alike) gets a synthetic oracle
tracker ID, assigned by a global incrementing counter in frame order, not
derived from or equal to the dataset identity. A new oracle ID is assigned
whenever a physical identity's annotated visibility has a gap (a frame index
discontinuity) -- i.e. the ground truth itself records the person as absent
and later present again -- so genuine re-entry/occlusion recovery in the
source data is preserved as controlled candidate-identity fragmentation
without inventing synthetic detector or tracker failure. TIM-MARS must still
discover which oracle ID is the frozen physical target the same way it would
a real tracker's ID: via the existing blind IoU/margin/confirmation
initialization rule, not by direct identity disclosure.

Real images are included (not just boxes) because the canonical TIM-MARS
configuration has appearance matching enabled, and Issue #30 forbids
changing that policy for this evaluation.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ANALYSIS_DIR = Path(__file__).resolve().parent
EXPERIMENTS_DIR = ANALYSIS_DIR.parent / "experiments"
sys.path.insert(0, str(ANALYSIS_DIR))
sys.path.insert(0, str(EXPERIMENTS_DIR))

from external_tracking_dataset import (  # noqa: E402
    ExternalObjectAnnotation,
    SequenceGeometry,
    parse_dancetrack_annotations,
    parse_visdrone_annotations,
)


def assign_oracle_ids(
    annotations: list[ExternalObjectAnnotation],
) -> dict[tuple, int]:
    """Map (dataset_identity, normalized_frame_index) -> oracle tracker ID.

    A new oracle ID starts whenever a physical identity's sorted frame
    indices are not consecutive with the previous one for that identity.
    IDs are assigned by a single global counter in ascending
    (first_frame, dataset_identity) discovery order, so oracle ID values
    carry no information about dataset identity ordering.
    """

    by_identity: dict[Any, list[int]] = {}
    for row in annotations:
        if not row.include_as_person_candidate:
            continue
        by_identity.setdefault(row.identity, []).append(
            row.normalized_frame_index
        )

    segments: list[tuple[int, Any, int, int]] = []

    for identity, frames in by_identity.items():
        frames = sorted(set(frames))
        segment_start = frames[0]
        previous = frames[0]

        for frame in frames[1:]:
            if frame != previous + 1:
                segments.append(
                    (segment_start, identity, segment_start, previous)
                )
                segment_start = frame
            previous = frame

        segments.append((segment_start, identity, segment_start, previous))

    segments.sort(key=lambda item: (item[0], item[1]))

    mapping: dict[tuple, int] = {}
    for index, (_, identity, start, end) in enumerate(segments, start=1):
        for frame in range(start, end + 1):
            mapping[(identity, frame)] = index

    return mapping


def load_annotations(
    *,
    dataset: str,
    annotation_path: Path,
    sequence_name: str,
    split: str,
    geometry: SequenceGeometry,
) -> list[ExternalObjectAnnotation]:
    if dataset == "dancetrack":
        return parse_dancetrack_annotations(
            annotation_path,
            sequence_name=sequence_name,
            split=split,
            geometry=geometry,
        )
    if dataset == "visdrone_mot":
        return parse_visdrone_annotations(
            annotation_path,
            sequence_name=sequence_name,
            split=split,
            geometry=geometry,
        )
    raise ValueError(f"unsupported dataset: {dataset}")


def build_oracle_bag(
    *,
    dataset: str,
    annotation_path: Path,
    sequence_name: str,
    split: str,
    image_dir: Path,
    geometry: SequenceGeometry,
    output_bag: Path,
    start_time_ns: int = 0,
) -> dict[str, Any]:
    import cv2
    import rosbag2_py
    from cv_bridge import CvBridge
    from rclpy.serialization import serialize_message
    from rclpy.time import Time as RclpyTime
    from thesis_msgs.msg import Track2D, Track2DArray

    from images_to_camera_bag import discover_images, frame_timestamps_ns

    annotations = load_annotations(
        dataset=dataset,
        annotation_path=annotation_path,
        sequence_name=sequence_name,
        split=split,
        geometry=geometry,
    )
    oracle_ids = assign_oracle_ids(annotations)

    by_frame: dict[int, list[ExternalObjectAnnotation]] = {}
    for row in annotations:
        if not row.include_as_person_candidate:
            continue
        by_frame.setdefault(row.normalized_frame_index, []).append(row)

    image_paths = discover_images(image_dir)
    timestamps_ns = frame_timestamps_ns(
        len(image_paths),
        frame_rate_hz=geometry.frame_rate,
        start_time_ns=start_time_ns,
    )

    bridge = CvBridge()

    writer = rosbag2_py.SequentialWriter()
    writer.open(
        rosbag2_py.StorageOptions(
            uri=str(output_bag), storage_id="mcap"
        ),
        rosbag2_py.ConverterOptions(
            input_serialization_format="cdr",
            output_serialization_format="cdr",
        ),
    )
    writer.create_topic(
        rosbag2_py.TopicMetadata(
            id=0,
            name="/camera/image_raw",
            type="sensor_msgs/msg/Image",
            serialization_format="cdr",
        )
    )
    writer.create_topic(
        rosbag2_py.TopicMetadata(
            id=1,
            name="/tracks",
            type="thesis_msgs/msg/Track2DArray",
            serialization_format="cdr",
        )
    )

    images_written = 0
    track_messages_written = 0
    total_oracle_boxes = 0

    for frame_index, (path, stamp_ns) in enumerate(
        zip(image_paths, timestamps_ns)
    ):
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            continue

        ros_time = RclpyTime(nanoseconds=stamp_ns).to_msg()

        image_message = bridge.cv2_to_imgmsg(image, encoding="bgr8")
        image_message.header.stamp = ros_time
        image_message.header.frame_id = "camera"
        writer.write(
            "/camera/image_raw",
            serialize_message(image_message),
            stamp_ns,
        )
        images_written += 1

        tracks_message = Track2DArray()
        tracks_message.header.stamp = ros_time
        tracks_message.frame_id = frame_index
        tracks_message.src_stamp_ns = stamp_ns

        for row in by_frame.get(frame_index, []):
            oracle_id = oracle_ids[(row.identity, frame_index)]
            track = Track2D()
            track.id = oracle_id
            track.cx = (row.bbox_xyxy[0] + row.bbox_xyxy[2]) / 2.0
            track.cy = (row.bbox_xyxy[1] + row.bbox_xyxy[3]) / 2.0
            track.w = row.bbox_xyxy[2] - row.bbox_xyxy[0]
            track.h = row.bbox_xyxy[3] - row.bbox_xyxy[1]
            track.score = 1.0
            track.label = "person"
            tracks_message.tracks.append(track)
            total_oracle_boxes += 1

        writer.write(
            "/tracks",
            serialize_message(tracks_message),
            stamp_ns,
        )
        track_messages_written += 1

    del writer

    return {
        "output_bag": str(output_bag),
        "images_written": images_written,
        "track_messages_written": track_messages_written,
        "total_oracle_boxes": total_oracle_boxes,
        "distinct_oracle_ids": len(set(oracle_ids.values())),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--annotation-path", type=Path, required=True)
    parser.add_argument("--sequence-name", required=True)
    parser.add_argument("--split", required=True)
    parser.add_argument("--image-dir", type=Path, required=True)
    parser.add_argument("--image-width", type=int, required=True)
    parser.add_argument("--image-height", type=int, required=True)
    parser.add_argument("--frame-rate", type=float, required=True)
    parser.add_argument("--source-index-base", type=int, default=1)
    parser.add_argument("--output-bag", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    arguments = parser.parse_args()

    if arguments.output_bag.exists():
        if not arguments.overwrite:
            raise SystemExit(
                f"output bag exists: {arguments.output_bag}"
            )
        import shutil

        shutil.rmtree(arguments.output_bag)

    geometry = SequenceGeometry(
        image_width=arguments.image_width,
        image_height=arguments.image_height,
        frame_rate=arguments.frame_rate,
        source_index_base=arguments.source_index_base,
    )

    result = build_oracle_bag(
        dataset=arguments.dataset,
        annotation_path=arguments.annotation_path,
        sequence_name=arguments.sequence_name,
        split=arguments.split,
        image_dir=arguments.image_dir,
        geometry=geometry,
        output_bag=arguments.output_bag,
    )

    import json

    print(json.dumps(result, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
