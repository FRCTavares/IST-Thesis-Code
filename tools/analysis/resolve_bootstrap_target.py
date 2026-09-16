#!/usr/bin/env python3
"""Resolve the operator bootstrap tracker ID for a deterministic tracker-replay
bag by spatial agreement with the frozen physical-target reference.

The operator selects the same physical person regardless of tracker
configuration. Historical tracker IDs cannot be reused across ByteTrack
configurations because the IDs change. This resolver aligns the generated
``/tracks`` stream to the first ``present_scored`` physical-reference sample,
then selects the best-overlapping track within the architecture's frozen frame
budget. The same rule is applied identically to every configuration.

Exit code 0 and ``ok: true`` when a track is resolved; exit code 2 and
``ok: false`` when no track reaches the threshold within the bootstrap window
(a preserved experimental result, not an error to hide).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rclpy.serialization import deserialize_message
from rosbag2_py import ConverterOptions, SequentialReader, StorageOptions
from rosidl_runtime_py.utilities import get_message


def iou_xyxy(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0.0:
        return 0.0
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    denom = area_a + area_b - inter
    return inter / denom if denom > 0.0 else 0.0


def first_scored_target(reference: dict) -> tuple[list[float], float]:
    for sample in reference["samples"]:
        if sample.get("identity_state") == "present_scored" and sample.get("target_bbox_xyxy"):
            return list(sample["target_bbox_xyxy"]), float(sample["t_s"])
    raise SystemExit("physical reference has no present_scored target sample")


def scored_target_boxes_by_time_ns(reference: dict) -> dict[int, list[float]]:
    """Index exact present-scored reference boxes by relative nanoseconds."""
    return {
        round(float(sample["t_s"]) * 1_000_000_000): list(
            sample["target_bbox_xyxy"]
        )
        for sample in reference["samples"]
        if sample.get("identity_state") == "present_scored"
        and sample.get("target_bbox_xyxy")
    }


def track_boxes(msg) -> list[tuple[int, tuple[float, float, float, float]]]:
    boxes = []
    for track in msg.tracks:
        cx, cy, w, h = float(track.cx), float(track.cy), float(track.w), float(track.h)
        boxes.append(
            (int(track.id), (cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0))
        )
    return boxes


def message_time_ns(msg, record_time_ns: int) -> int:
    """Return a source/header timestamp, falling back to bag record time."""
    source_time_ns = int(getattr(msg, "src_stamp_ns", 0))
    if source_time_ns > 0:
        return source_time_ns

    header = getattr(msg, "header", None)
    stamp = getattr(header, "stamp", None)
    if stamp is not None:
        header_time_ns = (
            int(getattr(stamp, "sec", 0)) * 1_000_000_000
            + int(getattr(stamp, "nanosec", 0))
        )
        if header_time_ns > 0:
            return header_time_ns

    return int(record_time_ns)


def open_reader(tracks_bag: Path) -> SequentialReader:
    reader = SequentialReader()
    reader.open(
        StorageOptions(uri=str(tracks_bag), storage_id="mcap"),
        ConverterOptions("cdr", "cdr"),
    )
    return reader


def first_topic_time_ns(
    tracks_bag: Path,
    topic_name: str,
) -> tuple[int, str | None]:
    """Return the first message time for one retained source topic."""
    reader = open_reader(tracks_bag)
    types = {t.name: t.type for t in reader.get_all_topics_and_types()}
    if topic_name not in types:
        raise RuntimeError(f"no {topic_name} in {tracks_bag}")
    msg_cls = get_message(types[topic_name])

    while reader.has_next():
        topic, raw, record_time_ns = reader.read_next()
        if topic != topic_name:
            continue
        msg = deserialize_message(raw, msg_cls)
        return message_time_ns(msg, record_time_ns), types[topic_name]

    raise RuntimeError(f"no messages on {topic_name} in {tracks_bag}")


def resolve(
    tracks_bag: Path,
    reference_path: Path,
    tracks_topic: str,
    min_iou: float,
    max_lag_frames: int,
    required_frame_index: int | None = None,
) -> dict:
    reference = json.loads(reference_path.read_text())
    initial_ref_box, ref_t = first_scored_target(reference)
    reference_boxes = scored_target_boxes_by_time_ns(reference)

    if required_frame_index is not None and not (
        0 <= required_frame_index < max_lag_frames
    ):
        raise ValueError(
            "required_frame_index must be within the bootstrap frame budget"
        )

    image_topic = str(
        reference.get("provenance", {}).get(
            "source_image_topic", "/camera/image_raw"
        )
    )
    try:
        reference_origin_ns, _image_type = first_topic_time_ns(
            tracks_bag, image_topic
        )
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc)}
    reference_instant_ns = reference_origin_ns + round(ref_t * 1_000_000_000)

    reader = open_reader(tracks_bag)
    types = {t.name: t.type for t in reader.get_all_topics_and_types()}
    if tracks_topic not in types:
        return {"ok": False, "error": f"no {tracks_topic} in {tracks_bag}"}
    msg_cls = get_message(types[tracks_topic])

    per_frame: list[dict] = []
    frame_index = 0
    skipped_before_reference = 0
    resolved: dict | None = None
    required_frame_box: list[float] | None = None
    while reader.has_next():
        topic, raw, record_time_ns = reader.read_next()
        if topic != tracks_topic:
            continue
        msg = deserialize_message(raw, msg_cls)
        track_time_ns = message_time_ns(msg, record_time_ns)
        if track_time_ns < reference_instant_ns:
            skipped_before_reference += 1
            continue
        if frame_index >= max_lag_frames:
            break
        relative_time_ns = track_time_ns - reference_origin_ns
        frame_ref_box = reference_boxes.get(relative_time_ns)
        best_iou, best_id = 0.0, None
        if frame_ref_box is not None:
            for track_id, box in track_boxes(msg):
                value = iou_xyxy(box, tuple(frame_ref_box))
                if value > best_iou:
                    best_iou, best_id = value, track_id
        if frame_index == required_frame_index:
            required_frame_box = frame_ref_box
        per_frame.append(
            {
                "frame_index": frame_index,
                "track_time_ns": track_time_ns,
                "track_time_from_reference_origin_s": round(
                    (track_time_ns - reference_origin_ns) / 1_000_000_000,
                    9,
                ),
                "reference_target_bbox_xyxy": frame_ref_box,
                "best_iou": round(best_iou, 6),
                "best_track_id": best_id,
            }
        )
        frame_is_eligible = (
            required_frame_index is None
            or frame_index == required_frame_index
        )
        if (
            resolved is None
            and frame_is_eligible
            and best_id is not None
            and best_iou >= min_iou
        ):
            resolved = {
                "resolved_track_id": int(best_id),
                "bootstrap_iou": round(float(best_iou), 6),
                "bootstrap_frame_index": frame_index,
                "reference_target_bbox_xyxy": frame_ref_box,
            }
        frame_index += 1

    result = {
        "ok": resolved is not None,
        "resolved_track_id": resolved["resolved_track_id"] if resolved else None,
        "bootstrap_iou": resolved["bootstrap_iou"] if resolved else (
            max((f["best_iou"] for f in per_frame), default=0.0)
        ),
        "bootstrap_frame_index": resolved["bootstrap_frame_index"] if resolved else None,
        "reference_sample_t_s": ref_t,
        "reference_time_origin_topic": image_topic,
        "reference_time_origin_ns": reference_origin_ns,
        "reference_instant_ns": reference_instant_ns,
        "reference_target_bbox_xyxy": (
            resolved["reference_target_bbox_xyxy"]
            if resolved
            else required_frame_box or initial_ref_box
        ),
        "first_present_scored_target_bbox_xyxy": initial_ref_box,
        "min_iou_required": min_iou,
        "max_bootstrap_lag_frames": max_lag_frames,
        "required_bootstrap_frame_index": required_frame_index,
        "frames_inspected": len(per_frame),
        "track_frames_skipped_before_reference": skipped_before_reference,
        "per_frame_best": per_frame[:12],
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tracks_bag", type=Path)
    parser.add_argument("--physical-reference", type=Path, required=True)
    parser.add_argument("--tracks-topic", default="/tracks")
    parser.add_argument("--min-iou", type=float, default=0.5)
    parser.add_argument("--max-bootstrap-lag-frames", type=int, default=30)
    parser.add_argument("--required-bootstrap-frame-index", type=int, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    result = resolve(
        args.tracks_bag,
        args.physical_reference,
        args.tracks_topic,
        args.min_iou,
        args.max_bootstrap_lag_frames,
        args.required_bootstrap_frame_index,
    )
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n")
    print(text)
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
