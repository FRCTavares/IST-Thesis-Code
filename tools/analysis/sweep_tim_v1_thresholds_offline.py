#!/usr/bin/env python3
"""Offline TIM-V1 threshold sweep.

This avoids ROS replay. It reads a recorded bag, feeds /target, /tracks, and
/camera/dashboard into TargetIdentityMemory, and evaluates the resulting
/target_memory-like output against interval annotations.

The goal is to test TIM thresholds deterministically on one bag.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import rclpy
from rclpy.serialization import deserialize_message
from rosbag2_py import ConverterOptions, SequentialReader, StorageOptions
from rosidl_runtime_py.utilities import get_message

from thesis_bringup.appearance_memory import AppearanceConfig, extract_hsv_upper_lower_feature
from thesis_bringup.target_memory import (
    BBox,
    CandidateTrack,
    TargetIdentityMemory,
    TargetMemoryConfig,
)


@dataclass
class AnnotationInterval:
    start_s: float
    end_s: float
    target_label: str
    target_visible: bool
    correct_target_track_id: int
    event_type: str
    notes: str


@dataclass
class OutputSample:
    t_s: float
    track_id: int
    state: str
    reason: str
    best_track_id: int
    best_total: float
    best_appearance: float
    best_appearance_used: bool
    appearance_features_valid: int
    num_tracks: int


def parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def parse_int_or_zero(value: Any) -> int:
    try:
        text = str(value).strip()
        if not text:
            return 0
        return int(float(text))
    except Exception:
        return 0


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return float("nan")


def load_annotations(path: Path) -> list[AnnotationInterval]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    out: list[AnnotationInterval] = []
    for row in rows:
        out.append(
            AnnotationInterval(
                start_s=float(row["start_s"]),
                end_s=float(row["end_s"]),
                target_label=str(row["target_label"]).strip(),
                target_visible=parse_bool(row["target_visible"]),
                correct_target_track_id=parse_int_or_zero(row.get("correct_target_track_id", "")),
                event_type=str(row.get("event_type", "")).strip(),
                notes=str(row.get("notes", "")).strip(),
            )
        )

    out.sort(key=lambda r: r.start_s)
    return out


def image_msg_to_bgr(msg: Any) -> np.ndarray | None:
    encoding = str(getattr(msg, "encoding", "")).lower()
    height = int(getattr(msg, "height", 0))
    width = int(getattr(msg, "width", 0))

    if height <= 0 or width <= 0:
        return None

    data = np.frombuffer(bytes(msg.data), dtype=np.uint8)

    if encoding in {"bgr8", "rgb8"}:
        expected = height * width * 3
        if data.size < expected:
            return None
        image = data[:expected].reshape((height, width, 3))
        if encoding == "rgb8":
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        return image.copy()

    return None


def clip_bbox(bbox: BBox, image_width: float, image_height: float) -> BBox:
    x1, y1, x2, y2 = bbox
    x1 = max(0.0, min(image_width, x1))
    y1 = max(0.0, min(image_height, y1))
    x2 = max(0.0, min(image_width, x2))
    y2 = max(0.0, min(image_height, y2))
    return (x1, y1, x2, y2)


def candidate_from_track(track: Any, image_width: float, image_height: float) -> CandidateTrack:
    cx = float(track.cx)
    cy = float(track.cy)
    w = float(track.w)
    h = float(track.h)

    bbox = clip_bbox(
        (
            cx - 0.5 * w,
            cy - 0.5 * h,
            cx + 0.5 * w,
            cy + 0.5 * h,
        ),
        image_width=image_width,
        image_height=image_height,
    )

    return CandidateTrack(
        track_id=int(track.id),
        bbox=bbox,
        score=float(track.score),
    )


def add_appearance(
    candidates: list[CandidateTrack],
    image_bgr: np.ndarray | None,
    appearance_cfg: AppearanceConfig,
) -> tuple[list[CandidateTrack], int]:
    if image_bgr is None:
        return candidates, 0

    out: list[CandidateTrack] = []
    valid = 0

    for c in candidates:
        feat = extract_hsv_upper_lower_feature(image_bgr, c.bbox, appearance_cfg)
        if feat is not None:
            valid += 1
        out.append(
            CandidateTrack(
                track_id=c.track_id,
                bbox=c.bbox,
                score=c.score,
                age=c.age,
                last_seen=c.last_seen,
                appearance=feat,
            )
        )

    return out, valid


def latest_sample_at(samples: list[OutputSample], t_s: float) -> OutputSample | None:
    # Samples are sorted by time. Linear scan is fine for these short bags.
    current = None
    for s in samples:
        if s.t_s <= t_s:
            current = s
        else:
            break
    return current


def evaluate_samples(
    samples: list[OutputSample],
    annotations: list[AnnotationInterval],
    step_s: float,
) -> dict[str, float]:
    correct = 0.0
    wrong = 0.0
    lost = 0.0
    target_not_visible = 0.0
    target_absent_but_output = 0.0
    no_target_selected = 0.0
    visible_target = 0.0

    for ann in annotations:
        t = ann.start_s
        while t < ann.end_s:
            dt = min(step_s, ann.end_s - t)
            sample = latest_sample_at(samples, t)
            output_id = sample.track_id if sample is not None else 0

            label = ann.target_label.upper()

            if label == "NO_TARGET_SELECTED":
                no_target_selected += dt
            elif not ann.target_visible:
                target_not_visible += dt
                if output_id != 0:
                    target_absent_but_output += dt
            else:
                visible_target += dt
                expected = int(ann.correct_target_track_id)

                if output_id == expected:
                    correct += dt
                elif output_id == 0:
                    lost += dt
                else:
                    wrong += dt

            t += dt

    return {
        "correct_duration_s": correct,
        "wrong_duration_s": wrong,
        "lost_duration_s": lost,
        "target_not_visible_duration_s": target_not_visible,
        "target_absent_but_output_duration_s": target_absent_but_output,
        "no_target_selected_duration_s": no_target_selected,
        "visible_target_duration_s": visible_target,
        "correct_ratio": correct / visible_target if visible_target > 0 else float("nan"),
        "wrong_ratio": wrong / visible_target if visible_target > 0 else float("nan"),
        "lost_ratio": lost / visible_target if visible_target > 0 else float("nan"),
    }


def run_threshold_case(
    bag_path: Path,
    threshold: float,
    image_width: float,
    image_height: float,
    annotations: list[AnnotationInterval],
    step_s: float,
    appearance_min_bbox_height: float,
) -> tuple[list[OutputSample], dict[str, float]]:
    cfg = TargetMemoryConfig(
        image_width=image_width,
        image_height=image_height,
        appearance_enabled=True,
        appearance_weight=0.12,
        appearance_min_similarity=0.35,
        appearance_update_alpha=0.10,
        appearance_ambiguous_only=True,
        accept_score_lost=threshold,
    )
    tim = TargetIdentityMemory(cfg)

    app_cfg = AppearanceConfig(min_bbox_height=appearance_min_bbox_height)

    reader = SequentialReader()
    reader.open(
        StorageOptions(uri=str(bag_path), storage_id="mcap"),
        ConverterOptions(input_serialization_format="cdr", output_serialization_format="cdr"),
    )

    topic_types = {topic.name: topic.type for topic in reader.get_all_topics_and_types()}
    msg_types = {
        topic: get_message(msg_type)
        for topic, msg_type in topic_types.items()
        if topic in {"/camera/dashboard", "/tracks", "/target"}
    }

    first_t_ns: int | None = None
    latest_image: np.ndarray | None = None
    latest_image_t_s: float | None = None

    pending_select_id: int | None = None
    last_mirrored_target_id: int | None = None

    outputs: list[OutputSample] = []

    while reader.has_next():
        topic, raw, t_ns = reader.read_next()

        if topic not in msg_types:
            continue

        if first_t_ns is None:
            first_t_ns = int(t_ns)

        t_s = (int(t_ns) - first_t_ns) / 1e9
        msg = deserialize_message(raw, msg_types[topic])

        if topic == "/camera/dashboard":
            latest_image = image_msg_to_bgr(msg)
            latest_image_t_s = t_s
            continue

        if topic == "/target":
            raw_id = int(getattr(msg, "id", 0))
            if raw_id > 0 and raw_id != last_mirrored_target_id:
                pending_select_id = raw_id
                last_mirrored_target_id = raw_id
            continue

        if topic == "/tracks":
            candidates = [
                candidate_from_track(track, image_width=image_width, image_height=image_height)
                for track in msg.tracks
            ]

            age_ok = (
                latest_image is not None
                and latest_image_t_s is not None
                and ((t_s - latest_image_t_s) * 1000.0) <= 250.0
            )

            if age_ok:
                candidates, valid_features = add_appearance(candidates, latest_image, app_cfg)
            else:
                valid_features = 0

            selected_candidate = None
            if pending_select_id is not None:
                for c in candidates:
                    if int(c.track_id) == int(pending_select_id):
                        selected_candidate = c
                        break

            if selected_candidate is not None:
                out = tim.select(selected_candidate)
                pending_select_id = None
            elif pending_select_id is not None and tim.state.value == "NO_TARGET":
                out = tim.update([])
                out.reason = f"pending_selection_track_not_visible:{pending_select_id}"
            else:
                out = tim.update(candidates)

            best = out.best_score
            target_id = int(out.target_track_id or 0) if out.visible and out.target_track_id is not None else 0

            outputs.append(
                OutputSample(
                    t_s=t_s,
                    track_id=target_id,
                    state=str(out.state.value),
                    reason=str(out.reason),
                    best_track_id=int(best.track_id) if best is not None else 0,
                    best_total=float(best.total) if best is not None else float("nan"),
                    best_appearance=float(best.appearance) if best is not None else float("nan"),
                    best_appearance_used=bool(best.appearance_used) if best is not None else False,
                    appearance_features_valid=int(valid_features),
                    num_tracks=len(candidates),
                )
            )

    stats = evaluate_samples(outputs, annotations, step_s=step_s)
    return outputs, stats


def write_case_csv(path: Path, samples: list[OutputSample]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    fields = [
        "t",
        "id",
        "state",
        "reason",
        "best_track_id",
        "best_total",
        "best_appearance",
        "best_appearance_used",
        "appearance_features_valid",
        "num_tracks",
    ]

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for s in samples:
            writer.writerow(
                {
                    "t": f"{s.t_s:.9f}",
                    "id": s.track_id,
                    "state": s.state,
                    "reason": s.reason,
                    "best_track_id": s.best_track_id,
                    "best_total": s.best_total,
                    "best_appearance": s.best_appearance,
                    "best_appearance_used": s.best_appearance_used,
                    "appearance_features_valid": s.appearance_features_valid,
                    "num_tracks": s.num_tracks,
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bag", type=Path)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=Path("reports/tim_v1_threshold_sweep"))
    parser.add_argument("--thresholds", nargs="+", type=float, default=[0.60, 0.55, 0.50, 0.45])
    parser.add_argument("--step-s", type=float, default=0.05)
    parser.add_argument("--image-width", type=float, default=640.0)
    parser.add_argument("--image-height", type=float, default=640.0)
    parser.add_argument("--appearance-min-bbox-height", type=float, default=30.0)
    args = parser.parse_args()

    annotations = load_annotations(args.annotations)

    bag_name = args.bag.name
    out_dir = args.out_dir / bag_name
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_rows: list[dict[str, Any]] = []

    for threshold in args.thresholds:
        samples, stats = run_threshold_case(
            bag_path=args.bag.resolve(),
            threshold=threshold,
            image_width=args.image_width,
            image_height=args.image_height,
            annotations=annotations,
            step_s=args.step_s,
            appearance_min_bbox_height=args.appearance_min_bbox_height,
        )

        tag = f"lost_{threshold:.2f}".replace(".", "_")
        write_case_csv(out_dir / f"{tag}_samples.csv", samples)

        states = Counter(s.state for s in samples)
        used = [s for s in samples if s.best_appearance_used]
        valid = [s for s in samples if s.appearance_features_valid > 0]
        first_reacq = next((s.t_s for s in samples if s.state == "REACQUIRED"), float("nan"))

        row = {
            "accept_score_lost": threshold,
            "correct_ratio": stats["correct_ratio"],
            "wrong_ratio": stats["wrong_ratio"],
            "lost_ratio": stats["lost_ratio"],
            "correct_duration_s": stats["correct_duration_s"],
            "wrong_duration_s": stats["wrong_duration_s"],
            "lost_duration_s": stats["lost_duration_s"],
            "LOCKED": states.get("LOCKED", 0),
            "UNCERTAIN": states.get("UNCERTAIN", 0),
            "LOST": states.get("LOST", 0),
            "REACQUIRED": states.get("REACQUIRED", 0),
            "appearance_used_rows": len(used),
            "valid_appearance_rows": len(valid),
            "first_reacq_t": first_reacq,
        }
        summary_rows.append(row)

    summary_csv = out_dir / "summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as f:
        fields = list(summary_rows[0].keys())
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(summary_rows)

    lines = []
    lines.append("# TIM-V1 Offline Threshold Sweep")
    lines.append("")
    lines.append(f"- Bag: `{args.bag}`")
    lines.append(f"- Annotations: `{args.annotations}`")
    lines.append("")
    lines.append("| accept_score_lost | correct ratio | wrong ratio | lost ratio | correct [s] | wrong [s] | lost [s] | LOCKED | LOST | REACQUIRED | appearance used | first reacq t |")
    lines.append("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in summary_rows:
        lines.append(
            f"| {row['accept_score_lost']:.2f} | "
            f"{row['correct_ratio']:.3f} | "
            f"{row['wrong_ratio']:.3f} | "
            f"{row['lost_ratio']:.3f} | "
            f"{row['correct_duration_s']:.3f} | "
            f"{row['wrong_duration_s']:.3f} | "
            f"{row['lost_duration_s']:.3f} | "
            f"{row['LOCKED']} | "
            f"{row['LOST']} | "
            f"{row['REACQUIRED']} | "
            f"{row['appearance_used_rows']} | "
            f"{row['first_reacq_t']:.3f} |"
        )

    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[ok] wrote {out_dir / 'summary.md'}")
    print(f"[ok] wrote {summary_csv}")


if __name__ == "__main__":
    main()
