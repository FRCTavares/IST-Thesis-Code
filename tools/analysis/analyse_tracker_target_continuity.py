#!/usr/bin/env python3
"""Identity-independent raw-tracker diagnostics for the ByteTrack/TIM-MARS
sensitivity experiment.

Given a deterministic tracker-replay bag (``/tracks``) and the frozen
physical-target reference, this computes compact diagnostics about how the raw
tracker represents the physical target over time, without using any
tracker-ID annotation oracle:

* which tracker IDs spatially represent the physical target, over time;
* target ID switches and contiguous target-ID fragments;
* target-visible coverage (fraction of scored frames with a matching track);
* number of tracks spatially matching the target (ambiguity);
* false continuation while the physical target is annotated absent;
* disappearance delay after the target becomes absent.

Time alignment uses the track message source timestamp relative to the first
track message, matched to the nearest physical-reference sample.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rclpy.serialization import deserialize_message
from rosbag2_py import ConverterOptions, SequentialReader, StorageOptions
from rosidl_runtime_py.utilities import get_message


def iou_xyxy(a, b) -> float:
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


def load_reference_samples(path: Path) -> list[dict]:
    ref = json.loads(path.read_text())
    samples = sorted(ref["samples"], key=lambda s: float(s["t_s"]))
    return samples


def nearest_sample(samples: list[dict], t_s: float, tolerance_s: float) -> dict | None:
    best = None
    best_dt = tolerance_s
    lo, hi = 0, len(samples) - 1
    # Linear scan is fine for a few thousand samples.
    for sample in samples:
        dt = abs(float(sample["t_s"]) - t_s)
        if dt <= best_dt:
            best_dt = dt
            best = sample
    return best


def read_track_frames(bag: Path, tracks_topic: str):
    reader = SequentialReader()
    reader.open(
        StorageOptions(uri=str(bag), storage_id="mcap"),
        ConverterOptions("cdr", "cdr"),
    )
    types = {t.name: t.type for t in reader.get_all_topics_and_types()}
    if tracks_topic not in types:
        raise SystemExit(f"no {tracks_topic} in {bag}")
    msg_cls = get_message(types[tracks_topic])
    frames = []
    while reader.has_next():
        topic, raw, _ns = reader.read_next()
        if topic != tracks_topic:
            continue
        msg = deserialize_message(raw, msg_cls)
        stamp = int(getattr(msg, "src_stamp_ns", 0)) or int(_ns)
        boxes = []
        for track in msg.tracks:
            cx, cy, w, h = float(track.cx), float(track.cy), float(track.w), float(track.h)
            boxes.append(
                (int(track.id), (cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0))
            )
        frames.append((stamp, boxes))
    return frames


def analyse(
    bag: Path,
    reference_path: Path,
    tracks_topic: str,
    match_iou: float,
    tolerance_s: float,
) -> dict:
    samples = load_reference_samples(reference_path)
    frames = read_track_frames(bag, tracks_topic)
    if not frames:
        return {"ok": False, "error": "no track frames"}

    t0 = frames[0][0]
    dt_nominal = 0.0
    if len(frames) > 1:
        dt_nominal = (frames[-1][0] - frames[0][0]) / 1e9 / max(1, len(frames) - 1)

    matched_sequence: list[int | None] = []
    scored_frames = 0
    scored_matched_frames = 0
    ambiguity_counts: list[int] = []
    absence_frames = 0
    absence_false_continuation_frames = 0
    last_target_box: tuple[float, float, float, float] | None = None
    disappearance_delay_s: float | None = None
    absent_started_t: float | None = None

    for stamp, boxes in frames:
        t_s = (stamp - t0) / 1e9
        sample = nearest_sample(samples, t_s, tolerance_s)
        if sample is None:
            continue
        state = sample.get("identity_state")
        if state == "present_scored" and sample.get("target_bbox_xyxy"):
            scored_frames += 1
            target_box = tuple(sample["target_bbox_xyxy"])
            last_target_box = target_box
            absent_started_t = None
            best_iou, best_id, matching = 0.0, None, 0
            for track_id, box in boxes:
                v = iou_xyxy(box, target_box)
                if v >= match_iou:
                    matching += 1
                if v > best_iou:
                    best_iou, best_id = v, track_id
            ambiguity_counts.append(matching)
            if best_id is not None and best_iou >= match_iou:
                scored_matched_frames += 1
                matched_sequence.append(int(best_id))
            else:
                matched_sequence.append(None)
        elif state == "absent":
            absence_frames += 1
            if absent_started_t is None:
                absent_started_t = t_s
            still_there = False
            if last_target_box is not None:
                for _track_id, box in boxes:
                    if iou_xyxy(box, last_target_box) >= match_iou:
                        still_there = True
                        break
            if still_there:
                absence_false_continuation_frames += 1
            elif disappearance_delay_s is None and absent_started_t is not None:
                disappearance_delay_s = round(max(0.0, t_s - absent_started_t), 6)

    present_matched = [m for m in matched_sequence if m is not None]
    distinct_ids = sorted(set(present_matched))
    id_switches = 0
    fragments = 0
    prev = None
    for m in present_matched:
        if m != prev:
            fragments += 1
            if prev is not None:
                id_switches += 1
        prev = m

    return {
        "ok": True,
        "tracks_topic": tracks_topic,
        "match_iou": match_iou,
        "nominal_frame_dt_s": round(dt_nominal, 6),
        "track_frames": len(frames),
        "scored_frames": scored_frames,
        "target_visible_coverage_fraction": round(
            scored_matched_frames / scored_frames, 6
        ) if scored_frames else 0.0,
        "target_matched_track_ids": distinct_ids,
        "target_matched_track_id_count": len(distinct_ids),
        "target_id_switch_count": id_switches,
        "target_track_fragment_count": fragments,
        "tracks_matching_target_mean": round(
            sum(ambiguity_counts) / len(ambiguity_counts), 6
        ) if ambiguity_counts else 0.0,
        "tracks_matching_target_max": max(ambiguity_counts) if ambiguity_counts else 0,
        "absence_frames": absence_frames,
        "absence_frames_with_false_continuation": absence_false_continuation_frames,
        "false_continuation_during_absence_s": round(
            absence_false_continuation_frames * dt_nominal, 6
        ),
        "disappearance_delay_s": disappearance_delay_s,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tracks_bag", type=Path)
    parser.add_argument("--physical-reference", type=Path, required=True)
    parser.add_argument("--tracks-topic", default="/tracks")
    parser.add_argument("--match-iou", type=float, default=0.3)
    parser.add_argument("--tolerance-s", type=float, default=0.05)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    result = analyse(
        args.tracks_bag,
        args.physical_reference,
        args.tracks_topic,
        args.match_iou,
        args.tolerance_s,
    )
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n")
    print(text)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
