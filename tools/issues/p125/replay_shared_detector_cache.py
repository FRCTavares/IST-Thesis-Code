#!/usr/bin/env python3
"""Validate and replay one frozen shared detector cache through a tracker.

This module does not construct a detector or tracker backend. Callers supply
the existing backend after the committed protocol/manifest freeze gate.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Sequence


LOGICAL_FRAME_TICK_NS = 1_000_000_000


def validate_sequence_cache(
    cache: dict[str, Any],
    *,
    protocol_sha256: str,
    manifest_sha256: str,
    freeze_commit: str,
    expected_split: str,
    expected_sequence: str,
    expected_source_frame_numbers: Sequence[int],
    detector_hef_sha256: str,
    detector_minimum_score: float,
) -> list[dict[str, Any]]:
    """Require exact provenance and one ordered record per image frame."""
    if cache.get("schema") != "p125_shared_detector_sequence_cache_v1":
        raise ValueError("unexpected shared detector cache schema")
    for key, expected in (
        ("protocol_sha256", protocol_sha256),
        ("manifest_sha256", manifest_sha256),
        ("freeze_commit", freeze_commit),
        ("detector_hef_sha256", detector_hef_sha256),
        ("split", expected_split),
        ("sequence_name", expected_sequence),
    ):
        if cache.get(key) != expected:
            raise ValueError(f"detector cache {key} mismatch")
    expected_frames = list(expected_source_frame_numbers)
    if (
        not expected_frames
        or expected_frames != sorted(set(expected_frames))
        or expected_frames[0] <= 0
    ):
        raise ValueError("expected source frames must be positive, sorted and unique")
    frames = cache.get("frames")
    if not isinstance(frames, list) or len(frames) != len(expected_frames):
        raise ValueError("detector cache image-frame count mismatch")
    if cache.get("source_frame_count") != len(frames):
        raise ValueError("detector cache declared frame count mismatch")
    source_numbers: list[int] = []
    for frame in frames:
        source_number = frame.get("source_frame_number")
        normalized = frame.get("normalized_frame_index")
        if (
            not isinstance(source_number, int)
            or source_number <= 0
            or normalized != source_number - 1
        ):
            raise ValueError("invalid detector cache source-frame mapping")
        source_numbers.append(source_number)
        detections = frame.get("detections")
        if not isinstance(detections, list):
            raise ValueError("detector cache detections must be a list")
        for detection in detections:
            box = detection.get("bbox_xyxy")
            score = detection.get("score")
            if (
                detection.get("class_id") != 0
                or not isinstance(box, list)
                or len(box) != 4
                or not all(isinstance(value, (int, float)) and math.isfinite(value) for value in box)
                or box[2] <= box[0]
                or box[3] <= box[1]
                or not isinstance(score, (int, float))
                or not math.isfinite(score)
                or not detector_minimum_score <= score <= 1.0
            ):
                raise ValueError("invalid detector cache person detection")
    if source_numbers != expected_frames:
        raise ValueError("detector cache source frame domain mismatch")
    return frames


def replay_backend(
    *,
    frames: Sequence[dict[str, Any]],
    backend: Any,
    minimum_score: float,
    before_frame: Callable[[int, int], None] | None = None,
) -> list[dict[str, object]]:
    """Apply one canonical tracker config to every cached source frame."""
    if not 0.0 <= minimum_score <= 1.0:
        raise ValueError("tracker minimum score must be in [0, 1]")
    replay: list[dict[str, object]] = []
    for frame in frames:
        source_number = int(frame["source_frame_number"])
        normalized = int(frame["normalized_frame_index"])
        logical_stamp_ns = source_number * LOGICAL_FRAME_TICK_NS
        if before_frame is not None:
            before_frame(source_number, logical_stamp_ns)
        detections = [
            detection for detection in frame["detections"]
            if float(detection["score"]) >= minimum_score
        ]
        boxes = [tuple(detection["bbox_xyxy"]) for detection in detections]
        scores = [float(detection["score"]) for detection in detections]
        tracks = backend.update(boxes, scores, logical_stamp_ns)
        seen_ids: set[int] = set()
        track_records: list[dict[str, object]] = []
        for track in tracks:
            identity = int(track.track_id)
            box = tuple(float(value) for value in track.bbox_xyxy)
            score = float(track.score)
            if (
                identity <= 0
                or identity in seen_ids
                or len(box) != 4
                or not all(math.isfinite(value) for value in box)
                or box[2] <= box[0]
                or box[3] <= box[1]
                or not math.isfinite(score)
            ):
                raise ValueError(f"invalid tracker output on source frame {source_number}")
            seen_ids.add(identity)
            track_records.append({
                "track_id": identity,
                "bbox_xyxy": list(box),
                "score": score,
            })
        replay.append({
            "source_frame_number": source_number,
            "normalized_frame_index": normalized,
            "logical_frame_stamp_ns": logical_stamp_ns,
            "tracks": track_records,
        })
    return replay
