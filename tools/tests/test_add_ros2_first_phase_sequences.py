"""Tests for adding the four internal ROS 2 sequences to the manifest."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = ROOT / "tools" / "analysis"
MODULE_PATH = ANALYSIS_DIR / "add_ros2_first_phase_sequences.py"
SCHEMA_PATH = (
    ROOT
    / "docs"
    / "data"
    / "external_benchmark"
    / "manifest.schema.json"
)

sys.path.insert(0, str(ANALYSIS_DIR))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_module(
    "add_ros2_first_phase_sequences",
    MODULE_PATH,
)


def base_manifest(sequences):
    return {
        "schema_version": 1,
        "benchmark_id": "test",
        "status": "draft_not_frozen",
        "created_date": "2026-08-07",
        "frozen_date": None,
        "baseline_commit": "c" * 40,
        "manifest_commit": None,
        "policy": {
            "canonical_policy_changes_allowed": False,
            "external_outcome_tuning_allowed": False,
            "issue_27_held_out_allowed": False,
            "selection_before_outcome_review": True,
        },
        "coordinate_contract": {
            "representation": "xyxy",
            "space": "original_source_image_pixels",
            "x2_y2_semantics": "geometric_edge",
            "clipping": "clip_to_zero_width_and_zero_height_bounds",
            "normalized_frame_index": "zero_based",
            "timestamp_rule": (
                "normalized_frame_index_divided_by_frame_rate"
            ),
        },
        "sequences": sequences,
    }


class TestBuildEntry:
    def test_all_four_specs_produce_schema_valid_entries(self):
        import jsonschema

        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        entries = [
            MODULE.build_entry(
                spec,
                repository_root=ROOT,
                repository_commit="b" * 40,
            )
            for spec in MODULE.ROS2_SEQUENCES
        ]

        manifest = base_manifest(entries)
        jsonschema.validate(instance=manifest, schema=schema)

    def test_frame_rate_is_images_over_duration(self):
        spec = MODULE.ROS2_SEQUENCES[1]  # seq01_clean

        entry = MODULE.build_entry(
            spec, repository_root=ROOT, repository_commit=None
        )

        expected = spec["image_count"] / spec["bag_duration_s"]
        assert entry["frame_contract"]["frame_rate"] == pytest.approx(
            expected
        )

    def test_seq03_uses_bytetrack_annotation_not_ocsort(self):
        spec = next(
            item
            for item in MODULE.ROS2_SEQUENCES
            if item["sequence_name"] == "seq03_crossing"
        )

        assert "bytetrack" in spec["annotation_relative_path"]
        assert "ocsort" not in spec["annotation_relative_path"]

    def test_seq04_uses_bytetrack_annotation_not_ocsort(self):
        spec = next(
            item
            for item in MODULE.ROS2_SEQUENCES
            if item["sequence_name"] == "seq04_occlusion"
        )

        assert "bytetrack" in spec["annotation_relative_path"]
        assert "ocsort" not in spec["annotation_relative_path"]

    def test_dataset_identity_matches_initial_tracker_identity(self):
        for spec in MODULE.ROS2_SEQUENCES:
            entry = MODULE.build_entry(
                spec, repository_root=ROOT, repository_commit=None
            )
            assert (
                entry["target"]["dataset_identity"]
                == entry["target"]["initial_tracker_identity"]
            )

    def test_initialization_window_does_not_exceed_sequence_length(self):
        short_spec = dict(MODULE.ROS2_SEQUENCES[0])
        short_spec["image_count"] = 3

        entry = MODULE.build_entry(
            short_spec, repository_root=ROOT, repository_commit=None
        )

        assert (
            entry["target"]["initialization_end_frame_inclusive"] == 2
        )


class TestMergeManifestEntries:
    def test_replaces_matching_ids_and_keeps_others(self):
        manifest = base_manifest(
            [
                {"id": "ros2_internal_development_seq01_clean", "v": "old"},
                {"id": "dancetrack_val_dancetrack0004", "v": "keep"},
            ]
        )

        merged = MODULE.merge_manifest_entries(
            manifest,
            [
                {
                    "id": "ros2_internal_development_seq01_clean",
                    "v": "new",
                }
            ],
        )

        by_id = {entry["id"]: entry for entry in merged["sequences"]}
        assert by_id["ros2_internal_development_seq01_clean"]["v"] == "new"
        assert by_id["dancetrack_val_dancetrack0004"]["v"] == "keep"
        assert len(merged["sequences"]) == 2
