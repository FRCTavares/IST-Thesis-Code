#!/usr/bin/env python3
"""Score one frozen VisDrone sequence with canonical ByteTrack + TIM-MARS."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_visdrone_selected_person_corpus import load_sequence_rows  # noqa: E402
from evaluate_visdrone_selected_person import AttributionConfig, evaluate_episode  # noqa: E402
from resolve_episode_initialization import resolve_initialization  # noqa: E402
from score_raw_tracker_sequence import validate_raw_replay  # noqa: E402
from shared_detector_cache import read_committed_frozen_inputs  # noqa: E402
from tim_mars_episode import tim_mars_authority_maps  # noqa: E402
from write_raw_tracker_replay import ARM_CONFIGS, sha256_file  # noqa: E402
from write_shared_detector_cache import image_paths_by_source_frame, write_cache_once  # noqa: E402


def score_tim_mars_episodes(
    *,
    split: str,
    sequence_name: str,
    episodes: list[dict[str, Any]],
    gt_rows: list[Any],
    tracker_frames: list[dict[str, Any]],
    initialization_rules: dict[str, Any],
    evaluation_rules: dict[str, Any],
    runtime_factory: Any,
    image_for_frame: Any,
) -> list[dict[str, Any]]:
    """Use ByteTrack initialization, then run one fresh TIM memory per episode."""
    source_indices = [int(frame["normalized_frame_index"]) for frame in tracker_frames]
    results = []
    for episode in episodes:
        if episode["split"] != split or episode["sequence_name"] != sequence_name:
            raise ValueError("episode belongs to another sequence")
        identity = int(episode["dataset_identity"])
        selection = int(episode["selection_frame_index"])
        target_indices = [
            int(row.normalized_frame_index) for row in gt_rows
            if int(row.identity) == identity and bool(row.include_as_person_candidate)
            and int(row.normalized_frame_index) >= selection
        ]
        if not target_indices:
            raise ValueError("frozen episode has no target GT after selection")
        last_target = max(target_indices)
        episode_frames = [
            frame for frame in tracker_frames
            if selection <= int(frame["normalized_frame_index"]) <= last_target
        ]
        if [int(frame["normalized_frame_index"]) for frame in episode_frames] != [
            index for index in source_indices if selection <= index <= last_target
        ]:
            raise ValueError("episode source frame domain mismatch")
        initialization = resolve_initialization(
            episode=episode,
            gt_rows=gt_rows,
            tracker_frames=episode_frames,
            minimum_match_iou=float(initialization_rules["minimum_match_iou"]),
            minimum_match_margin=float(initialization_rules["minimum_match_margin"]),
            confirmation_frames=int(initialization_rules["confirmation_frames"]),
        )
        boxes, ids = tim_mars_authority_maps(
            tracker_frames=episode_frames,
            initialization=initialization,
            runtime_factory=runtime_factory,
            image_for_frame=image_for_frame,
        )
        evaluation = evaluate_episode(
            split=split,
            sequence_name=sequence_name,
            dataset_identity=identity,
            selection_frame_index=selection,
            source_frame_indices=source_indices,
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
    parser.add_argument("--split", choices=("train", "val"), required=True)
    parser.add_argument("--sequence", required=True)
    parser.add_argument("--dataset-root", type=Path, default=ROOT / "data/datasets/external/visdrone_mot")
    parser.add_argument("--cache-root", type=Path, default=ROOT / "artifacts/reports/p125_shared_detector_cache")
    parser.add_argument("--tracker-root", type=Path, default=ROOT / "artifacts/reports/p125_raw_tracker_replay")
    parser.add_argument("--output-root", type=Path, default=ROOT / "artifacts/reports/p125_scored_tim_mars")
    args = parser.parse_args()

    frozen = read_committed_frozen_inputs(
        repository_root=ROOT,
        protocol_path=ROOT / "docs/data/external_benchmark_v2/visdrone_selected_person_protocol_v1.json",
        manifest_path=ROOT / "docs/data/external_benchmark_v2/visdrone_gt_only_episode_manifest_v1.json",
    )
    protocol = frozen["protocol"]
    manifest = frozen["manifest"]
    arm = next((item for item in protocol["architectures_planned"]
                if item["id"] == "bytetrack_tim_mars"), None)
    canonical_relative = "ros2_ws/src/thesis_bringup/config/tim_mars_canonical.yaml"
    if (arm is None or arm["candidate_stream"] != "bytetrack"
            or arm["config"] != canonical_relative):
        raise ValueError("TIM-MARS arm differs from frozen canonical config")
    inventory = [entry for entry in manifest["sequence_inventory"]
                 if entry["split"] == args.split and entry["sequence_name"] == args.sequence]
    if len(inventory) != 1:
        raise ValueError("sequence is absent or duplicated in frozen manifest")
    entry = inventory[0]
    image_paths = image_paths_by_source_frame(
        args.dataset_root / args.split / "sequences" / args.sequence
    )
    source_numbers = sorted(image_paths)
    if (len(source_numbers) != entry["image_frame_count"]
            or source_numbers[0] != entry["first_source_frame"]
            or source_numbers[-1] != entry["last_source_frame"]):
        raise ValueError("source images differ from frozen inventory")
    annotation_path = args.dataset_root / args.split / "annotations" / f"{args.sequence}.txt"
    if sha256_file(annotation_path) != entry["annotation_sha256"]:
        raise ValueError("annotation differs from frozen inventory")
    hashes = protocol["pre_result_implementation_hashes_draft"]
    for relative in (
        ARM_CONFIGS["bytetrack_raw"],
        "models/reid/mars-small128.pb",
        canonical_relative,
        "ros2_ws/src/thesis_bringup/thesis_bringup/tim_mars/runtime.py",
        "ros2_ws/src/thesis_bringup/thesis_bringup/tim_mars/target_memory.py",
        "tools/experiments/run_deterministic_tim_replay.py",
    ):
        if sha256_file(ROOT / relative) != hashes[relative]:
            raise ValueError(f"frozen implementation hash mismatch: {relative}")
    cache_path = args.cache_root / args.split / f"{args.sequence}.json"
    replay_path = args.tracker_root / "bytetrack_raw" / args.split / f"{args.sequence}.json"
    replay_sha = sha256_file(replay_path)
    replay = json.loads(replay_path.read_text())
    frames = validate_raw_replay(
        replay,
        arm="bytetrack_raw",
        split=args.split,
        sequence_name=args.sequence,
        source_frame_numbers=source_numbers,
        protocol_sha256=frozen["protocol_sha256"],
        manifest_sha256=frozen["manifest_sha256"],
        freeze_commit=frozen["freeze_commit"],
        detector_cache_sha256=sha256_file(cache_path),
        tracker_config_sha256=hashes[ARM_CONFIGS["bytetrack_raw"]],
    )
    rows = load_sequence_rows(
        split=args.split, sequence_name=args.sequence,
        annotation_path=annotation_path,
        image_width=int(entry["image_width"]), image_height=int(entry["image_height"]),
    )
    sys.path.insert(0, str(ROOT / "tools/analysis"))
    sys.path.insert(0, str(ROOT / "ros2_ws/src/thesis_bringup"))
    sys.path.insert(0, str(ROOT / "ros2_ws/src/thesis_tracker"))
    import cv2
    sys.path.insert(0, str(ROOT / "tools/experiments"))
    from run_deterministic_tim_replay import build_runtime, load_canonical_parameters
    from thesis_bringup.tim_mars.runtime import TimMarsRuntime

    model_path = ROOT / "models/reid/mars-small128.pb"
    canonical = load_canonical_parameters(ROOT / canonical_relative)
    if not bool(canonical.get("appearance_enabled", True)):
        raise ValueError("canonical TIM-MARS appearance must be enabled")
    base = build_runtime(canonical, argparse.Namespace(
        appearance_enabled=None,
        appearance_request_policy=None,
        appearance_compute_min_interval_ms=None,
        image_width=float(entry["image_width"]),
        image_height=float(entry["image_height"]),
        tracks_are_normalized=False,
        selected_track_id=0,
        model=model_path,
    ))
    def runtime_factory(selected_id: int) -> TimMarsRuntime:
        return TimMarsRuntime(
            config=replace(
                base.config,
                memory=copy.deepcopy(base.config.memory),
                selected_track_id=selected_id,
            ),
            mars_backend=base.mars_backend,
        )
    def image_for_frame(frame: dict[str, Any]) -> Any:
        source_number = int(frame["source_frame_number"])
        image = cv2.imread(str(image_paths[source_number]), cv2.IMREAD_COLOR)
        if image is None or image.shape[:2] != (int(entry["image_height"]), int(entry["image_width"])):
            raise ValueError(f"unreadable or mismatched source image {source_number}")
        return image

    episodes = [episode for episode in manifest["episodes"]
                if episode["split"] == args.split and episode["sequence_name"] == args.sequence]
    results = score_tim_mars_episodes(
        split=args.split, sequence_name=args.sequence, episodes=episodes,
        gt_rows=rows, tracker_frames=frames,
        initialization_rules=protocol["initialization_draft"],
        evaluation_rules=protocol["evaluation_draft"],
        runtime_factory=runtime_factory, image_for_frame=image_for_frame,
    )
    document = {
        "schema": "p125_scored_tim_mars_sequence_v1",
        "arm": "bytetrack_tim_mars", "split": args.split,
        "sequence_name": args.sequence,
        "protocol_sha256": frozen["protocol_sha256"],
        "manifest_sha256": frozen["manifest_sha256"],
        "freeze_commit": frozen["freeze_commit"],
        "bytetrack_replay_sha256": replay_sha,
        "tim_mars_config_sha256": hashes[canonical_relative],
        "episode_count": len(results), "episodes": results,
    }
    output_path = args.output_root / args.split / f"{args.sequence}.json"
    digest = write_cache_once(output_path, document)
    print(json.dumps({"output": str(output_path), "sha256": digest,
                      "episode_count": len(results)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
