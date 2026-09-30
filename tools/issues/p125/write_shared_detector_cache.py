#!/usr/bin/env python3
"""Write one Issue #125 shared detector cache after the committed freeze.

No dataset image or Hailo engine is opened until the protocol and episode
manifest have both passed the committed freeze checkpoint.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

import cv2

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from shared_detector_cache import (  # noqa: E402
    build_sequence_cache,
    prepare_source_image,
    read_committed_frozen_inputs,
    source_pixel_detections,
)


def image_paths_by_source_frame(image_dir: Path) -> dict[int, Path]:
    if not image_dir.is_dir():
        raise FileNotFoundError(image_dir)
    paths: dict[int, Path] = {}
    for path in sorted(image_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            continue
        try:
            frame = int(path.stem)
        except ValueError as exc:
            raise ValueError(f"non-numeric source image: {path.name}") from exc
        if frame <= 0 or frame in paths:
            raise ValueError(f"invalid or duplicate source frame {frame}")
        paths[frame] = path
    if not paths:
        raise ValueError(f"no source images in {image_dir}")
    return paths


def generate_sequence_cache(
    *,
    image_paths: dict[int, Path],
    engine: Any,
    protocol_sha256: str,
    split: str,
    sequence_name: str,
    inference_width: int,
    inference_height: int,
    minimum_score: float,
    infer_timeout_ms: int,
) -> dict[str, object]:
    """Run each source image once; a detector timeout fails the sequence."""
    source_frames = sorted(image_paths)
    frame_detections: list[tuple[int, Sequence[dict[str, object]]]] = []
    for source_frame in source_frames:
        image = cv2.imread(str(image_paths[source_frame]), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"unreadable source image: {image_paths[source_frame]}")
        rgb, transform = prepare_source_image(
            image,
            inference_width=inference_width,
            inference_height=inference_height,
        )
        result = engine.infer(rgb, source_frame, source_frame - 1, 0, infer_timeout_ms)
        if result is None:
            raise RuntimeError(f"detector timeout on source frame {source_frame}")
        if not isinstance(result, dict) or "detections" not in result:
            raise ValueError(f"invalid detector result on source frame {source_frame}")
        frame_detections.append((
            source_frame,
            source_pixel_detections(
                result["detections"],
                transform=transform,
                minimum_score=minimum_score,
            ),
        ))
    return build_sequence_cache(
        protocol_status="frozen",
        protocol_sha256=protocol_sha256,
        split=split,
        sequence_name=sequence_name,
        expected_source_frame_numbers=source_frames,
        frame_detections=frame_detections,
    )


def write_cache_once(path: Path, document: dict[str, object]) -> str:
    """Publish atomically and reject a differing second run."""
    payload = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()
    digest = hashlib.sha256(payload).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError(f"existing detector cache differs: {path}")
        return digest
    with tempfile.NamedTemporaryFile(
        mode="wb", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as temporary:
        temporary.write(payload)
        temporary_path = Path(temporary.name)
    try:
        try:
            os.link(temporary_path, path)
        except FileExistsError:
            if path.read_bytes() != payload:
                raise ValueError(f"existing detector cache differs: {path}")
    finally:
        temporary_path.unlink(missing_ok=True)
    return digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("train", "val"), required=True)
    parser.add_argument("--sequence", required=True)
    parser.add_argument(
        "--dataset-root", type=Path,
        default=ROOT / "data" / "datasets" / "external" / "visdrone_mot",
    )
    parser.add_argument(
        "--output-root", type=Path,
        default=ROOT / "artifacts" / "reports" / "p125_shared_detector_cache",
    )
    args = parser.parse_args()

    protocol_path = ROOT / "docs/data/external_benchmark_v2/visdrone_selected_person_protocol_v1.json"
    manifest_path = ROOT / "docs/data/external_benchmark_v2/visdrone_gt_only_episode_manifest_v1.json"
    frozen = read_committed_frozen_inputs(
        repository_root=ROOT,
        protocol_path=protocol_path,
        manifest_path=manifest_path,
    )
    protocol = frozen["protocol"]
    manifest = frozen["manifest"]
    detector = protocol["shared_detector_draft"]
    inventory = [
        entry for entry in manifest["sequence_inventory"]
        if entry["split"] == args.split and entry["sequence_name"] == args.sequence
    ]
    if len(inventory) != 1:
        raise ValueError("sequence is absent or duplicated in frozen manifest")
    inventory_entry = inventory[0]
    annotation_path = (
        args.dataset_root / args.split / "annotations" / f"{args.sequence}.txt"
    )
    annotation_sha = hashlib.sha256(annotation_path.read_bytes()).hexdigest()
    if annotation_sha != inventory_entry["annotation_sha256"]:
        raise ValueError("annotation file differs from frozen sequence inventory")
    if (
        detector["source_image_encoding"] != "bgr8"
        or detector["inference_encoding"] != "rgb8"
        or detector["resize"] != "cv2.INTER_LINEAR_direct_resize"
        or detector["label"] != "person"
        or detector["coordinate_transform_contract"]
        != "tim_mars_source_pixels_resize_v1"
    ):
        raise ValueError("unsupported frozen detector preprocessing contract")
    image_dir = args.dataset_root / args.split / "sequences" / args.sequence
    image_paths = image_paths_by_source_frame(image_dir)
    source_frames = sorted(image_paths)
    if (
        len(source_frames) != inventory_entry["image_frame_count"]
        or source_frames[0] != inventory_entry["first_source_frame"]
        or source_frames[-1] != inventory_entry["last_source_frame"]
    ):
        raise ValueError("source images do not match frozen sequence inventory")

    hef_relative = "models/hef/yolov8s.hef"
    hef_path = ROOT / hef_relative
    hef_sha = hashlib.sha256(hef_path.read_bytes()).hexdigest()
    expected_hef_sha = protocol["pre_result_implementation_hashes_draft"][hef_relative]
    if hef_sha != expected_hef_sha:
        raise ValueError("detector HEF differs from frozen protocol hash")

    hailo_log_dir = ROOT / "ros2_ws" / "log" / "hailort"
    hailo_log_dir.mkdir(parents=True, exist_ok=True)
    os.environ["HAILORT_LOGGER_PATH"] = str(hailo_log_dir)
    sys.path.insert(0, str(ROOT / "ros2_ws" / "src" / "thesis_bringup"))
    from thesis_bringup.perception.inference_engines import HailoDirectInferenceEngine

    timeout_ms = int(detector["infer_timeout_ms"])
    engine = HailoDirectInferenceEngine(
        hef_path=str(hef_path),
        infer_timeout_ms=timeout_ms,
        label_filter="person",
    )
    try:
        document = generate_sequence_cache(
            image_paths=image_paths,
            engine=engine,
            protocol_sha256=frozen["protocol_sha256"],
            split=args.split,
            sequence_name=args.sequence,
            inference_width=int(detector["input_width"]),
            inference_height=int(detector["input_height"]),
            minimum_score=float(detector["minimum_score"]),
            infer_timeout_ms=timeout_ms,
        )
    finally:
        engine.close()
    document["manifest_sha256"] = frozen["manifest_sha256"]
    document["freeze_commit"] = frozen["freeze_commit"]
    document["detector_hef_sha256"] = hef_sha
    output_path = args.output_root / args.split / f"{args.sequence}.json"
    digest = write_cache_once(output_path, document)
    print(json.dumps({
        "output": str(output_path),
        "sha256": digest,
        "source_frame_count": document["source_frame_count"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
