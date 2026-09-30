#!/usr/bin/env python3
"""Reconcile all frozen Issue #125 arm outputs and summarize episode outcomes."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyse_visdrone_selected_person_statistics import PairedEpisode, analyse  # noqa: E402
from shared_detector_cache import read_committed_frozen_inputs  # noqa: E402
from write_shared_detector_cache import write_cache_once  # noqa: E402

RAW = ("sort_raw", "bytetrack_raw", "ocsort_raw", "deepsort_raw")
ARMS = (*RAW, "target_reid_0_90", "bytetrack_tim_mars")
BUCKETS = ("correct", "wrong_person", "identity_unresolved", "lost_suppressed")
SCHEMAS = {
    **{arm: "p125_scored_raw_tracker_sequence_v1" for arm in RAW},
    "target_reid_0_90": "p125_scored_target_reid_sequence_v1",
    "bytetrack_tim_mars": "p125_scored_tim_mars_sequence_v1",
}


def score_path(arm: str, split: str, sequence: str) -> Path:
    reports = ROOT / "artifacts/reports"
    if arm in RAW:
        return reports / "p125_scored_raw" / arm / split / f"{sequence}.json"
    suffix = "target_reid" if arm == "target_reid_0_90" else "tim_mars"
    return reports / f"p125_scored_{suffix}" / split / f"{sequence}.json"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def key(episode: dict[str, Any]) -> str:
    return f"{episode['split']}/{episode['sequence_name']}/{episode['dataset_identity']}/{episode['selection_frame_index']}"


def height_stratum(height: float) -> str:
    if height < 20:
        return "<20"
    if height < 40:
        return "20-39"
    if height < 80:
        return "40-79"
    if height < 160:
        return "80-159"
    return ">=160"


def load_scores(
    *, frozen: dict[str, Any], split: str, sequence: str,
    expected_episodes: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, dict[str, Any]]], dict[str, str]]:
    by_arm: dict[str, dict[str, dict[str, Any]]] = {}
    digests = {}
    reports = ROOT / "artifacts/reports"
    cache_path = reports / "p125_shared_detector_cache" / split / f"{sequence}.json"
    cache_payload = cache_path.read_bytes()
    cache = json.loads(cache_payload)
    for field, expected in (
        ("schema", "p125_shared_detector_sequence_cache_v1"),
        ("split", split), ("sequence_name", sequence),
        ("protocol_sha256", frozen["protocol_sha256"]),
        ("manifest_sha256", frozen["manifest_sha256"]),
        ("freeze_commit", frozen["freeze_commit"]),
    ):
        if cache.get(field) != expected:
            raise ValueError(f"{cache_path}: {field} mismatch")
    cache_sha = sha256_bytes(cache_payload)
    digests[str(cache_path.relative_to(ROOT))] = cache_sha
    replay_shas = {}
    for arm in RAW:
        replay_path = reports / "p125_raw_tracker_replay" / arm / split / f"{sequence}.json"
        replay_payload = replay_path.read_bytes()
        replay = json.loads(replay_payload)
        for field, expected in (
            ("schema", "p125_raw_tracker_sequence_replay_v1"),
            ("arm", arm), ("split", split), ("sequence_name", sequence),
            ("protocol_sha256", frozen["protocol_sha256"]),
            ("manifest_sha256", frozen["manifest_sha256"]),
            ("freeze_commit", frozen["freeze_commit"]),
            ("detector_cache_sha256", cache_sha),
        ):
            if replay.get(field) != expected:
                raise ValueError(f"{replay_path}: {field} mismatch")
        replay_shas[arm] = sha256_bytes(replay_payload)
        digests[str(replay_path.relative_to(ROOT))] = replay_shas[arm]
    for arm in ARMS:
        path = score_path(arm, split, sequence)
        payload = path.read_bytes()
        doc = json.loads(payload)
        for field, expected in (
            ("schema", SCHEMAS[arm]), ("arm", arm), ("split", split),
            ("sequence_name", sequence),
            ("protocol_sha256", frozen["protocol_sha256"]),
            ("manifest_sha256", frozen["manifest_sha256"]),
            ("freeze_commit", frozen["freeze_commit"]),
            ("episode_count", len(expected_episodes)),
            (("tracker_replay_sha256" if arm in RAW else "bytetrack_replay_sha256"),
             replay_shas[arm] if arm in RAW else replay_shas["bytetrack_raw"]),
        ):
            if doc.get(field) != expected:
                raise ValueError(f"{path}: {field} mismatch")
        rows = doc.get("episodes")
        if not isinstance(rows, list) or [row["episode"] for row in rows] != expected_episodes:
            raise ValueError(f"{path}: frozen episode list mismatch")
        by_arm[arm] = {}
        for row in rows:
            episode_key = key(row["episode"])
            scoring = row["evaluation"]["scoring"]
            counts = scoring["counts"]
            denominator = scoring["target_present_scored_frames"]
            if set(counts) != set(BUCKETS) or sum(counts.values()) != denominator or denominator <= 0:
                raise ValueError(f"{path}: four-bucket reconciliation failed for {episode_key}")
            if any(scoring["fractions"][bucket] != counts[bucket] / denominator for bucket in BUCKETS):
                raise ValueError(f"{path}: episode fraction mismatch for {episode_key}")
            frame_counts = {bucket: 0 for bucket in BUCKETS}
            for frame in row["evaluation"]["frames"]:
                bucket = frame["bucket"]
                if bucket in BUCKETS:
                    frame_counts[bucket] += 1
            if frame_counts != counts:
                raise ValueError(f"{path}: frame buckets differ from summary for {episode_key}")
            if episode_key in by_arm[arm]:
                raise ValueError(f"{path}: duplicate episode {episode_key}")
            by_arm[arm][episode_key] = row
        digests[str(path.relative_to(ROOT))] = sha256_bytes(payload)
    return by_arm, digests


def arm_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {bucket: 0 for bucket in BUCKETS}
    strata = defaultdict(lambda: {bucket: 0 for bucket in BUCKETS})
    events = defaultdict(int)
    macro = {bucket: 0.0 for bucket in BUCKETS}
    localization_sum = 0.0
    localization_count = 0
    initialized = 0
    for row in rows:
        initialized += bool(row["initialization"]["success"])
        evaluation = row["evaluation"]
        for bucket in BUCKETS:
            counts[bucket] += evaluation["scoring"]["counts"][bucket]
            macro[bucket] += evaluation["scoring"]["fractions"][bucket]
        for name, value in evaluation["events"].items():
            if type(value) is int:
                events[name] += value
        for frame in evaluation["frames"]:
            bucket = frame["bucket"]
            if bucket not in BUCKETS:
                continue
            height = frame["target_bbox_height_px"]
            occlusion = frame["target_occlusion"]
            strata[f"height:{height_stratum(height)}"][bucket] += 1
            strata[f"occlusion:{occlusion if occlusion is not None else 'unknown'}"][bucket] += 1
            if bucket == "correct":
                iou = frame["target_iou"]
                if iou is None:
                    raise ValueError("correct frame lacks target IoU")
                localization_sum += iou
                localization_count += 1
    denominator = sum(counts.values())
    return {
        "episode_count": len(rows),
        "initialization_success_count": initialized,
        "target_present_frame_count": denominator,
        "frame_bucket_counts": counts,
        "frame_bucket_micro_fractions": {
            bucket: counts[bucket] / denominator if denominator else None for bucket in BUCKETS
        },
        "episode_macro_bucket_fractions": {
            bucket: macro[bucket] / len(rows) if rows else None for bucket in BUCKETS
        },
        "correct_only_localization": {
            "correct_frame_count": localization_count,
            "mean_target_iou": localization_sum / localization_count if localization_count else None,
        },
        "strata_frame_bucket_counts": dict(sorted(strata.items())),
        "event_counts": dict(sorted(events.items())),
    }


def summarize(frozen: dict[str, Any], *, split: str) -> dict[str, Any]:
    manifest = frozen["manifest"]
    inventory = sorted(
        (item for item in manifest["sequence_inventory"] if split == "all" or item["split"] == split),
        key=lambda item: (item["split"], item["sequence_name"]),
    )
    by_arm = {arm: {} for arm in ARMS}
    source_digests: dict[str, str] = {}
    for item in inventory:
        sequence_episodes = [e for e in manifest["episodes"]
                             if e["split"] == item["split"] and e["sequence_name"] == item["sequence_name"]]
        rows, digests = load_scores(
            frozen=frozen, split=item["split"], sequence=item["sequence_name"],
            expected_episodes=sequence_episodes,
        )
        source_digests.update(digests)
        for arm in ARMS:
            by_arm[arm].update(rows[arm])
    expected_keys = {key(e) for e in manifest["episodes"]
                     if split == "all" or e["split"] == split}
    if any(set(by_arm[arm]) != expected_keys for arm in ARMS):
        raise ValueError("six-arm episode coverage mismatch")
    byte = by_arm["bytetrack_raw"]
    tim = by_arm["bytetrack_tim_mars"]
    target = by_arm["target_reid_0_90"]
    primary_keys = sorted(k for k in expected_keys if byte[k]["initialization"]["success"])
    if any(tim[k]["initialization"] != byte[k]["initialization"] or
           target[k]["initialization"] != byte[k]["initialization"] for k in expected_keys):
        raise ValueError("ByteTrack-dependent initialization mismatch")
    common_raw_keys = sorted(k for k in expected_keys
                             if all(by_arm[arm][k]["initialization"]["success"] for arm in RAW))
    summaries = {arm: arm_summary([by_arm[arm][k] for k in sorted(expected_keys)]) for arm in ARMS}
    common_raw = {arm: arm_summary([by_arm[arm][k] for k in common_raw_keys]) for arm in RAW}
    primary = {arm: arm_summary([by_arm[arm][k] for k in primary_keys])
               for arm in ("bytetrack_raw", "bytetrack_tim_mars")}
    report = {
        "schema": "p125_visdrone_selected_person_aggregate_v1",
        "split": split,
        "protocol_sha256": frozen["protocol_sha256"],
        "manifest_sha256": frozen["manifest_sha256"],
        "freeze_commit": frozen["freeze_commit"],
        "sequence_count": len(inventory),
        "frozen_episode_count": len(expected_keys),
        "source_artifact_sha256": dict(sorted(source_digests.items())),
        "all_eligible": summaries,
        "common_raw_initializable": {"episode_count": len(common_raw_keys), "arms": common_raw},
        "primary_bytetrack_initializable": {"episode_count": len(primary_keys), "arms": primary},
        "nominal_replay_clock_is_measured_time": False,
    }
    if split == "all":
        settings = frozen["protocol"]["statistics_draft"]
        records = []
        for episode_key in primary_keys:
            episode = byte[episode_key]["episode"]
            tim_fractions = tim[episode_key]["evaluation"]["scoring"]["fractions"]
            byte_fractions = byte[episode_key]["evaluation"]["scoring"]["fractions"]
            records.append(PairedEpisode(
                sequence_name=f"{episode['split']}/{episode['sequence_name']}",
                episode_key=episode_key,
                tim_wrong_fraction=tim_fractions["wrong_person"],
                bytetrack_wrong_fraction=byte_fractions["wrong_person"],
                tim_correct_fraction=tim_fractions["correct"],
                bytetrack_correct_fraction=byte_fractions["correct"],
            ))
        report["predeclared_primary_statistics"] = analyse(
            records, seed=settings["random_seed"],
            bootstrap_replicates=settings["cluster_bootstrap_replicates"],
            sign_flip_draws=settings["formal_test_draws"],
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("train", "val", "all"), default="all")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    frozen = read_committed_frozen_inputs(
        repository_root=ROOT,
        protocol_path=ROOT / "docs/data/external_benchmark_v2/visdrone_selected_person_protocol_v1.json",
        manifest_path=ROOT / "docs/data/external_benchmark_v2/visdrone_gt_only_episode_manifest_v1.json",
    )
    report = summarize(frozen, split=args.split)
    output = args.output or ROOT / "artifacts/reports/p125_aggregate" / f"{args.split}.json"
    digest = write_cache_once(output, report)
    print(json.dumps({"output": str(output), "sha256": digest,
                      "sequence_count": report["sequence_count"],
                      "frozen_episode_count": report["frozen_episode_count"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
