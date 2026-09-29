"""GT-only manifest integrity checks for Issue #125."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "issues"
    / "p125"
    / "build_visdrone_gt_only_episode_manifest.py"
)
SPEC = importlib.util.spec_from_file_location("p125_gt_manifest", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def audit(split: str):
    config = {
        "minimum_selection_height_px": 20.0,
        "minimum_target_present_frames": 30,
        "maximum_selection_truncation": 1,
        "maximum_selection_occlusion": 1,
        "initialization_window_frames": 10,
    }
    name = f"{split}_sequence"
    return {
        "schema": "p125_visdrone_gt_only_corpus_audit_v1",
        "dataset": "visdrone_mot",
        "split": split,
        "eligibility_config": config,
        "sequence_count": 1,
        "sequence_reports": [{
            "split": split,
            "sequence_name": name,
            "pedestrian_identity_count": 2,
            "source": {
                "annotation_sha256": "e" * 64,
                "image_width": 1280,
                "image_height": 720,
            },
            "frame_domain": {
                "image_frame_count": 40,
                "annotation_frame_count": 40,
                "intersection_frame_count": 40,
                "image_only_frames": [],
                "annotation_only_frames": [],
                "minimum_image_frame": 1,
                "maximum_image_frame": 40,
                "minimum_annotation_frame": 1,
                "maximum_annotation_frame": 40,
            },
            "eligibility": {
                "config": config,
                "eligible_episode_count": 1,
                "exclusions": {"no_eligible_selection_frame": 1},
            },
        }],
        "episode_candidates": [{
            "split": split,
            "sequence_name": name,
            "dataset_identity": 7,
            "selection_frame_index": 0,
            "initialization_end_frame_inclusive": 9,
            "target_present_frames_from_selection": 40,
            "selection_bbox_height_px": 30.0,
            "selection_truncation": 0,
            "selection_occlusion": 0,
        }],
        "totals": {
            "pedestrian_identities": 2,
            "eligible_episode_candidates": 1,
            "image_frames": 40,
            "annotation_frames": 40,
            "image_only_frames": 0,
            "annotation_only_frames": 0,
        },
    }


def build(train, val):
    return MODULE.build_manifest(
        train, val,
        train_audit_sha256="a" * 64,
        val_audit_sha256="b" * 64,
        train_archive_sha256="c" * 64,
        val_archive_sha256="d" * 64,
    )


def test_complete_audits_produce_sorted_draft_manifest():
    manifest = build(audit("train"), audit("val"))
    assert manifest["status"] == "draft_not_frozen"
    assert manifest["sequence_count"] == 2
    assert manifest["pedestrian_identity_count"] == 4
    assert manifest["episode_candidate_count"] == 2
    assert len(manifest["sequence_inventory"]) == 2
    assert manifest["sequence_inventory"][0]["annotation_sha256"] == "e" * 64
    assert [episode["split"] for episode in manifest["episodes"]] == ["train", "val"]


def test_missing_image_frame_rejects_manifest():
    train = audit("train")
    domain = train["sequence_reports"][0]["frame_domain"]
    domain["image_frame_count"] = 39
    domain["intersection_frame_count"] = 39
    domain["annotation_only_frames"] = [40]
    train["totals"]["image_frames"] = 39
    train["totals"]["annotation_only_frames"] = 1
    with pytest.raises(ValueError, match="annotation frame has no source image"):
        build(train, audit("val"))


def test_identity_exclusions_must_reconcile():
    train = audit("train")
    train["sequence_reports"][0]["eligibility"]["exclusions"] = {}
    with pytest.raises(ValueError, match="identity eligibility"):
        build(train, audit("val"))


def test_split_eligibility_config_must_match():
    val = audit("val")
    val["eligibility_config"]["minimum_selection_height_px"] = 25.0
    with pytest.raises(ValueError, match="eligibility configurations differ"):
        build(audit("train"), val)


def test_duplicate_episode_rejected():
    train = audit("train")
    train["episode_candidates"].append(copy.deepcopy(train["episode_candidates"][0]))
    train["totals"]["eligible_episode_candidates"] = 2
    train["sequence_reports"][0]["eligibility"]["eligible_episode_count"] = 2
    train["sequence_reports"][0]["pedestrian_identity_count"] = 3
    train["totals"]["pedestrian_identities"] = 3
    with pytest.raises(ValueError, match="duplicate or misplaced episode"):
        build(train, audit("val"))


def test_image_without_gt_rows_is_recorded_as_reference_unavailable():
    train = audit("train")
    domain = train["sequence_reports"][0]["frame_domain"]
    domain["annotation_frame_count"] = 37
    domain["intersection_frame_count"] = 37
    domain["image_only_frames"] = [23, 24, 25]
    train["totals"]["annotation_frames"] = 37
    train["totals"]["image_only_frames"] = 3
    manifest = build(train, audit("val"))
    assert manifest["image_frames_without_gt_rows"] == [{
        "split": "train",
        "sequence_name": "train_sequence",
        "source_frame_numbers": [23, 24, 25],
        "scoring_policy": "reference_unavailable_for_target_present_scoring",
    }]
