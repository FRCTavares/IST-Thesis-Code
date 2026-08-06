"""Tests for the Issue #30 first-phase benchmark selection tool."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = ROOT / "tools" / "analysis"
MODULE_PATH = ANALYSIS_DIR / "select_first_phase_benchmark.py"
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
    "select_first_phase_benchmark",
    MODULE_PATH,
)


def make_sequence(name, candidate_count):
    return {
        "sequence_name": name,
        "candidate_count": candidate_count,
        "candidates": [],
    }


def make_candidate(
    identity,
    *,
    visible_frame_count,
    longest_consecutive_run,
    eligible=True,
    initialization_eligible=True,
    overlapping_person_frames=0,
    border_touch_frames=0,
    median_height_px=200.0,
    initialization_start_frame=0,
    initialization_end_frame_inclusive=9,
):
    return {
        "identity": identity,
        "eligible": eligible,
        "initialization_eligible": initialization_eligible,
        "visible_frame_count": visible_frame_count,
        "longest_consecutive_run": longest_consecutive_run,
        "overlapping_person_frames": overlapping_person_frames,
        "border_touch_frames": border_touch_frames,
        "median_height_px": median_height_px,
        "initialization_start_frame": initialization_start_frame,
        "initialization_end_frame_inclusive": (
            initialization_end_frame_inclusive
        ),
    }


class TestStratifiedSelection:
    def test_picks_requested_count(self):
        sequences = [
            make_sequence(f"seq{i:02d}", candidate_count=i)
            for i in range(10)
        ]

        picked = MODULE.stratified_selection(sequences, count=4)

        assert len(picked) == 4
        assert len(set(item["sequence_name"] for item in picked)) == 4

    def test_deterministic_across_calls(self):
        sequences = [
            make_sequence(f"seq{i:02d}", candidate_count=(i * 7) % 11)
            for i in range(15)
        ]

        first = MODULE.stratified_selection(sequences, count=5)
        second = MODULE.stratified_selection(sequences, count=5)

        assert first == second

    def test_spans_low_and_high_density(self):
        sequences = [
            make_sequence(f"seq{i:02d}", candidate_count=i)
            for i in range(20)
        ]

        picked = MODULE.stratified_selection(sequences, count=4)
        densities = sorted(item["candidate_count"] for item in picked)

        assert densities[0] <= 2
        assert densities[-1] >= 17

    def test_rejects_count_larger_than_population(self):
        sequences = [make_sequence("seq00", candidate_count=1)]

        with pytest.raises(ValueError, match="cannot select"):
            MODULE.stratified_selection(sequences, count=2)

    def test_ties_broken_by_sequence_name(self):
        sequences = [
            make_sequence("seq_b", candidate_count=1),
            make_sequence("seq_a", candidate_count=1),
        ]

        picked = MODULE.stratified_selection(sequences, count=2)

        assert [item["sequence_name"] for item in picked] == [
            "seq_a",
            "seq_b",
        ]


class TestSelectPhysicalTarget:
    def test_picks_longest_visible_span(self):
        sequence = {
            "sequence_name": "seq00",
            "candidates": [
                make_candidate(1, visible_frame_count=50, longest_consecutive_run=50),
                make_candidate(2, visible_frame_count=90, longest_consecutive_run=40),
            ],
        }

        chosen = MODULE.select_physical_target(sequence)

        assert chosen["identity"] == 2

    def test_ties_broken_by_longest_run_then_identity(self):
        sequence = {
            "sequence_name": "seq00",
            "candidates": [
                make_candidate(3, visible_frame_count=50, longest_consecutive_run=10),
                make_candidate(1, visible_frame_count=50, longest_consecutive_run=20),
                make_candidate(2, visible_frame_count=50, longest_consecutive_run=20),
            ],
        }

        chosen = MODULE.select_physical_target(sequence)

        assert chosen["identity"] == 1

    def test_ineligible_candidates_are_excluded(self):
        sequence = {
            "sequence_name": "seq00",
            "candidates": [
                make_candidate(
                    1,
                    visible_frame_count=1000,
                    longest_consecutive_run=1000,
                    eligible=False,
                ),
                make_candidate(2, visible_frame_count=10, longest_consecutive_run=10),
            ],
        }

        chosen = MODULE.select_physical_target(sequence)

        assert chosen["identity"] == 2

    def test_no_eligible_candidate_raises(self):
        sequence = {
            "sequence_name": "seq00",
            "candidates": [
                make_candidate(
                    1,
                    visible_frame_count=10,
                    longest_consecutive_run=10,
                    initialization_eligible=False,
                ),
            ],
        }

        with pytest.raises(ValueError, match="no eligible"):
            MODULE.select_physical_target(sequence)


class TestClassifyScene:
    def test_crowd_crossing_from_high_overlap(self):
        sequence = {"candidate_count": 12}
        candidate = make_candidate(
            1,
            visible_frame_count=100,
            longest_consecutive_run=100,
            overlapping_person_frames=40,
        )

        people, challenge, categories = MODULE.classify_scene(
            sequence, candidate, dataset_id="dancetrack"
        )

        assert people == 12
        assert challenge == "crowd_crossing"
        assert "crowd_crossing" in categories

    def test_clean_tracking_with_no_signals(self):
        sequence = {"candidate_count": 1}
        candidate = make_candidate(
            1,
            visible_frame_count=100,
            longest_consecutive_run=100,
        )

        _, challenge, categories = MODULE.classify_scene(
            sequence, candidate, dataset_id="mot17"
        )

        assert challenge == "moderate_visibility_tracking"
        assert categories == ["clean_tracking"]

    def test_small_target_tag(self):
        sequence = {"candidate_count": 1}
        candidate = make_candidate(
            1,
            visible_frame_count=100,
            longest_consecutive_run=100,
            median_height_px=30.0,
        )

        _, _, categories = MODULE.classify_scene(
            sequence, candidate, dataset_id="visdrone_mot"
        )

        assert "small_target" in categories
        assert "camera_motion" in categories

    def test_dancetrack_tags_similar_clothing(self):
        sequence = {"candidate_count": 1}
        candidate = make_candidate(
            1,
            visible_frame_count=100,
            longest_consecutive_run=100,
        )

        _, _, categories = MODULE.classify_scene(
            sequence, candidate, dataset_id="dancetrack"
        )

        assert "similar_clothing" in categories
        assert "appearance_ambiguity" in categories


class TestMergeManifestEntries:
    def test_replaces_matching_ids_and_keeps_others(self):
        manifest = {
            "sequences": [
                {"id": "a", "value": "old"},
                {"id": "b", "value": "keep"},
            ]
        }

        merged = MODULE.merge_manifest_entries(
            manifest, [{"id": "a", "value": "new"}]
        )

        by_id = {entry["id"]: entry for entry in merged["sequences"]}
        assert by_id["a"]["value"] == "new"
        assert by_id["b"]["value"] == "keep"
        assert len(merged["sequences"]) == 2


class TestBuildManifestEntrySchemaValidity:
    def test_entry_matches_schema(self):
        import jsonschema

        sequence = {
            "sequence_name": "seq00",
            "candidate_count": 5,
            "annotation_relative_path": "docs/data/external_benchmark/manifest.schema.json",
            "source_relative_path": "data/datasets/external/dancetrack/val/seq00",
            "image_width": 1920,
            "image_height": 1080,
            "image_count": 500,
            "timing_contract": {"analysis_frame_rate_hz": 20.0},
        }
        candidate = make_candidate(
            3, visible_frame_count=400, longest_consecutive_run=400
        )
        dataset_registry_entry = {
            "official_reference": "https://github.com/DanceTrack/DanceTrack",
            "source_frame_index_base": 1,
            "acquisitions": [
                {
                    "split": "val",
                    "verified_date": "2026-08-06",
                    "archive_sha256": "a" * 64,
                }
            ],
        }

        entry = MODULE.build_manifest_entry(
            dataset_id="dancetrack",
            split="val",
            sequence=sequence,
            candidate=candidate,
            dataset_registry_entry=dataset_registry_entry,
            repository_root=ROOT,
            repository_commit="b" * 40,
        )

        manifest = {
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
            "sequences": [entry],
        }

        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.validate(instance=manifest, schema=schema)
