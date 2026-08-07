#!/usr/bin/env python3
"""Frame-level physical-target outcome classification for Issue #30.

This is the MOT-style (per-frame ground-truth box) evaluator distinct from
``tim_evaluation.py`` / ``evaluate_tim_event_recovery.py``, which are built
for the ROS 2 sequences' interval-annotation format.

Core invariant: a tracker ID is a temporary candidate label, never the
identity of evaluation. Every classification is anchored to the frozen
physical target established at initialization (Issue #30's Slice 2/13/16),
using IoU correctness against the sequence's own official ground-truth box
for that physical identity -- not tracker-ID continuity -- as the primary
correctness signal. Tracker-candidate matching
(``external_target_initialization.match_frame``) is used only to explain
*why* an incorrect or missing output happened (no candidate present,
ambiguous candidates, or -- via ID history -- whether a wrong output reused
an ID that used to be correct).

A wrong-person output is treated as more severe than a missing one: outcomes
never merge "wrong" and "lost/suppressed/absent".
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

ANALYSIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ANALYSIS_DIR))

from external_target_initialization import (  # noqa: E402
    InitializationConfig,
    PhysicalTargetObservation,
    TrackerCandidateObservation,
    bbox_iou,
    match_frame,
)


BBoxXYXY = tuple[float, float, float, float]

OUTCOME_CORRECT_TARGET = "correct_target"
OUTCOME_CORRECT_RECOVERY = "correct_same_person_recovery"
OUTCOME_SAFE_SUPPRESSION = "safe_suppression"
OUTCOME_PHYSICAL_ABSENCE = "physical_absence_correct"
OUTCOME_CANDIDATE_ABSENT = "target_candidate_absent"
OUTCOME_AMBIGUOUS_CANDIDATE = "ambiguous_candidate"
OUTCOME_DISTRACTOR_SELECTION = "distractor_selection"
OUTCOME_STALE_ID_TRANSFER = "stale_id_transfer"
OUTCOME_WRONG_UNMATCHED = "wrong_unmatched_output"
OUTCOME_WRONG_DURING_ABSENCE = "wrong_output_during_physical_absence"

ALL_OUTCOMES = (
    OUTCOME_CORRECT_TARGET,
    OUTCOME_CORRECT_RECOVERY,
    OUTCOME_SAFE_SUPPRESSION,
    OUTCOME_PHYSICAL_ABSENCE,
    OUTCOME_CANDIDATE_ABSENT,
    OUTCOME_AMBIGUOUS_CANDIDATE,
    OUTCOME_DISTRACTOR_SELECTION,
    OUTCOME_STALE_ID_TRANSFER,
    OUTCOME_WRONG_UNMATCHED,
    OUTCOME_WRONG_DURING_ABSENCE,
)

# Outcomes counted as "wrong physical person" -- the dangerous category that
# must never be merged with lost/suppressed/absent outcomes.
WRONG_PERSON_OUTCOMES = frozenset(
    {
        OUTCOME_DISTRACTOR_SELECTION,
        OUTCOME_STALE_ID_TRANSFER,
        OUTCOME_WRONG_UNMATCHED,
        OUTCOME_WRONG_DURING_ABSENCE,
    }
)


@dataclass(frozen=True)
class SystemOutput:
    """One stream's (raw or TIM-MARS) output at one frame, or none."""

    normalized_frame_index: int
    tracker_identity: Optional[int]
    bbox_xyxy: Optional[BBoxXYXY]


@dataclass(frozen=True)
class OtherPerson:
    """A visible, non-target physical identity at one frame (a distractor)."""

    normalized_frame_index: int
    dataset_identity: object
    bbox_xyxy: BBoxXYXY


@dataclass(frozen=True)
class FrameOutcome:
    normalized_frame_index: int
    outcome: str
    output_tracker_identity: Optional[int]
    correctness_iou: Optional[float]
    matched_other_identity: Optional[object]
    detail: str


def _index_by_frame(
    observations,
) -> dict:
    indexed: dict[int, list] = {}
    for observation in observations:
        indexed.setdefault(
            observation.normalized_frame_index, []
        ).append(observation)
    return indexed


def classify_sequence(
    *,
    frame_indices: list[int],
    target_by_frame: dict[int, PhysicalTargetObservation],
    candidates_by_frame: dict[int, list[TrackerCandidateObservation]],
    other_people_by_frame: dict[int, list[OtherPerson]],
    outputs_by_frame: dict[int, SystemOutput],
    match_config: InitializationConfig,
    correctness_iou_threshold: float = 0.30,
    other_person_iou_threshold: float = 0.30,
) -> list[FrameOutcome]:
    """Classify every frame in ``frame_indices`` into one outcome.

    ``match_config`` reuses the sequence's own frozen
    ``minimum_iou``/``minimum_margin`` initialization thresholds as the
    definition of "a tracker candidate confidently corresponds to the
    target's location", so candidate-absence and ambiguity are judged by the
    same rule already frozen in the manifest, not a newly invented one.
    """

    outcomes: list[FrameOutcome] = []
    ids_ever_correct: set[int] = set()
    last_correct_tracker_identity: Optional[int] = None

    for frame_index in frame_indices:
        target = target_by_frame.get(frame_index)
        output = outputs_by_frame.get(frame_index)
        candidates = candidates_by_frame.get(frame_index, [])
        others = other_people_by_frame.get(frame_index, [])

        has_output = (
            output is not None
            and output.tracker_identity is not None
            and output.bbox_xyxy is not None
        )

        if target is None:
            if not has_output:
                outcomes.append(
                    FrameOutcome(
                        frame_index,
                        OUTCOME_PHYSICAL_ABSENCE,
                        None,
                        None,
                        None,
                        "target not visible; no output published",
                    )
                )
            else:
                outcomes.append(
                    FrameOutcome(
                        frame_index,
                        OUTCOME_WRONG_DURING_ABSENCE,
                        output.tracker_identity,
                        None,
                        None,
                        "output published while target not visible",
                    )
                )
            continue

        if has_output:
            correctness_iou = bbox_iou(target.bbox_xyxy, output.bbox_xyxy)
        else:
            correctness_iou = None

        if has_output and correctness_iou >= correctness_iou_threshold:
            is_recovery = (
                last_correct_tracker_identity is not None
                and output.tracker_identity != last_correct_tracker_identity
            )
            ids_ever_correct.add(output.tracker_identity)
            last_correct_tracker_identity = output.tracker_identity
            outcomes.append(
                FrameOutcome(
                    frame_index,
                    (
                        OUTCOME_CORRECT_RECOVERY
                        if is_recovery
                        else OUTCOME_CORRECT_TARGET
                    ),
                    output.tracker_identity,
                    correctness_iou,
                    None,
                    (
                        "output overlaps target ground truth after a "
                        "tracker-ID change"
                        if is_recovery
                        else "output overlaps target ground truth"
                    ),
                )
            )
            continue

        if has_output:
            best_other = None
            best_other_iou = 0.0
            for other in others:
                iou = bbox_iou(other.bbox_xyxy, output.bbox_xyxy)
                if iou > best_other_iou:
                    best_other_iou = iou
                    best_other = other

            if best_other is not None and (
                best_other_iou >= other_person_iou_threshold
            ):
                if output.tracker_identity in ids_ever_correct:
                    outcomes.append(
                        FrameOutcome(
                            frame_index,
                            OUTCOME_STALE_ID_TRANSFER,
                            output.tracker_identity,
                            correctness_iou,
                            best_other.dataset_identity,
                            "output ID was previously correct but now "
                            "matches a different physical person",
                        )
                    )
                else:
                    outcomes.append(
                        FrameOutcome(
                            frame_index,
                            OUTCOME_DISTRACTOR_SELECTION,
                            output.tracker_identity,
                            correctness_iou,
                            best_other.dataset_identity,
                            "output matches a different, never-correct "
                            "physical person",
                        )
                    )
            else:
                outcomes.append(
                    FrameOutcome(
                        frame_index,
                        OUTCOME_WRONG_UNMATCHED,
                        output.tracker_identity,
                        correctness_iou,
                        None,
                        "output does not match target or any known "
                        "other physical person",
                    )
                )
            continue

        oracle = match_frame(target, candidates, match_config)

        if oracle.accepted:
            outcomes.append(
                FrameOutcome(
                    frame_index,
                    OUTCOME_SAFE_SUPPRESSION,
                    None,
                    None,
                    None,
                    "a confident target candidate existed but no output "
                    "was published",
                )
            )
        elif oracle.reason == "ambiguous_candidate_margin":
            outcomes.append(
                FrameOutcome(
                    frame_index,
                    OUTCOME_AMBIGUOUS_CANDIDATE,
                    None,
                    None,
                    None,
                    "multiple candidates near the target without a "
                    "confident margin, and no output was published",
                )
            )
        else:
            outcomes.append(
                FrameOutcome(
                    frame_index,
                    OUTCOME_CANDIDATE_ABSENT,
                    None,
                    None,
                    None,
                    f"no confident target candidate ({oracle.reason})",
                )
            )

    return outcomes


def summarize(outcomes: list[FrameOutcome]) -> dict[str, object]:
    counts = {name: 0 for name in ALL_OUTCOMES}
    for outcome in outcomes:
        counts[outcome.outcome] += 1

    total = len(outcomes)
    wrong_person_count = sum(
        counts[name] for name in WRONG_PERSON_OUTCOMES
    )

    return {
        "total_frames": total,
        "counts": counts,
        "correct_fraction": (
            (counts[OUTCOME_CORRECT_TARGET] + counts[OUTCOME_CORRECT_RECOVERY])
            / total
            if total
            else None
        ),
        "wrong_person_count": wrong_person_count,
        "wrong_person_fraction": (
            wrong_person_count / total if total else None
        ),
        "lost_or_suppressed_count": (
            counts[OUTCOME_SAFE_SUPPRESSION]
            + counts[OUTCOME_CANDIDATE_ABSENT]
        ),
    }
