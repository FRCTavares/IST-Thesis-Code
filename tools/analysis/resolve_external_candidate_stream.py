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


MINIMUM_FREE_GIB_AFTER_DECOMPRESSION = 25
DECOMPRESSED_SIZE_SAFETY_MULTIPLIER = 6


def is_compressed_bag(bag_path: Path) -> bool:
    """Detect file-level bag compression from metadata.yaml."""

    metadata_path = Path(bag_path) / "metadata.yaml"

    if not metadata_path.is_file():
        return False

    text = metadata_path.read_text(encoding="utf-8", errors="ignore")

    return (
        "compression_mode: FILE" in text
        or "compression_mode: MESSAGE" in text
    )


def _free_space_gib(path: Path) -> float:
    import shutil as _shutil

    usage = _shutil.disk_usage(path)
    return usage.free / (1024**3)


def ensure_uncompressed_bag(
    bag_path: Path,
    *,
    work_root: Path | None = None,
) -> Path:
    """Return an uncompressed bag directory usable by a plain reader.

    ``rosbag2_py.SequentialCompressionReader`` decompresses the *entire*
    mcap file to a full uncompressed copy up front (observed: a 1.7 GB
    compressed capture produced a 7.5 GB decompressed file), and doing this
    independently in both the resolve step and the deterministic replay step
    for the same sequence contributed to an out-of-memory crash and full
    reboot of the (8 GB RAM, zero swap) development Pi on 2026-08-07. This
    function instead decompresses once, explicitly, via the ``zstd`` CLI
    (which streams in small fixed buffers regardless of file size, unlike
    the observed rosbag2_py behaviour), and the caller is expected to reuse
    the returned path for every step that needs to read this bag, then
    delete it when done.

    If ``bag_path`` is already uncompressed, it is returned unchanged (no
    copy, no cleanup obligation) -- callers should only delete the returned
    path if it differs from the input.
    """

    import shutil
    import subprocess

    import yaml

    bag_path = Path(bag_path)

    if not is_compressed_bag(bag_path):
        return bag_path

    metadata_path = bag_path / "metadata.yaml"
    metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    info = metadata["rosbag2_bagfile_information"]

    relative_paths = info["relative_file_paths"]
    if len(relative_paths) != 1:
        raise ValueError(
            f"{bag_path}: expected exactly one compressed file, "
            f"found {relative_paths}"
        )

    compressed_file = bag_path / relative_paths[0]
    if not compressed_file.name.endswith(".zstd"):
        raise ValueError(
            f"{bag_path}: expected a .zstd compressed file, "
            f"found {compressed_file.name}"
        )

    uncompressed_name = compressed_file.name[: -len(".zstd")]

    work_root = work_root or bag_path.parent
    dest_dir = work_root / f"{bag_path.name}__decompressed_tmp"

    compressed_size_gib = compressed_file.stat().st_size / (1024**3)
    required_gib = (
        compressed_size_gib * DECOMPRESSED_SIZE_SAFETY_MULTIPLIER
        + MINIMUM_FREE_GIB_AFTER_DECOMPRESSION
    )
    available_gib = _free_space_gib(work_root)

    if available_gib < required_gib:
        raise RuntimeError(
            f"refusing to decompress {bag_path}: only "
            f"{available_gib:.1f} GiB free, need an estimated "
            f"{required_gib:.1f} GiB (compressed size "
            f"{compressed_size_gib:.1f} GiB x"
            f"{DECOMPRESSED_SIZE_SAFETY_MULTIPLIER} + "
            f"{MINIMUM_FREE_GIB_AFTER_DECOMPRESSION} GiB floor)"
        )

    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True)

    dest_mcap = dest_dir / uncompressed_name
    subprocess.run(
        ["zstd", "-d", "--long=31", str(compressed_file), "-o", str(dest_mcap)],
        check=True,
    )

    info["relative_file_paths"] = [uncompressed_name]
    info["files"] = [
        {
            **entry,
            "path": uncompressed_name,
        }
        for entry in info["files"]
    ]
    # An uncompressed bag written by the real rosbag2 writer still carries
    # these keys with empty-string values; the metadata schema requires
    # their presence (a genuinely uncompressed bag was checked to confirm
    # this rather than assumed), so they are set, not removed.
    info["compression_format"] = ""
    info["compression_mode"] = ""

    (dest_dir / "metadata.yaml").write_text(
        yaml.safe_dump(metadata, sort_keys=False),
        encoding="utf-8",
    )

    return dest_dir


def open_bag_reader(bag_path: Path):
    """Open an already-uncompressed ``bag_path`` for reading.

    Callers must pass a bag that ``ensure_uncompressed_bag`` has already
    processed; this function deliberately does not fall back to
    ``SequentialCompressionReader`` (see ``ensure_uncompressed_bag`` for
    why that path is unsafe on this hardware).
    """

    if is_compressed_bag(bag_path):
        raise ValueError(
            f"{bag_path} is still compressed; call "
            "ensure_uncompressed_bag() first"
        )

    import rosbag2_py

    reader = rosbag2_py.SequentialReader()
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

    reader = open_bag_reader(ensure_uncompressed_bag(capture_bag))
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
