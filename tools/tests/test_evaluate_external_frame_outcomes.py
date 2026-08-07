"""Tests for the Issue #30 frame-level physical-target outcome classifier."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_DIR = ROOT / "tools" / "analysis"
MODULE_PATH = ANALYSIS_DIR / "evaluate_external_frame_outcomes.py"

sys.path.insert(0, str(ANALYSIS_DIR))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_module("evaluate_external_frame_outcomes", MODULE_PATH)

from external_target_initialization import (  # noqa: E402
    InitializationConfig,
    PhysicalTargetObservation,
    TrackerCandidateObservation,
)


CONFIG = InitializationConfig(
    start_frame_index=0,
    end_frame_index_inclusive=100,
    minimum_iou=0.5,
    minimum_margin=0.1,
    confirmation_frames=2,
)

TARGET_BOX = (100.0, 100.0, 200.0, 200.0)
OTHER_BOX = (500.0, 500.0, 600.0, 600.0)


def target_obs(frame, bbox=TARGET_BOX):
    return PhysicalTargetObservation(
        normalized_frame_index=frame,
        dataset_identity=1,
        bbox_xyxy=bbox,
    )


def candidate(frame, identity, bbox, score=0.9):
    return TrackerCandidateObservation(
        normalized_frame_index=frame,
        tracker_identity=identity,
        bbox_xyxy=bbox,
        score=score,
    )


def output(frame, identity, bbox):
    return MODULE.SystemOutput(
        normalized_frame_index=frame,
        tracker_identity=identity,
        bbox_xyxy=bbox,
    )


def other_person(frame, identity=2, bbox=OTHER_BOX):
    return MODULE.OtherPerson(
        normalized_frame_index=frame,
        dataset_identity=identity,
        bbox_xyxy=bbox,
    )


def classify_one_frame(
    *,
    target=None,
    candidates=None,
    others=None,
    output_msg=None,
):
    frame = 0
    return MODULE.classify_sequence(
        frame_indices=[frame],
        target_by_frame={frame: target} if target is not None else {},
        candidates_by_frame={frame: candidates or []},
        other_people_by_frame={frame: others or []},
        outputs_by_frame=(
            {frame: output_msg} if output_msg is not None else {}
        ),
        match_config=CONFIG,
    )[0]


class TestCorrectTarget:
    def test_output_overlaps_target(self):
        result = classify_one_frame(
            target=target_obs(0),
            output_msg=output(0, 7, TARGET_BOX),
        )

        assert result.outcome == MODULE.OUTCOME_CORRECT_TARGET
        assert result.correctness_iou == 1.0


class TestCorrectRecovery:
    def test_id_change_between_two_correct_frames_is_recovery(self):
        outcomes = MODULE.classify_sequence(
            frame_indices=[0, 1],
            target_by_frame={0: target_obs(0), 1: target_obs(1)},
            candidates_by_frame={0: [], 1: []},
            other_people_by_frame={0: [], 1: []},
            outputs_by_frame={
                0: output(0, 7, TARGET_BOX),
                1: output(1, 9, TARGET_BOX),
            },
            match_config=CONFIG,
        )

        assert outcomes[0].outcome == MODULE.OUTCOME_CORRECT_TARGET
        assert outcomes[1].outcome == MODULE.OUTCOME_CORRECT_RECOVERY

    def test_same_id_stays_correct_target(self):
        outcomes = MODULE.classify_sequence(
            frame_indices=[0, 1],
            target_by_frame={0: target_obs(0), 1: target_obs(1)},
            candidates_by_frame={0: [], 1: []},
            other_people_by_frame={0: [], 1: []},
            outputs_by_frame={
                0: output(0, 7, TARGET_BOX),
                1: output(1, 7, TARGET_BOX),
            },
            match_config=CONFIG,
        )

        assert outcomes[1].outcome == MODULE.OUTCOME_CORRECT_TARGET


class TestSafeSuppressionVsCandidateAbsent:
    def test_confident_candidate_but_no_output_is_safe_suppression(self):
        result = classify_one_frame(
            target=target_obs(0),
            candidates=[candidate(0, 7, TARGET_BOX)],
            output_msg=None,
        )

        assert result.outcome == MODULE.OUTCOME_SAFE_SUPPRESSION

    def test_no_candidates_and_no_output_is_candidate_absent(self):
        result = classify_one_frame(
            target=target_obs(0),
            candidates=[],
            output_msg=None,
        )

        assert result.outcome == MODULE.OUTCOME_CANDIDATE_ABSENT

    def test_ambiguous_margin_is_reported(self):
        near_box = (105.0, 100.0, 205.0, 200.0)
        result = classify_one_frame(
            target=target_obs(0),
            candidates=[
                candidate(0, 7, TARGET_BOX),
                candidate(0, 8, near_box),
            ],
            output_msg=None,
        )

        assert result.outcome == MODULE.OUTCOME_AMBIGUOUS_CANDIDATE


class TestPhysicalAbsence:
    def test_no_target_no_output_is_correct_absence(self):
        result = classify_one_frame(target=None, output_msg=None)

        assert result.outcome == MODULE.OUTCOME_PHYSICAL_ABSENCE

    def test_output_while_target_absent_is_wrong(self):
        result = classify_one_frame(
            target=None,
            output_msg=output(0, 7, TARGET_BOX),
        )

        assert result.outcome == MODULE.OUTCOME_WRONG_DURING_ABSENCE
        assert result.outcome in MODULE.WRONG_PERSON_OUTCOMES


class TestDistractorVsStaleIdTransfer:
    def test_never_correct_id_on_other_person_is_distractor(self):
        result = classify_one_frame(
            target=target_obs(0),
            others=[other_person(0)],
            output_msg=output(0, 99, OTHER_BOX),
        )

        assert result.outcome == MODULE.OUTCOME_DISTRACTOR_SELECTION

    def test_previously_correct_id_on_other_person_is_stale_transfer(self):
        outcomes = MODULE.classify_sequence(
            frame_indices=[0, 1],
            target_by_frame={0: target_obs(0), 1: target_obs(1)},
            candidates_by_frame={0: [], 1: []},
            other_people_by_frame={0: [], 1: [other_person(1)]},
            outputs_by_frame={
                0: output(0, 7, TARGET_BOX),
                1: output(1, 7, OTHER_BOX),
            },
            match_config=CONFIG,
        )

        assert outcomes[0].outcome == MODULE.OUTCOME_CORRECT_TARGET
        assert outcomes[1].outcome == MODULE.OUTCOME_STALE_ID_TRANSFER
        assert outcomes[1].output_tracker_identity == 7

    def test_unmatched_wrong_output_falls_back(self):
        hallucinated_box = (900.0, 900.0, 950.0, 950.0)
        result = classify_one_frame(
            target=target_obs(0),
            others=[other_person(0)],
            output_msg=output(0, 42, hallucinated_box),
        )

        assert result.outcome == MODULE.OUTCOME_WRONG_UNMATCHED


class TestWrongNeverMergedWithLost:
    def test_wrong_person_outcomes_disjoint_from_lost_outcomes(self):
        lost_like = {
            MODULE.OUTCOME_SAFE_SUPPRESSION,
            MODULE.OUTCOME_CANDIDATE_ABSENT,
            MODULE.OUTCOME_PHYSICAL_ABSENCE,
            MODULE.OUTCOME_AMBIGUOUS_CANDIDATE,
        }

        assert not (MODULE.WRONG_PERSON_OUTCOMES & lost_like)


class TestSummarize:
    def test_counts_and_fractions(self):
        outcomes = [
            MODULE.FrameOutcome(0, MODULE.OUTCOME_CORRECT_TARGET, 1, 1.0, None, ""),
            MODULE.FrameOutcome(1, MODULE.OUTCOME_DISTRACTOR_SELECTION, 2, 0.0, 5, ""),
            MODULE.FrameOutcome(2, MODULE.OUTCOME_SAFE_SUPPRESSION, None, None, None, ""),
        ]

        summary = MODULE.summarize(outcomes)

        assert summary["total_frames"] == 3
        assert summary["counts"][MODULE.OUTCOME_CORRECT_TARGET] == 1
        assert summary["wrong_person_count"] == 1
        assert summary["wrong_person_fraction"] == 1 / 3
        assert summary["lost_or_suppressed_count"] == 1
