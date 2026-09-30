#!/usr/bin/env python3
"""Score all frozen selected-person episodes in one raw tracker sequence."""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_visdrone_selected_person_corpus import load_sequence_rows  # noqa: E402
from evaluate_visdrone_selected_person import (  # noqa: E402
    AttributionConfig,
    evaluate_episode,
)
from resolve_episode_initialization import (  # noqa: E402
    raw_authority_maps,
    resolve_initialization,
)
from shared_detector_cache import read_committed_frozen_inputs  # noqa: E402
from replay_shared_detector_cache import LOGICAL_FRAME_TICK_NS  # noqa: E402
from write_raw_tracker_replay import ARM_CONFIGS, sha256_file  # noqa: E402
from write_shared_detector_cache import (  # noqa: E402
    image_paths_by_source_frame,
    write_cache_once,
)


def validate_raw_replay(
    replay: dict[str, Any],
    *,
    arm: str,
    split: str,
    sequence_name: str,
    source_frame_numbers: Sequence[int],
    protocol_sha256: str,
    manifest_sha256: str,
    freeze_commit: str,
    detector_cache_sha256: str,
    tracker_config_sha256: str,
) -> list[dict[str, Any]]:
    """Reject stale, cross-arm or incomplete tracker replay documents."""
    if replay.get("schema") != "p125_raw_tracker_sequence_replay_v1":
        raise ValueError("unexpected raw tracker replay schema")
    for key, expected in (
        ("arm", arm),
        ("split", split),
        ("sequence_name", sequence_name),
        ("protocol_sha256", protocol_sha256),
        ("manifest_sha256", manifest_sha256),
        ("freeze_commit", freeze_commit),
        ("detector_cache_sha256", detector_cache_sha256),
        ("tracker_config_sha256", tracker_config_sha256),
    ):
        if replay.get(key) != expected:
            raise ValueError(f"raw tracker replay {key} mismatch")
    if (
        replay.get("logical_frame_tick_ns") != LOGICAL_FRAME_TICK_NS
        or replay.get("logical_tick_is_physical_time") is not False
    ):
        raise ValueError("raw tracker replay logical frame clock mismatch")
    frames = replay.get("frames")
    if not isinstance(frames, list) or replay.get("frame_count") != len(frames):
        raise ValueError("raw tracker replay frame count mismatch")
    if [frame["source_frame_number"] for frame in frames] != list(source_frame_numbers):
        raise ValueError("raw tracker replay source frame domain mismatch")
    for frame in frames:
        if (
            frame["normalized_frame_index"] != frame["source_frame_number"] - 1
            or frame.get("logical_frame_stamp_ns")
            != frame["source_frame_number"] * LOGICAL_FRAME_TICK_NS
        ):
            raise ValueError("raw tracker replay frame mapping mismatch")
        tracks = frame.get("tracks")
        if not isinstance(tracks, list):
            raise ValueError("raw tracker replay tracks must be a list")
        seen_ids: set[int] = set()
        for track in tracks:
            identity = track.get("track_id")
            box = track.get("bbox_xyxy")
            score = track.get("score")
            if (
                not isinstance(identity, int)
                or identity <= 0
                or identity in seen_ids
                or not isinstance(box, list)
                or len(box) != 4
                or not all(isinstance(value, (int, float)) and math.isfinite(value) for value in box)
                or box[2] <= box[0]
                or box[3] <= box[1]
                or not isinstance(score, (int, float))
                or not math.isfinite(score)
            ):
                raise ValueError("invalid raw tracker replay track")
            seen_ids.add(identity)
    return frames


def score_raw_episodes(
    *,
    split: str,
    sequence_name: str,
    episodes: Sequence[dict[str, Any]],
    gt_rows: Sequence[Any],
    tracker_frames: Sequence[dict[str, Any]],
    initialization_rules: dict[str, Any],
    evaluation_rules: dict[str, Any],
) -> list[dict[str, object]]:
    """Apply one frozen episode list without selecting from outcomes."""
    source_frames = [
        int(frame["normalized_frame_index"]) for frame in tracker_frames
    ]
    results: list[dict[str, object]] = []
    for episode in episodes:
        if episode["split"] != split or episode["sequence_name"] != sequence_name:
            raise ValueError("episode does not belong to requested source sequence")
        initialization = resolve_initialization(
            episode=episode,
            gt_rows=gt_rows,
            tracker_frames=tracker_frames,
            minimum_match_iou=float(initialization_rules["minimum_match_iou"]),
            minimum_match_margin=float(initialization_rules["minimum_match_margin"]),
            confirmation_frames=int(initialization_rules["confirmation_frames"]),
        )
        boxes, ids = raw_authority_maps(
            tracker_frames=tracker_frames,
            initialization=initialization,
        )
        evaluation = evaluate_episode(
            split=split,
            sequence_name=sequence_name,
            dataset_identity=int(episode["dataset_identity"]),
            selection_frame_index=int(episode["selection_frame_index"]),
            source_frame_indices=source_frames,
            gt_rows=gt_rows,
            output_bboxes_by_frame=boxes,
            output_tracker_ids_by_frame=ids,
            config=AttributionConfig(
                person_iou_threshold=float(evaluation_rules["target_iou_threshold"]),
                unique_iou_margin=float(evaluation_rules["unique_iou_margin"]),
                ambiguous_region_output_coverage=float(
                    evaluation_rules["ambiguous_region_output_coverage_threshold"]
                ),
            ),
        )
        results.append({
            "episode": episode,
            "initialization": asdict(initialization),
            "evaluation": evaluation,
        })
    return results


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
        "--tracker-root", type=Path,
        default=ROOT / "artifacts" / "reports" / "p125_raw_tracker_replay",
    )
    parser.add_argument(
        "--output-root", type=Path,
        default=ROOT / "artifacts" / "reports" / "p125_scored_raw",
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
    image_paths = image_paths_by_source_frame(
        args.dataset_root / args.split / "sequences" / args.sequence
    )
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
    rows = load_sequence_rows(
        split=args.split,
        sequence_name=args.sequence,
        annotation_path=annotation_path,
        image_width=int(entry["image_width"]),
        image_height=int(entry["image_height"]),
    )
    config_relative = ARM_CONFIGS[args.arm]
    config_sha = sha256_file(ROOT / config_relative)
    if config_sha != protocol["pre_result_implementation_hashes_draft"][config_relative]:
        raise ValueError("tracker config differs from frozen protocol")
    detector_cache_path = args.cache_root / args.split / f"{args.sequence}.json"
    replay_path = args.tracker_root / args.arm / args.split / f"{args.sequence}.json"
    replay_sha = sha256_file(replay_path)
    replay = json.loads(replay_path.read_text())
    frames = validate_raw_replay(
        replay,
        arm=args.arm,
        split=args.split,
        sequence_name=args.sequence,
        source_frame_numbers=source_numbers,
        protocol_sha256=frozen["protocol_sha256"],
        manifest_sha256=frozen["manifest_sha256"],
        freeze_commit=frozen["freeze_commit"],
        detector_cache_sha256=sha256_file(detector_cache_path),
        tracker_config_sha256=config_sha,
    )
    episodes = [
        episode for episode in manifest["episodes"]
        if episode["split"] == args.split
        and episode["sequence_name"] == args.sequence
    ]
    results = score_raw_episodes(
        split=args.split,
        sequence_name=args.sequence,
        episodes=episodes,
        gt_rows=rows,
        tracker_frames=frames,
        initialization_rules=protocol["initialization_draft"],
        evaluation_rules=protocol["evaluation_draft"],
    )
    document = {
        "schema": "p125_scored_raw_tracker_sequence_v1",
        "arm": args.arm,
        "split": args.split,
        "sequence_name": args.sequence,
        "protocol_sha256": frozen["protocol_sha256"],
        "manifest_sha256": frozen["manifest_sha256"],
        "freeze_commit": frozen["freeze_commit"],
        "tracker_replay_sha256": replay_sha,
        "episode_count": len(results),
        "episodes": results,
    }
    output_path = args.output_root / args.arm / args.split / f"{args.sequence}.json"
    digest = write_cache_once(output_path, document)
    print(json.dumps({
        "output": str(output_path),
        "sha256": digest,
        "episode_count": len(results),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
