#!/usr/bin/env python3
"""Combine outcome-blind VisDrone train/val audits into a draft episode manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_audit(path: Path, expected_split: str) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    audit = json.loads(raw)
    if audit.get("schema") != "p125_visdrone_gt_only_corpus_audit_v1":
        raise ValueError(f"{path}: unexpected audit schema")
    if audit.get("split") != expected_split:
        raise ValueError(f"{path}: expected {expected_split} audit")
    if audit.get("dataset") != "visdrone_mot":
        raise ValueError(f"{path}: unexpected dataset")
    return audit, hashlib.sha256(raw).hexdigest()


def validate_audit(audit: dict[str, Any]) -> None:
    split = audit["split"]
    sequences = audit["sequence_reports"]
    episodes = audit["episode_candidates"]
    if not sequences or audit["sequence_count"] != len(sequences):
        raise ValueError(f"{split}: sequence count mismatch")
    names: set[str] = set()
    episode_keys: set[tuple[str, int]] = set()
    eligible_count = 0
    identity_count = 0
    image_count = 0
    annotation_count = 0
    for sequence in sequences:
        name = sequence["sequence_name"]
        if name in names or sequence["split"] != split:
            raise ValueError(f"{split}: duplicate or misplaced sequence {name}")
        names.add(name)
        domain = sequence["frame_domain"]
        if domain["annotation_only_frames"]:
            raise ValueError(f"{split}/{name}: annotation frame has no source image")
        if domain["image_frame_count"] - domain["annotation_frame_count"] != len(domain["image_only_frames"]):
            raise ValueError(f"{split}/{name}: image-only frame count mismatch")
        if domain["intersection_frame_count"] != domain["annotation_frame_count"]:
            raise ValueError(f"{split}/{name}: intersection count mismatch")
        if domain["minimum_image_frame"] != domain["minimum_annotation_frame"] or domain["maximum_image_frame"] != domain["maximum_annotation_frame"]:
            raise ValueError(f"{split}/{name}: frame range mismatch")
        identities = sequence["pedestrian_identity_count"]
        eligibility = sequence["eligibility"]
        if identities != eligibility["eligible_episode_count"] + sum(eligibility["exclusions"].values()):
            raise ValueError(f"{split}/{name}: identity eligibility does not reconcile")
        if eligibility["config"] != audit["eligibility_config"]:
            raise ValueError(f"{split}/{name}: eligibility config mismatch")
        eligible_count += eligibility["eligible_episode_count"]
        identity_count += identities
        image_count += domain["image_frame_count"]
        annotation_count += domain["annotation_frame_count"]
    for episode in episodes:
        name = episode["sequence_name"]
        key = (name, episode["dataset_identity"])
        if episode["split"] != split or name not in names or key in episode_keys:
            raise ValueError(f"{split}: duplicate or misplaced episode {key}")
        if episode["target_present_frames_from_selection"] < audit["eligibility_config"]["minimum_target_present_frames"]:
            raise ValueError(f"{split}/{name}: episode shorter than eligibility minimum")
        episode_keys.add(key)
    totals = audit["totals"]
    if len(episodes) != eligible_count or totals["eligible_episode_candidates"] != eligible_count:
        raise ValueError(f"{split}: episode count mismatch")
    if totals["pedestrian_identities"] != identity_count:
        raise ValueError(f"{split}: identity count mismatch")
    if totals["image_frames"] != image_count or totals["annotation_frames"] != annotation_count:
        raise ValueError(f"{split}: frame totals mismatch")
    image_only_count = sum(
        len(sequence["frame_domain"]["image_only_frames"])
        for sequence in sequences
    )
    if totals["image_only_frames"] != image_only_count or totals["annotation_only_frames"]:
        raise ValueError(f"{split}: frame-domain gap total mismatch")


def build_manifest(
    train_audit: dict[str, Any],
    val_audit: dict[str, Any],
    *,
    train_audit_sha256: str,
    val_audit_sha256: str,
    train_archive_sha256: str,
    val_archive_sha256: str,
) -> dict[str, Any]:
    for split, audit in (("train", train_audit), ("val", val_audit)):
        if audit.get("split") != split:
            raise ValueError(f"expected {split} audit")
        validate_audit(audit)
    if train_audit["eligibility_config"] != val_audit["eligibility_config"]:
        raise ValueError("train and val eligibility configurations differ")
    episodes = sorted(
        train_audit["episode_candidates"] + val_audit["episode_candidates"],
        key=lambda episode: (
            episode["split"],
            episode["sequence_name"],
            episode["dataset_identity"],
        ),
    )
    image_frames_without_gt_rows = [
        {
            "split": audit["split"],
            "sequence_name": sequence["sequence_name"],
            "source_frame_numbers": sequence["frame_domain"]["image_only_frames"],
            "scoring_policy": "reference_unavailable_for_target_present_scoring",
        }
        for audit in (train_audit, val_audit)
        for sequence in audit["sequence_reports"]
        if sequence["frame_domain"]["image_only_frames"]
    ]
    sequence_inventory = sorted(
        [
            {
                "split": audit["split"],
                "sequence_name": sequence["sequence_name"],
                "image_frame_count": sequence["frame_domain"]["image_frame_count"],
                "annotation_frame_count": sequence["frame_domain"]["annotation_frame_count"],
                "first_source_frame": sequence["frame_domain"]["minimum_image_frame"],
                "last_source_frame": sequence["frame_domain"]["maximum_image_frame"],
                "image_frames_without_gt_rows": sequence["frame_domain"]["image_only_frames"],
                "annotation_sha256": sequence["source"]["annotation_sha256"],
                "image_width": sequence["source"]["image_width"],
                "image_height": sequence["source"]["image_height"],
            }
            for audit in (train_audit, val_audit)
            for sequence in audit["sequence_reports"]
        ],
        key=lambda sequence: (sequence["split"], sequence["sequence_name"]),
    )
    return {
        "schema": "p125_visdrone_gt_only_episode_manifest_v1",
        "status": "draft_not_frozen",
        "dataset": "visdrone_mot",
        "eligibility_config": train_audit["eligibility_config"],
        "source_audits": {
            "train": {"sha256": train_audit_sha256, "archive_sha256": train_archive_sha256, "totals": train_audit["totals"]},
            "val": {"sha256": val_audit_sha256, "archive_sha256": val_archive_sha256, "totals": val_audit["totals"]},
        },
        "sequence_count": train_audit["sequence_count"] + val_audit["sequence_count"],
        "pedestrian_identity_count": train_audit["totals"]["pedestrian_identities"] + val_audit["totals"]["pedestrian_identities"],
        "episode_candidate_count": len(episodes),
        "sequence_inventory": sequence_inventory,
        "image_frames_without_gt_rows": image_frames_without_gt_rows,
        "episodes": episodes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train-audit", type=Path, required=True)
    parser.add_argument("--val-audit", type=Path, required=True)
    parser.add_argument("--train-archive", type=Path, required=True)
    parser.add_argument("--val-archive", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    train, train_sha = load_audit(args.train_audit, "train")
    val, val_sha = load_audit(args.val_audit, "val")
    manifest = build_manifest(
        train,
        val,
        train_audit_sha256=train_sha,
        val_audit_sha256=val_sha,
        train_archive_sha256=sha256_file(args.train_archive),
        val_archive_sha256=sha256_file(args.val_archive),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "sequence_count": manifest["sequence_count"],
        "pedestrian_identity_count": manifest["pedestrian_identity_count"],
        "episode_candidate_count": manifest["episode_candidate_count"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
