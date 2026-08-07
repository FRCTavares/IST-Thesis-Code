"""Tests for oracle-candidate ID assignment (Issue #30 oracle-candidate mode)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = ROOT / "tools" / "analysis"
MODULE_PATH = ANALYSIS_DIR / "build_oracle_candidate_bag.py"

sys.path.insert(0, str(ANALYSIS_DIR))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_module("build_oracle_candidate_bag", MODULE_PATH)

import external_tracking_dataset as adapter  # noqa: E402


def annotation(identity, frame, *, included=True):
    return adapter.ExternalObjectAnnotation(
        dataset="dancetrack",
        sequence_name="seq",
        split="val",
        source_path="x",
        source_line_number=1,
        source_row="x",
        source_frame_number=frame + 1,
        normalized_frame_index=frame,
        timestamp_s=0.0,
        image_width=1920,
        image_height=1080,
        frame_rate=20.0,
        source_index_base=1,
        identity=identity,
        bbox_xyxy=(0.0, 0.0, 10.0, 10.0),
        source_bbox_xywh=(0.0, 0.0, 10.0, 10.0),
        source_score=1.0,
        class_id=1,
        class_name="pedestrian",
        visibility=1.0,
        truncation=0,
        occlusion=0,
        ignored_region=False,
        include_as_person_candidate=included,
        exclusion_reason=None,
    )


class TestAssignOracleIds:
    def test_continuous_visibility_keeps_one_id(self):
        rows = [annotation(5, frame) for frame in range(5)]

        mapping = MODULE.assign_oracle_ids(rows)

        ids = {mapping[(5, frame)] for frame in range(5)}
        assert len(ids) == 1

    def test_gap_in_visibility_starts_new_id(self):
        rows = (
            [annotation(5, frame) for frame in range(0, 3)]
            + [annotation(5, frame) for frame in range(10, 13)]
        )

        mapping = MODULE.assign_oracle_ids(rows)

        first_segment_ids = {mapping[(5, f)] for f in range(0, 3)}
        second_segment_ids = {mapping[(5, f)] for f in range(10, 13)}

        assert len(first_segment_ids) == 1
        assert len(second_segment_ids) == 1
        assert first_segment_ids != second_segment_ids

    def test_different_identities_get_different_ids(self):
        rows = [annotation(5, 0), annotation(6, 0)]

        mapping = MODULE.assign_oracle_ids(rows)

        assert mapping[(5, 0)] != mapping[(6, 0)]

    def test_excluded_rows_are_ignored(self):
        rows = [
            annotation(5, 0),
            annotation(5, 1, included=False),
            annotation(5, 2),
        ]

        mapping = MODULE.assign_oracle_ids(rows)

        # frame 1 excluded => frame 0 and frame 2 are non-consecutive
        assert (5, 1) not in mapping
        assert mapping[(5, 0)] != mapping[(5, 2)]

    def test_oracle_ids_do_not_equal_dataset_identity(self):
        # a large, arbitrary dataset identity should not leak into the
        # small sequential oracle ID space
        rows = [annotation(9999, frame) for frame in range(3)]

        mapping = MODULE.assign_oracle_ids(rows)

        assert all(value != 9999 for value in mapping.values())

    def test_ids_are_globally_unique_across_identities_and_segments(self):
        rows = (
            [annotation(1, f) for f in range(0, 3)]
            + [annotation(1, f) for f in range(10, 13)]
            + [annotation(2, f) for f in range(0, 5)]
        )

        mapping = MODULE.assign_oracle_ids(rows)

        all_ids = list(mapping.values())
        distinct_ids = set(all_ids)

        # 3 segments total: identity 1 has 2 segments, identity 2 has 1
        assert len(distinct_ids) == 3
