#!/usr/bin/env python3
"""Run the frozen Issue #125 sequence pipeline with resumable stage outputs."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from shared_detector_cache import read_committed_frozen_inputs  # noqa: E402

RAW_ARMS = ("sort_raw", "bytetrack_raw", "ocsort_raw", "deepsort_raw")


def stages(split: str, sequence: str) -> list[tuple[str, Path, list[str]]]:
    prefix = ["--split", split, "--sequence", sequence]
    reports = ROOT / "artifacts/reports"
    result = [
        (
            "detector_cache",
            reports / "p125_shared_detector_cache" / split / f"{sequence}.json",
            ["write_shared_detector_cache.py", *prefix],
        )
    ]
    for arm in RAW_ARMS:
        result.append((
            f"{arm}_replay",
            reports / "p125_raw_tracker_replay" / arm / split / f"{sequence}.json",
            ["write_raw_tracker_replay.py", "--arm", arm, *prefix],
        ))
    for arm in RAW_ARMS:
        result.append((
            f"{arm}_score",
            reports / "p125_scored_raw" / arm / split / f"{sequence}.json",
            ["score_raw_tracker_sequence.py", "--arm", arm, *prefix],
        ))
    result.extend((
        (
            "target_reid_0_90_score",
            reports / "p125_scored_target_reid" / split / f"{sequence}.json",
            ["write_target_reid_sequence.py", *prefix],
        ),
        (
            "bytetrack_tim_mars_score",
            reports / "p125_scored_tim_mars" / split / f"{sequence}.json",
            ["write_tim_mars_sequence.py", *prefix],
        ),
    ))
    return result


def check_existing(path: Path, *, split: str, sequence: str, frozen: dict, stage: str, episodes: int, frames: int) -> None:
    document = json.loads(path.read_text())
    if stage == "detector_cache":
        schema, arm = "p125_shared_detector_sequence_cache_v1", None
    elif stage.endswith("_replay"):
        schema, arm = "p125_raw_tracker_sequence_replay_v1", stage.removesuffix("_replay")
    elif stage.endswith("_score") and stage.removesuffix("_score") in RAW_ARMS:
        schema, arm = "p125_scored_raw_tracker_sequence_v1", stage.removesuffix("_score")
    elif stage == "target_reid_0_90_score":
        schema, arm = "p125_scored_target_reid_sequence_v1", "target_reid_0_90"
    else:
        schema, arm = "p125_scored_tim_mars_sequence_v1", "bytetrack_tim_mars"
    if document.get("schema") != schema or (arm is not None and document.get("arm") != arm):
        raise ValueError(f"existing {stage} schema or arm mismatch: {path}")
    for key, expected in (
        ("split", split),
        ("sequence_name", sequence),
        ("protocol_sha256", frozen["protocol_sha256"]),
        ("manifest_sha256", frozen["manifest_sha256"]),
        ("freeze_commit", frozen["freeze_commit"]),
    ):
        if document.get(key) != expected:
            raise ValueError(f"existing {stage} {key} mismatch: {path}")
    if stage == "detector_cache":
        if document.get("source_frame_count") != frames or len(document.get("frames", [])) != frames:
            raise ValueError(f"existing detector frame count mismatch: {path}")
    elif stage.endswith("_replay"):
        if document.get("frame_count") != frames or len(document.get("frames", [])) != frames:
            raise ValueError(f"existing tracker frame count mismatch: {path}")
    elif document.get("episode_count") != episodes or len(document.get("episodes", [])) != episodes:
        raise ValueError(f"existing episode count mismatch: {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("train", "val", "all"), default="all")
    parser.add_argument("--max-sequences", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.max_sequences is not None and args.max_sequences <= 0:
        parser.error("--max-sequences must be positive")
    frozen = read_committed_frozen_inputs(
        repository_root=ROOT,
        protocol_path=ROOT / "docs/data/external_benchmark_v2/visdrone_selected_person_protocol_v1.json",
        manifest_path=ROOT / "docs/data/external_benchmark_v2/visdrone_gt_only_episode_manifest_v1.json",
    )
    manifest = frozen["manifest"]
    inventory = sorted(
        (item for item in manifest["sequence_inventory"]
         if args.split == "all" or item["split"] == args.split),
        key=lambda item: (item["split"], item["sequence_name"]),
    )
    if args.max_sequences is not None:
        inventory = inventory[:args.max_sequences]
    episode_counts: dict[tuple[str, str], int] = {}
    for episode in manifest["episodes"]:
        key = (episode["split"], episode["sequence_name"])
        episode_counts[key] = episode_counts.get(key, 0) + 1
    for ordinal, item in enumerate(inventory, 1):
        split = item["split"]
        sequence = item["sequence_name"]
        count = episode_counts.get((split, sequence), 0)
        for stage, path, command in stages(split, sequence):
            if path.exists():
                check_existing(
                    path, split=split, sequence=sequence, frozen=frozen,
                    stage=stage, episodes=count, frames=item["image_frame_count"],
                )
                action = "verified_existing"
            elif args.dry_run:
                action = "pending"
            else:
                completed = subprocess.run(
                    [sys.executable, str(Path(__file__).resolve().parent / command[0]), *command[1:]],
                    cwd=ROOT, check=False,
                )
                if completed.returncode != 0:
                    raise RuntimeError(f"{split}/{sequence} {stage} failed: {completed.returncode}")
                check_existing(
                    path, split=split, sequence=sequence, frozen=frozen,
                    stage=stage, episodes=count, frames=item["image_frame_count"],
                )
                action = "completed"
            print(json.dumps({"sequence": f"{ordinal}/{len(inventory)}", "split": split,
                              "name": sequence, "stage": stage, "action": action}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
