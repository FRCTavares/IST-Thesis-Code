#!/usr/bin/env python3
"""Resolve the frozen tracker identity for one captured external sequence.

Reads a manifest sequence entry (already frozen by Slice 14/16), reads the
recorded /tracks stream from that sequence's live-captured candidate bag
(tools/experiments/capture_external_detector_tracker.sh output), reads the
sequence's own official ground-truth annotation for the frozen
target.dataset_identity across the frozen initialization window, and applies
tools/analysis/external_target_initialization.py's IoU/margin/confirmation
rule -- the same rule already recorded in the manifest entry -- to resolve
target.initial_tracker_identity.

This does not change which sequence, physical identity or initialization
window was selected. It mechanically resolves which live tracker ID that
already-frozen physical identity corresponds to in this specific capture,
exactly as Issue #30 describes for the (deliberately left null at freeze
time) initial_tracker_identity field.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = ROOT / "tools" / "analysis"
sys.path.insert(0, str(ANALYSIS_DIR))

from external_target_initialization import (  # noqa: E402
    InitializationConfig,
    PhysicalTargetObservation,
    TrackerCandidateObservation,
    initialize_frozen_target,
)
from external_tracking_dataset import (  # noqa: E402
    SequenceGeometry,
    parse_dancetrack_annotations,
    parse_visdrone_annotations,
)


DEFAULT_MANIFEST = (
    ROOT / "docs" / "data" / "external_benchmark" / "sequence_manifest.json"
)


def is_compressed_bag(bag_path: Path) -> bool:
    """Detect file-level bag compression from metadata.yaml.

    Plain ``rosbag2_py.SequentialReader`` cannot open a compressed mcap file
    directly (it fails with an "invalid magic bytes" error trying to parse
    compressed bytes as an uncompressed mcap stream); a compressed bag needs
    ``SequentialCompressionReader`` instead. The CLI tools (``ros2 bag
    play``/``info``) handle this transparently; the raw Python bindings do
    not, so every reader in this evaluation pipeline must check explicitly.
    """

    metadata_path = Path(bag_path) / "metadata.yaml"

    if not metadata_path.is_file():
        return False

    text = metadata_path.read_text(encoding="utf-8", errors="ignore")

    return (
        "compression_mode: FILE" in text
        or "compression_mode: MESSAGE" in text
    )


def open_bag_reader(bag_path: Path):
    """Open ``bag_path`` with the reader class its compression needs."""

    import rosbag2_py

    reader = (
        rosbag2_py.SequentialCompressionReader()
        if is_compressed_bag(bag_path)
        else rosbag2_py.SequentialReader()
    )
    reader.open(
        rosbag2_py.StorageOptions(uri=str(bag_path), storage_id="mcap"),
        rosbag2_py.ConverterOptions(
            input_serialization_format="cdr",
            output_serialization_format="cdr",
        ),
    )
    return reader


def load_manifest_entry(
    manifest_path: Path, *, sequence_id: str
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    for entry in manifest["sequences"]:
        if entry["id"] == sequence_id:
            return entry

    raise ValueError(f"sequence id not found in manifest: {sequence_id}")


def annotation_path_for(entry: dict[str, Any]) -> Path:
    dataset = entry["dataset"]
    split = entry["split"]
    sequence_name = entry["sequence_name"]

    if dataset == "dancetrack":
        return (
            ROOT
            / "data"
            / "datasets"
            / "external"
            / "dancetrack"
            / split
            / sequence_name
            / "gt"
            / "gt.txt"
        )

    if dataset == "visdrone_mot":
        return (
            ROOT
            / "data"
            / "datasets"
            / "external"
            / "visdrone_mot"
            / split
            / "annotations"
            / f"{sequence_name}.txt"
        )

    raise ValueError(f"unsupported dataset for annotation lookup: {dataset}")


def load_target_observations(
    entry: dict[str, Any],
) -> list[PhysicalTargetObservation]:
    geometry = SequenceGeometry(
        image_width=entry["image"]["width"],
        image_height=entry["image"]["height"],
        frame_rate=entry["frame_contract"]["frame_rate"],
        source_index_base=entry["frame_contract"]["source_index_base"],
    )

    path = annotation_path_for(entry)
    dataset = entry["dataset"]

    if dataset == "dancetrack":
        rows = parse_dancetrack_annotations(
            path,
            sequence_name=entry["sequence_name"],
            split=entry["split"],
            geometry=geometry,
        )
    else:
        rows = parse_visdrone_annotations(
            path,
            sequence_name=entry["sequence_name"],
            split=entry["split"],
            geometry=geometry,
        )

    dataset_identity = entry["target"]["dataset_identity"]
    start = entry["target"]["initialization_start_frame"]
    end = entry["target"]["initialization_end_frame_inclusive"]

    return [
        PhysicalTargetObservation(
            normalized_frame_index=row.normalized_frame_index,
            dataset_identity=row.identity,
            bbox_xyxy=row.bbox_xyxy,
        )
        for row in rows
        if row.identity == dataset_identity
        and start <= row.normalized_frame_index <= end
        and row.include_as_person_candidate
    ]


def load_tracker_candidates(
    capture_bag: Path,
    *,
    frame_rate_hz: float,
    start_time_ns: int = 0,
    tracks_topic: str = "/tracks",
) -> list[TrackerCandidateObservation]:
    import rosbag2_py
    from rclpy.serialization import deserialize_message
    from thesis_msgs.msg import Track2DArray

    period_ns = round(1_000_000_000 / frame_rate_hz)

    reader = open_bag_reader(capture_bag)
    reader.set_filter(
        rosbag2_py.StorageFilter(topics=[tracks_topic])
    )

    observations: list[TrackerCandidateObservation] = []

    while reader.has_next():
        topic, data, _bag_timestamp_ns = reader.read_next()
        message = deserialize_message(data, Track2DArray)

        source_stamp_ns = int(message.src_stamp_ns)
        normalized_frame_index = round(
            (source_stamp_ns - start_time_ns) / period_ns
        )

        for track in message.tracks:
            half_w = track.w / 2.0
            half_h = track.h / 2.0
            bbox_xyxy = (
                track.cx - half_w,
                track.cy - half_h,
                track.cx + half_w,
                track.cy + half_h,
            )
            observations.append(
                TrackerCandidateObservation(
                    normalized_frame_index=normalized_frame_index,
                    tracker_identity=int(track.id),
                    bbox_xyxy=bbox_xyxy,
                    score=float(track.score),
                )
            )

    return observations


def resolve(
    *,
    sequence_id: str,
    capture_bag: Path,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict[str, Any]:
    entry = load_manifest_entry(manifest_path, sequence_id=sequence_id)
    target = entry["target"]

    target_observations = load_target_observations(entry)
    tracker_candidates = load_tracker_candidates(
        capture_bag,
        frame_rate_hz=entry["frame_contract"]["frame_rate"],
    )

    config = InitializationConfig(
        start_frame_index=target["initialization_start_frame"],
        end_frame_index_inclusive=target[
            "initialization_end_frame_inclusive"
        ],
        minimum_iou=target["minimum_match_iou"],
        minimum_margin=target["minimum_match_margin"],
        confirmation_frames=target["confirmation_frames"],
    )

    result = initialize_frozen_target(
        dataset_identity=target["dataset_identity"],
        target_observations=target_observations,
        tracker_candidates=tracker_candidates,
        config=config,
    )

    return {
        "sequence_id": sequence_id,
        "capture_bag": str(capture_bag),
        "dataset_identity": target["dataset_identity"],
        "target_observation_count": len(target_observations),
        "tracker_candidate_count": len(tracker_candidates),
        "initial_tracker_identity": result.initial_tracker_identity,
        "success": result.success,
        "reason": result.reason,
        "confirmed_frames": result.confirmed_frames,
        "initialization_frame_index": result.initialization_frame_index,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sequence_id")
    parser.add_argument("capture_bag", type=Path)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    arguments = parser.parse_args()

    result = resolve(
        sequence_id=arguments.sequence_id,
        capture_bag=arguments.capture_bag,
        manifest_path=arguments.manifest,
    )

    print(json.dumps(result, indent=2))

    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
