#!/usr/bin/env python3
"""Join retained TIM status, crop provenance and physical-v2 frame evidence.

Frame counts are diagnostic. Duration metrics remain owned by the unchanged
physical-v2 evaluator, with its reference breakpoints and output-age contract.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import fields
import json
from math import hypot
from pathlib import Path
import sys

import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ros2_ws/src/thesis_bringup"))

from physical_target_bbox_evaluation_v2 import (  # noqa: E402
    REF_COVERED, classify_identity_stage_a, resolve_reference_interval,
)
from physical_target_reference_v2 import load_physical_reference  # noqa: E402
from physical_target_reference import IDENTITY_TARGET, IDENTITY_WRONG_PERSON  # noqa: E402
from thesis_bringup.tim_mars.appearance_attachment import (  # noqa: E402
    AppearanceAttachmentConfig, AppearanceAttachmentState,
    reconcile_appearance_track_lifecycle,
)
from thesis_bringup.tim_mars.geometry_scoring import bbox_iou  # noqa: E402
from thesis_bringup.tim_mars.target_memory import TargetIdentityMemory  # noqa: E402
from thesis_bringup.tim_mars.types import (  # noqa: E402
    CandidateScore, CandidateTrack, TargetMemoryConfig,
)


def bbox(track):
    return (track.cx - track.w / 2, track.cy - track.h / 2,
            track.cx + track.w / 2, track.cy + track.h / 2)


def physical(reference, time, box):
    resolved = resolve_reference_interval(reference.samples, time)
    if resolved.condition != REF_COVERED:
        return {"identity": resolved.condition}
    return {
        "identity": classify_identity_stage_a(
            identity_context=resolved.identity_context,
            target_bbox_xyxy=resolved.target_bbox_xyxy,
            distractor_bboxes_xyxy=[d.bbox_xyxy for d in resolved.distractors],
            output_bbox_xyxy=box,
        ),
        "target_iou": bbox_iou(box, resolved.target_bbox_xyxy),
        "distractor_iou": max((bbox_iou(box, d.bbox_xyxy)
                               for d in resolved.distractors), default=0.),
    }


def spatial(source, current, width, height):
    centre = hypot((current[0] + current[2] - source[0] - source[2]) / 2,
                   (current[1] + current[3] - source[1] - source[3]) / 2)
    a = (source[2] - source[0]) * (source[3] - source[1])
    b = (current[2] - current[0]) * (current[3] - current[1])
    return {"centre_distance_norm": centre / hypot(width, height),
            "scale_ratio": min(a, b) / max(a, b) if min(a, b) > 0 else 0.,
            "bbox_iou": bbox_iou(source, current)}


def source_reference_time(output_time_s, track_timestamp_ns, image_timestamp_ns):
    """Translate a causal image offset without mixing replay and capture epochs."""
    return output_time_s - (track_timestamp_ns - image_timestamp_ns) / 1e9


def analyse(bag, reference_path, out):
    metadata = json.loads((bag / "tim_replay_metadata.json").read_text())
    params = yaml.safe_load((bag / "tim_mars_canonical_config.yaml").read_text())
    params = params["target_memory_mars_node"]["ros__parameters"]
    names = {f.name for f in fields(TargetMemoryConfig)}
    values = {k: v for k, v in params.items() if k in names}
    width, height = (metadata["runtime"]["image_width"], metadata["runtime"]["image_height"])
    values.update(image_width=width, image_height=height)
    memory = TargetIdentityMemory(TargetMemoryConfig(**values))
    attachment = AppearanceAttachmentConfig(
        True, params["appearance_max_image_age_ms"],
        params["appearance_compute_min_interval_ms"], params["appearance_cache_ttl_ms"],
        params["appearance_cache_max_centre_distance_norm"],
        params["appearance_cache_min_scale_ratio"],
    )
    lifecycle = AppearanceAttachmentState()
    reference = load_physical_reference(reference_path)
    reader = rosbag2_py.SequentialReader()
    reader.open(rosbag2_py.StorageOptions(uri=str(bag), storage_id="mcap"),
                rosbag2_py.ConverterOptions("", ""))
    types = {topic.name: get_message(topic.type) for topic in reader.get_all_topics_and_types()}
    timeline, boxes_by_frame, last_boxes = {}, {}, {}
    counts, supported, reasons, updates = Counter(), Counter(), Counter(), Counter()
    wrong, transitions = [], []
    previous_state = None
    origin = None
    out.mkdir(parents=True, exist_ok=True)
    with (out / "frames.jsonl").open("w") as stream:
        while reader.has_next():
            topic, payload, timestamp = reader.read_next()
            origin = timestamp if origin is None else origin
            if topic not in {"/tracks", "/target_memory_mars/status"}:
                continue
            message = deserialize_message(payload, types[topic])
            if topic == "/tracks":
                boxes_by_frame[int(message.frame_id)] = {
                    int(track.id): bbox(track) for track in message.tracks
                }
                continue
            status = json.loads(message.data)
            time = (timestamp - origin) / 1e9
            track_ns = status["track_timestamp_ns"]
            current = boxes_by_frame.get(status["frame_id"], {})
            candidates = [CandidateTrack(track_id, box) for track_id, box in current.items()]
            reconcile_appearance_track_lifecycle(
                config=attachment, state=lifecycle, candidates=candidates,
                frame_id=status["frame_id"], image_width=width, image_height=height,
            )
            timeline[track_ns] = (status, current, time)
            score_fields = {f.name for f in fields(CandidateScore)}
            scores = [CandidateScore(**{k: v for k, v in score.items() if k in score_fields})
                      for score in status["all_scores"]]
            candidate_rows = []
            for track_id, box in current.items():
                row = {"track_id": track_id, "bbox": box,
                       "physical": physical(reference, time, box),
                       "frame_generation": lifecycle.frame_generation,
                       "track_generation": lifecycle.track_generation_by_id.get(track_id)}
                score = next((s for s in status["all_scores"] if s["track_id"] == track_id), None)
                row["score"] = score
                age = status.get("appearance_embedding_age_ms_by_track_id", {}).get(str(track_id))
                row["embedding_age_ms"] = age
                row["appearance_source"] = "none" if age is None else "fresh" if age == 0 else "cache"
                if age is not None:
                    embedded_ns = track_ns - round(age * 1e6)
                    source = timeline.get(embedded_ns)
                    if source is not None and track_id in source[1]:
                        source_status, source_boxes, source_time = source
                        source_box = source_boxes[track_id]
                        row.update(source_frame_id=source_status["frame_id"], source_bbox=source_box,
                                   source_image_timestamp_ns=source_status["selected_image_timestamp_ns"])
                        row["source_displacement"] = spatial(source_box, box, width, height)
                        row["source_physical"] = physical(
                            reference, source_reference_time(
                                source_time, source_status["track_timestamp_ns"],
                                source_status["selected_image_timestamp_ns"],
                            ),
                            source_box,
                        )
                if track_id in last_boxes:
                    row["consecutive_displacement"] = spatial(last_boxes[track_id], box, width, height)
                challenger = memory._nearby_identity_challenger(
                    selected=CandidateTrack(track_id, box), candidates=candidates, all_scores=scores,
                )
                row["challenger_track_id"] = challenger.track_id if challenger else None
                row["challenger_geometry_score"] = challenger.geometry_score if challenger else None
                if not status["visible"] and row["physical"]["identity"] == IDENTITY_TARGET:
                    reason = status["reason"].split(":")[0]
                    reasons[reason] += 1
                    if score and score["appearance_raw"] >= values["id_switch_min_appearance_similarity"] and not score["hard_negative_reject"]:
                        supported[reason] += 1
                candidate_rows.append(row)
            selected = next((row for row in candidate_rows if row["track_id"] == status["candidate_track_id"]), None)
            record = {"time_s": time, "status": status, "candidates": candidate_rows}
            if status["visible"] and selected and selected["physical"]["identity"] == IDENTITY_WRONG_PERSON:
                wrong.append(record)
            if status["positive_memory_updated"] and selected:
                updates["current_box:" + selected["physical"]["identity"]] += 1
                updates["source_crop:" + selected.get("source_physical", {}).get("identity", "unresolved_provenance")] += 1
                updates["source:" + selected["appearance_source"]] += 1
            if previous_state != status["state"]:
                transitions.append({"time_s": time, "from": previous_state,
                                    "to": status["state"], "reason": status["reason"],
                                    "track_id": status["candidate_track_id"]})
            previous_state = status["state"]
            last_boxes = current
            counts[status["state"]] += 1
            stream.write(json.dumps(record, sort_keys=True) + "\n")
    summary = {"bag": str(bag), "reference": str(reference_path),
               "diagnostic_only_frame_counts": True, "states": dict(counts),
               "suppressed_correct_candidates": dict(reasons),
               "suppressed_correct_candidates_with_strong_support": dict(supported),
               "positive_memory_updates": dict(updates),
               "wrong_authority_frames": wrong, "transitions": transitions}
    (out / "audit.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(out, "wrong frames", len(wrong), "memory", dict(updates), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bag", type=Path)
    parser.add_argument("--physical-reference", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    analyse(args.bag, args.physical_reference, args.out)


if __name__ == "__main__":
    main()
