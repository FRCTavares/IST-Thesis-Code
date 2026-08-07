"""Tests for Issue #30's bbox-height-stratified reporting."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = ROOT / "tools" / "analysis"
MODULE_PATH = ANALYSIS_DIR / "bbox_size_stratified_report.py"

sys.path.insert(0, str(ANALYSIS_DIR))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_module("bbox_size_stratified_report", MODULE_PATH)

from evaluate_external_frame_outcomes import (  # noqa: E402
    FrameOutcome,
    OUTCOME_CANDIDATE_ABSENT,
    OUTCOME_CORRECT_TARGET,
    OUTCOME_SAFE_SUPPRESSION,
)
from external_target_initialization import (  # noqa: E402
    TrackerCandidateObservation,
)


TEST_BINS = [
    ("<70px", 0.0, 70.0),
    ("70-89px", 70.0, 90.0),
    ("90-109px", 90.0, 110.0),
    ("110-129px", 110.0, 130.0),
    (">=130px", 130.0, float("inf")),
]


@dataclass(frozen=True)
class FakeRow:
    normalized_frame_index: int
    identity: int
    bbox_xyxy: tuple
    include_as_person_candidate: bool = True


def make_row(
    frame_index: int, height_px: float, *, identity: int = 1
) -> FakeRow:
    return FakeRow(
        normalized_frame_index=frame_index,
        identity=identity,
        bbox_xyxy=(0.0, 0.0, 10.0, height_px),
    )


def make_outcome(frame_index: int, outcome: str) -> FrameOutcome:
    return FrameOutcome(
        normalized_frame_index=frame_index,
        outcome=outcome,
        output_tracker_identity=None,
        correctness_iou=None,
        matched_other_identity=None,
        detail="",
    )


class TestAssignBin:
    def test_boundary_values_use_lower_bin_inclusive(self):
        assert MODULE.assign_bin(69.999, TEST_BINS) == "<70px"
        assert MODULE.assign_bin(70.0, TEST_BINS) == "70-89px"
        assert MODULE.assign_bin(89.999, TEST_BINS) == "70-89px"
        assert MODULE.assign_bin(90.0, TEST_BINS) == "90-109px"
        assert MODULE.assign_bin(130.0, TEST_BINS) == ">=130px"

    def test_zero_and_very_large_values_are_covered(self):
        assert MODULE.assign_bin(0.0, TEST_BINS) == "<70px"
        assert MODULE.assign_bin(1_000_000.0, TEST_BINS) == ">=130px"


class TestSizeDistribution:
    def test_counts_and_fractions_sum_to_total(self):
        target_by_frame = {
            0: make_row(0, 50.0),
            1: make_row(1, 75.0),
            2: make_row(2, 75.0),
            3: make_row(3, 200.0),
        }
        distribution = MODULE.size_distribution(
            target_by_frame, TEST_BINS, image_height=1000
        )

        assert distribution["gt_visible_frames"] == 4
        assert distribution["counts_by_bin"]["<70px"] == 1
        assert distribution["counts_by_bin"]["70-89px"] == 2
        assert distribution["counts_by_bin"][">=130px"] == 1
        assert sum(distribution["counts_by_bin"].values()) == 4

        fractions = distribution["fraction_by_bin"]
        assert fractions["70-89px"] == 0.5
        assert fractions["<70px"] == 0.25

    def test_empty_input_reports_zero_not_crash(self):
        distribution = MODULE.size_distribution(
            {}, TEST_BINS, image_height=1000
        )
        assert distribution["gt_visible_frames"] == 0
        assert all(v == 0 for v in distribution["counts_by_bin"].values())
        assert all(v is None for v in distribution["fraction_by_bin"].values())


class TestCandidatePresenceByBin:
    def test_frame_with_matching_candidate_counts_as_present(self):
        entry = {
            "frame_contract": {
                "normalized_start_index": 0,
                "normalized_end_index_inclusive": 1,
            },
            "target": {
                "minimum_match_iou": 0.5,
                "minimum_match_margin": 0.1,
                "confirmation_frames": 2,
            },
        }
        target_by_frame = {
            0: make_row(0, 80.0),
            1: make_row(1, 80.0),
        }
        candidates_by_frame = {
            0: [
                TrackerCandidateObservation(
                    normalized_frame_index=0,
                    tracker_identity=5,
                    bbox_xyxy=(0.0, 0.0, 10.0, 80.0),
                    score=0.9,
                )
            ],
            # frame 1 has no candidates at all.
        }

        result = MODULE.candidate_presence_by_bin(
            entry, target_by_frame, candidates_by_frame, TEST_BINS
        )

        assert result["70-89px"]["frames"] == 2
        assert result["70-89px"]["with_candidate"] == 1
        assert result["70-89px"]["fraction_with_candidate"] == 0.5

    def test_bin_with_no_frames_has_none_fraction(self):
        entry = {
            "frame_contract": {
                "normalized_start_index": 0,
                "normalized_end_index_inclusive": 0,
            },
            "target": {
                "minimum_match_iou": 0.5,
                "minimum_match_margin": 0.1,
                "confirmation_frames": 2,
            },
        }
        target_by_frame = {0: make_row(0, 80.0)}
        result = MODULE.candidate_presence_by_bin(
            entry, target_by_frame, {}, TEST_BINS
        )
        assert result["<70px"]["frames"] == 0
        assert result["<70px"]["fraction_with_candidate"] is None


class TestBucketOutcomesByBin:
    def test_outcomes_grouped_by_matching_frame_gt_height(self):
        target_by_frame = {
            0: make_row(0, 50.0),
            1: make_row(1, 95.0),
        }
        outcomes = [
            make_outcome(0, OUTCOME_CORRECT_TARGET),
            make_outcome(1, OUTCOME_SAFE_SUPPRESSION),
        ]

        by_bin = MODULE.bucket_outcomes_by_bin(
            outcomes, target_by_frame, TEST_BINS
        )

        assert [o.outcome for o in by_bin["<70px"]] == [OUTCOME_CORRECT_TARGET]
        assert [o.outcome for o in by_bin["90-109px"]] == [
            OUTCOME_SAFE_SUPPRESSION
        ]
        assert by_bin["70-89px"] == []

    def test_frame_without_gt_row_is_excluded_not_crashed(self):
        target_by_frame = {0: make_row(0, 50.0)}
        outcomes = [
            make_outcome(0, OUTCOME_CORRECT_TARGET),
            make_outcome(99, OUTCOME_CANDIDATE_ABSENT),
        ]

        by_bin = MODULE.bucket_outcomes_by_bin(
            outcomes, target_by_frame, TEST_BINS
        )

        total_bucketed = sum(len(v) for v in by_bin.values())
        assert total_bucketed == 1
        assert [o.outcome for o in by_bin["<70px"]] == [OUTCOME_CORRECT_TARGET]


class TestAggregateAcrossSequences:
    def test_pools_outcomes_from_multiple_sequences_by_bin(self):
        per_sequence = {
            "seqA": {
                "_raw_outcomes_by_bin": {
                    "<70px": [make_outcome(0, OUTCOME_CORRECT_TARGET)],
                    "70-89px": [],
                    "90-109px": [],
                    "110-129px": [],
                    ">=130px": [],
                }
            },
            "seqB": {
                "_raw_outcomes_by_bin": {
                    "<70px": [make_outcome(1, OUTCOME_SAFE_SUPPRESSION)],
                    "70-89px": [],
                    "90-109px": [],
                    "110-129px": [],
                    ">=130px": [],
                }
            },
            "seqC_init_failure": {"_raw_outcomes_by_bin": None},
        }

        aggregate = MODULE.aggregate_across_sequences(
            per_sequence, TEST_BINS, stream_key="_raw_outcomes_by_bin"
        )

        assert aggregate["<70px"]["total_frames"] == 2
        assert aggregate["<70px"]["counts"][OUTCOME_CORRECT_TARGET] == 1
        assert aggregate["<70px"]["counts"][OUTCOME_SAFE_SUPPRESSION] == 1
        assert aggregate["70-89px"]["total_frames"] == 0


class TestStripPrivateFields:
    def test_underscore_prefixed_keys_removed(self):
        report = {
            "status": "evaluated",
            "raw_by_bin": {"a": 1},
            "_raw_outcomes_by_bin": {"a": [1, 2, 3]},
            "_tim_outcomes_by_bin": {"a": [1]},
        }
        cleaned = MODULE.strip_private_fields(report)
        assert "_raw_outcomes_by_bin" not in cleaned
        assert "_tim_outcomes_by_bin" not in cleaned
        assert cleaned["status"] == "evaluated"


class TestSequenceScope:
    def test_only_retained_visdrone_sequences_are_in_scope(self):
        assert MODULE.SEQUENCE_IDS == [
            "visdrone_mot_val_uav0000117_02622_v",
            "visdrone_mot_val_uav0000137_00458_v",
            "visdrone_mot_val_uav0000339_00001_v",
        ]
        for excluded in (
            "dancetrack_val_dancetrack0004",
            "dancetrack_val_dancetrack0019",
            "dancetrack_val_dancetrack0063",
            "dancetrack_val_dancetrack0073",
            "dancetrack_val_dancetrack0094",
            "visdrone_mot_val_uav0000268_05773_v",
            "ros2_internal_development_may_hard_reentry",
            "ros2_internal_development_seq01_clean",
            "ros2_internal_development_seq03_crossing",
            "ros2_internal_development_seq04_occlusion",
        ):
            assert excluded not in MODULE.SEQUENCE_IDS

    def test_full_pipeline_and_oracle_use_distinct_bag_roots(self):
        assert (
            MODULE.FULL_PIPELINE_CAPTURE_ROOT != MODULE.ORACLE_CAPTURE_ROOT
        )
        assert MODULE.FULL_PIPELINE_REPLAY_ROOT != MODULE.ORACLE_REPLAY_ROOT
