#!/usr/bin/env python3
"""Replay one frozen shared detector cache through one canonical raw tracker."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from replay_shared_detector_cache import (  # noqa: E402
    LOGICAL_FRAME_TICK_NS,
    replay_backend,
    validate_sequence_cache,
)
from shared_detector_cache import read_committed_frozen_inputs  # noqa: E402
from write_shared_detector_cache import (  # noqa: E402
    image_paths_by_source_frame,
    write_cache_once,
)


ARM_CONFIGS = {
    "sort_raw": "ros2_ws/src/thesis_bringup/config/tracker_sort.yaml",
    "bytetrack_raw": "ros2_ws/src/thesis_bringup/config/tracker_bytetrack.yaml",
    "ocsort_raw": "ros2_ws/src/thesis_bringup/config/tracker_ocsort.yaml",
    "deepsort_raw": "ros2_ws/src/thesis_bringup/config/tracker_deepsort.yaml",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def make_deepsort_image_callback(
    *,
    backend: Any,
    image_paths: dict[int, Path],
):
    """Feed the same BGR source image and logical stamp before each update."""
    import cv2
    from sensor_msgs.msg import Image

    def before_frame(source_frame: int, logical_stamp_ns: int) -> None:
        image = cv2.imread(str(image_paths[source_frame]), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"unreadable DeepSORT source image: {image_paths[source_frame]}")
        height, width = image.shape[:2]
        message = Image()
        message.header.stamp.sec = logical_stamp_ns // LOGICAL_FRAME_TICK_NS
        message.header.stamp.nanosec = logical_stamp_ns % LOGICAL_FRAME_TICK_NS
        message.height = height
        message.width = width
        message.encoding = "bgr8"
        message.step = width * 3
        message.data = image.tobytes()
        backend.update_latest_image(message)

    return before_frame


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", choices=tuple(ARM_CONFIGS), required=True)
    parser.add_argument("--split", choices=("train", "val"), required=True)
    parser.add_argument("--sequence", required=True)
    parser.add_argument(
        "--dataset-root", type=Path,
        default=ROOT / "data" / "datasets" / "external" / "visdrone_mot",
    )
    parser.add_argument(
        "--cache-root", type=Path,
        default=ROOT / "artifacts" / "reports" / "p125_shared_detector_cache",
    )
    parser.add_argument(
        "--output-root", type=Path,
        default=ROOT / "artifacts" / "reports" / "p125_raw_tracker_replay",
    )
    args = parser.parse_args()

    frozen = read_committed_frozen_inputs(
        repository_root=ROOT,
        protocol_path=ROOT / "docs/data/external_benchmark_v2/visdrone_selected_person_protocol_v1.json",
        manifest_path=ROOT / "docs/data/external_benchmark_v2/visdrone_gt_only_episode_manifest_v1.json",
    )
    protocol = frozen["protocol"]
    manifest = frozen["manifest"]
    inventory = [
        entry for entry in manifest["sequence_inventory"]
        if entry["split"] == args.split and entry["sequence_name"] == args.sequence
    ]
    if len(inventory) != 1:
        raise ValueError("sequence is absent or duplicated in frozen manifest")
    entry = inventory[0]
    image_dir = args.dataset_root / args.split / "sequences" / args.sequence
    image_paths = image_paths_by_source_frame(image_dir)
    source_numbers = sorted(image_paths)
    if (
        len(source_numbers) != entry["image_frame_count"]
        or source_numbers[0] != entry["first_source_frame"]
        or source_numbers[-1] != entry["last_source_frame"]
    ):
        raise ValueError("source images differ from frozen inventory")
    annotation_path = args.dataset_root / args.split / "annotations" / f"{args.sequence}.txt"
    if sha256_file(annotation_path) != entry["annotation_sha256"]:
        raise ValueError("annotation differs from frozen inventory")

    hashes = protocol["pre_result_implementation_hashes_draft"]
    hef_relative = "models/hef/yolov8s.hef"
    hef_sha = hashes[hef_relative]
    cache_path = args.cache_root / args.split / f"{args.sequence}.json"
    cache_sha = sha256_file(cache_path)
    cache = json.loads(cache_path.read_text())
    frames = validate_sequence_cache(
        cache,
        protocol_sha256=frozen["protocol_sha256"],
        manifest_sha256=frozen["manifest_sha256"],
        freeze_commit=frozen["freeze_commit"],
        expected_split=args.split,
        expected_sequence=args.sequence,
        expected_source_frame_numbers=source_numbers,
        detector_hef_sha256=hef_sha,
        detector_minimum_score=float(protocol["shared_detector_draft"]["minimum_score"]),
    )

    config_relative = ARM_CONFIGS[args.arm]
    frozen_arms = {
        arm["id"]: arm for arm in protocol["architectures_planned"]
    }
    if frozen_arms[args.arm]["config"] != config_relative:
        raise ValueError("requested tracker config differs from frozen arm")
    config_path = ROOT / config_relative
    config_sha = sha256_file(config_path)
    if config_sha != hashes[config_relative]:
        raise ValueError("tracker config differs from frozen protocol hash")
    mars_relative = "models/reid/mars-small128.pb"
    mars_path = ROOT / mars_relative
    if args.arm == "deepsort_raw" and sha256_file(mars_path) != hashes[mars_relative]:
        raise ValueError("DeepSORT MARS model differs from frozen protocol hash")

    hailo_log_dir = ROOT / "ros2_ws" / "log" / "hailort"
    hailo_log_dir.mkdir(parents=True, exist_ok=True)
    os.environ["HAILORT_LOGGER_PATH"] = str(hailo_log_dir)
    sys.path.insert(0, str(ROOT / "tools" / "experiments"))
    from run_deterministic_tracker_replay import build_backend, load_tracker_parameters

    parameters = load_tracker_parameters(config_path)
    tracker_type, minimum_score, backend = build_backend(
        parameters,
        mars_path if args.arm == "deepsort_raw" else None,
    )
    expected_type = args.arm.removesuffix("_raw")
    if tracker_type != expected_type:
        raise ValueError("tracker YAML type differs from requested arm")
    before_frame = (
        make_deepsort_image_callback(backend=backend, image_paths=image_paths)
        if args.arm == "deepsort_raw" else None
    )
    replay = replay_backend(
        frames=frames,
        backend=backend,
        minimum_score=minimum_score,
        before_frame=before_frame,
    )
    document = {
        "schema": "p125_raw_tracker_sequence_replay_v1",
        "arm": args.arm,
        "split": args.split,
        "sequence_name": args.sequence,
        "protocol_sha256": frozen["protocol_sha256"],
        "manifest_sha256": frozen["manifest_sha256"],
        "freeze_commit": frozen["freeze_commit"],
        "detector_cache_sha256": cache_sha,
        "tracker_config_sha256": config_sha,
        "logical_frame_tick_ns": LOGICAL_FRAME_TICK_NS,
        "logical_tick_is_physical_time": False,
        "frame_count": len(replay),
        "frames": replay,
    }
    output_path = args.output_root / args.arm / args.split / f"{args.sequence}.json"
    digest = write_cache_once(output_path, document)
    print(json.dumps({"output": str(output_path), "sha256": digest}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
