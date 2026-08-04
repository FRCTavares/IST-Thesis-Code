#!/usr/bin/env python3
"""Extract paired MARS and RepVGG observations from an Issue #44 ROS bag.

This tool is offline and observational. It executes MARS-small128 on the
exact BGR crop carried by each RepVGG request and pairs the two independent
embedding-space observations by request ID.

It never compares a 128D MARS vector directly with a 512D RepVGG vector and
does not modify target memory, ranking, target selection, or canonical YAML.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

import numpy as np


SCHEMA = "p044_observational_embedding_pairs_v1"
REQUEST_TOPIC = "/appearance/reid/request"
RESULT_TOPIC = "/appearance/reid/result"
STATUS_TOPIC = "/target_memory_mars/status"


def decode_crop(message: Any) -> np.ndarray:
    """Decode one BGR8 crop while removing any row padding."""
    height = int(message.crop_height)
    width = int(message.crop_width)
    step = int(message.crop_step)
    encoding = str(message.crop_encoding)

    if encoding != "bgr8":
        raise ValueError(
            f"unsupported crop encoding: {encoding!r}"
        )

    if height <= 0 or width <= 0:
        raise ValueError(
            f"invalid crop dimensions: {height}x{width}"
        )

    pixel_step = width * 3

    if step < pixel_step:
        raise ValueError(
            f"crop step {step} is smaller than {pixel_step}"
        )

    raw = np.frombuffer(
        bytes(message.crop_data),
        dtype=np.uint8,
    )

    expected = height * step

    if raw.size != expected:
        raise ValueError(
            f"crop byte length mismatch: {raw.size} != {expected}"
        )

    rows = raw.reshape(height, step)
    pixels = np.ascontiguousarray(
        rows[:, :pixel_step]
    )

    return pixels.reshape(height, width, 3)


def validate_vector(
    values: Any,
    *,
    dimension: int,
    label: str,
) -> tuple[np.ndarray, float]:
    """Validate one finite, nonzero vector without changing its space."""
    vector = np.asarray(
        values,
        dtype=np.float32,
    ).reshape(-1)

    if vector.size != dimension:
        raise ValueError(
            f"{label} dimension mismatch: "
            f"{vector.size} != {dimension}"
        )

    if not np.all(np.isfinite(vector)):
        raise ValueError(
            f"{label} contains non-finite values"
        )

    norm = float(np.linalg.norm(vector))

    if not math.isfinite(norm) or norm <= 0.0:
        raise ValueError(
            f"{label} has zero or invalid norm"
        )

    return vector, norm


def storage_identifier(bag: Path) -> str:
    """Read the rosbag2 storage identifier when metadata is available."""
    metadata = bag / "metadata.yaml"

    if not metadata.is_file():
        return "mcap"

    try:
        import yaml

        payload = yaml.safe_load(
            metadata.read_text(encoding="utf-8")
        )
        information = payload.get(
            "rosbag2_bagfile_information",
            {},
        )
        return str(
            information.get(
                "storage_identifier",
                "mcap",
            )
        )
    except Exception:
        return "mcap"


def read_bag(
    bag: Path,
) -> tuple[
    dict[int, tuple[Any, int]],
    dict[int, tuple[Any, int]],
    dict[int, dict[str, Any]],
]:
    """Read requests, results and CPU-authoritative TIM status messages."""
    import rosbag2_py
    from rclpy.serialization import deserialize_message
    from rosidl_runtime_py.utilities import get_message

    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(
            uri=str(bag),
            storage_id=storage_identifier(bag),
        ),
        rosbag2_py.ConverterOptions(
            input_serialization_format="cdr",
            output_serialization_format="cdr",
        ),
    )

    topic_types = {
        item.name: item.type
        for item in reader.get_all_topics_and_types()
    }

    required = {
        REQUEST_TOPIC:
            "thesis_msgs/msg/AppearanceEmbeddingRequest",
        RESULT_TOPIC:
            "thesis_msgs/msg/AppearanceEmbeddingResult",
        STATUS_TOPIC:
            "std_msgs/msg/String",
    }

    for topic, expected_type in required.items():
        actual_type = topic_types.get(topic)

        if actual_type != expected_type:
            raise RuntimeError(
                f"{topic}: expected {expected_type}, "
                f"found {actual_type!r}"
            )

    message_types = {
        topic: get_message(type_name)
        for topic, type_name in required.items()
    }

    requests: dict[int, tuple[Any, int]] = {}
    results: dict[int, tuple[Any, int]] = {}
    statuses: dict[int, dict[str, Any]] = {}

    while reader.has_next():
        topic, serialized, timestamp_ns = reader.read_next()

        if topic not in message_types:
            continue

        message = deserialize_message(
            serialized,
            message_types[topic],
        )

        if topic == REQUEST_TOPIC:
            request_id = int(message.request_id)

            if request_id in requests:
                raise RuntimeError(
                    f"duplicate request ID: {request_id}"
                )

            requests[request_id] = (
                message,
                int(timestamp_ns),
            )

        elif topic == RESULT_TOPIC:
            request_id = int(message.request_id)

            if request_id in results:
                raise RuntimeError(
                    f"duplicate result ID: {request_id}"
                )

            results[request_id] = (
                message,
                int(timestamp_ns),
            )

        else:
            try:
                payload = json.loads(str(message.data))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue

            if not isinstance(payload, dict):
                continue

            frame_id = payload.get("frame_id")

            if frame_id is not None:
                statuses[int(frame_id)] = payload

    return requests, results, statuses


def write_json(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(
        path.suffix + ".tmp"
    )
    temporary.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def write_jsonl(
    path: Path,
    records: list[dict[str, Any]],
) -> None:
    temporary = path.with_suffix(
        path.suffix + ".tmp"
    )

    with temporary.open(
        "w",
        encoding="utf-8",
    ) as stream:
        for record in records:
            stream.write(
                json.dumps(
                    record,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            stream.write("\n")

    os.replace(temporary, path)


def extract(
    *,
    bag: Path,
    output: Path,
    mars_model: Path,
    run_id: str,
    condition: str,
) -> dict[str, Any]:
    """Extract paired observations from one recorded run."""
    from thesis_bringup.tim_mars.mars_reid_backend import (
        MarsReIdBackend,
    )

    requests, results, statuses = read_bag(bag)

    mars_backend = MarsReIdBackend(
        mars_model,
        batch_size=1,
    )

    paired: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for request_id in sorted(requests):
        request, request_bag_ns = requests[request_id]

        try:
            crop = decode_crop(request)
        except ValueError as exc:
            rejected.append(
                {
                    "request_id": request_id,
                    "reason": "invalid_crop",
                    "detail": str(exc),
                }
            )
            continue

        mars_embedding = mars_backend.encode(
            crop,
            [
                (
                    0.0,
                    0.0,
                    float(crop.shape[1]),
                    float(crop.shape[0]),
                )
            ],
        )[0]

        if mars_embedding is None:
            rejected.append(
                {
                    "request_id": request_id,
                    "reason": "mars_encoding_failed",
                }
            )
            continue

        result_item = results.get(request_id)

        if result_item is None:
            rejected.append(
                {
                    "request_id": request_id,
                    "reason": "missing_repvgg_result",
                }
            )
            continue

        result, result_bag_ns = result_item

        if not bool(result.succeeded):
            rejected.append(
                {
                    "request_id": request_id,
                    "reason": "repvgg_failure",
                    "error": str(result.error),
                }
            )
            continue

        try:
            mars_vector, mars_norm = validate_vector(
                mars_embedding,
                dimension=128,
                label="MARS",
            )
            repvgg_vector, repvgg_norm = validate_vector(
                result.embedding,
                dimension=512,
                label="RepVGG",
            )
        except ValueError as exc:
            rejected.append(
                {
                    "request_id": request_id,
                    "reason": "invalid_embedding",
                    "detail": str(exc),
                }
            )
            continue

        frame_id = int(request.source_frame_id)
        status = statuses.get(frame_id)

        paired.append(
            {
                "schema": SCHEMA,
                "run_id": run_id,
                "condition": condition,
                "request_id": request_id,
                "request_bag_timestamp_ns": request_bag_ns,
                "result_bag_timestamp_ns": result_bag_ns,
                "source_frame_id": frame_id,
                "source_image_timestamp_ns": int(
                    request.source_image_timestamp_ns
                ),
                "source_image_seq": int(
                    request.source_image_seq
                ),
                "frame_generation": int(
                    request.frame_generation
                ),
                "candidate_index": int(
                    request.candidate_index
                ),
                "track_id": int(request.track_id),
                "track_generation": int(
                    request.track_generation
                ),
                "source_bbox_xyxy": [
                    float(value)
                    for value in request.source_bbox_xyxy
                ],
                "crop_sha256": hashlib.sha256(
                    crop.tobytes(order="C")
                ).hexdigest(),
                "cpu_mars_authoritative": True,
                "repvgg_observational_only": True,
                "cross_model_similarity_computed": False,
                "mars": {
                    "dimension": 128,
                    "norm": mars_norm,
                    "embedding": mars_vector.tolist(),
                },
                "repvgg": {
                    "backend_name": str(
                        result.backend_name
                    ),
                    "embedding_space": str(
                        result.embedding_space
                    ),
                    "dimension": 512,
                    "norm": repvgg_norm,
                    "embedding": repvgg_vector.tolist(),
                },
                "tim_status": status,
            }
        )

    output.mkdir(
        parents=True,
        exist_ok=False,
    )

    write_jsonl(
        output / "paired_embeddings.jsonl",
        paired,
    )
    write_jsonl(
        output / "rejected_observations.jsonl",
        rejected,
    )

    summary = {
        "schema": SCHEMA,
        "run_id": run_id,
        "condition": condition,
        "source_bag": str(bag.resolve()),
        "mars_model": str(mars_model.resolve()),
        "counts": {
            "requests": len(requests),
            "results": len(results),
            "status_frames": len(statuses),
            "paired": len(paired),
            "rejected": len(rejected),
        },
        "claim_boundary": {
            "causally_identical_crops": True,
            "cross_model_similarity_computed": False,
            "ranking_equivalence_computed": False,
            "target_decision_equivalence_computed": False,
            "runtime_modified": False,
            "canonical_policy_changed": False,
            "cpu_mars_authoritative": True,
        },
    }

    write_json(
        output / "summary.json",
        summary,
    )

    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("bag", type=Path)
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--mars-model",
        required=True,
        type=Path,
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--condition", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.bag.is_dir():
        raise SystemExit(
            f"ERROR: bag directory absent: {args.bag}"
        )

    if not args.mars_model.is_file():
        raise SystemExit(
            f"ERROR: MARS model absent: {args.mars_model}"
        )

    if args.output.exists():
        raise SystemExit(
            f"ERROR: output already exists: {args.output}"
        )

    summary = extract(
        bag=args.bag,
        output=args.output,
        mars_model=args.mars_model,
        run_id=args.run_id,
        condition=args.condition,
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
