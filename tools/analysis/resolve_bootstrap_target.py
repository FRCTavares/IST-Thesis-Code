#!/usr/bin/env python3
"""Resolve the operator bootstrap tracker ID for a deterministic tracker-replay
bag by spatial agreement with the frozen physical-target reference.

The operator selects the same physical person regardless of tracker
configuration. Historical tracker IDs cannot be reused across ByteTrack
configurations because the IDs change. This resolver walks the generated
``/tracks`` stream in order and, at the first frame whose best-overlapping
track reaches the IoU threshold against the physical-target reference box at
the first ``present_scored`` reference sample, selects that track ID. The same
rule is applied identically to every configuration.

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


def track_boxes(msg) -> list[tuple[int, tuple[float, float, float, float]]]:
    boxes = []
    for track in msg.tracks:
        cx, cy, w, h = float(track.cx), float(track.cy), float(track.w), float(track.h)
        boxes.append(
            (int(track.id), (cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0))
        )
    return boxes


def resolve(
    tracks_bag: Path,
    reference_path: Path,
    tracks_topic: str,
    min_iou: float,
    max_lag_frames: int,
) -> dict:
    reference = json.loads(reference_path.read_text())
    ref_box, ref_t = first_scored_target(reference)

    reader = SequentialReader()
    reader.open(
        StorageOptions(uri=str(tracks_bag), storage_id="mcap"),
        ConverterOptions("cdr", "cdr"),
    )
    types = {t.name: t.type for t in reader.get_all_topics_and_types()}
    if tracks_topic not in types:
        return {"ok": False, "error": f"no {tracks_topic} in {tracks_bag}"}
    msg_cls = get_message(types[tracks_topic])

    per_frame: list[dict] = []
    frame_index = 0
    resolved: dict | None = None
    while reader.has_next():
        topic, raw, _ns = reader.read_next()
        if topic != tracks_topic:
            continue
        if frame_index >= max_lag_frames:
            break
        msg = deserialize_message(raw, msg_cls)
        best_iou, best_id = 0.0, None
        for track_id, box in track_boxes(msg):
            value = iou_xyxy(box, tuple(ref_box))
            if value > best_iou:
                best_iou, best_id = value, track_id
        per_frame.append(
            {"frame_index": frame_index, "best_iou": round(best_iou, 6), "best_track_id": best_id}
        )
        if resolved is None and best_id is not None and best_iou >= min_iou:
            resolved = {
                "resolved_track_id": int(best_id),
                "bootstrap_iou": round(float(best_iou), 6),
                "bootstrap_frame_index": frame_index,
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
        "reference_target_bbox_xyxy": ref_box,
        "min_iou_required": min_iou,
        "max_bootstrap_lag_frames": max_lag_frames,
        "frames_inspected": len(per_frame),
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
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    result = resolve(
        args.tracks_bag,
        args.physical_reference,
        args.tracks_topic,
        args.min_iou,
        args.max_bootstrap_lag_frames,
    )
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n")
    print(text)
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
