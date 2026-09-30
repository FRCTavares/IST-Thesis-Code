"""Synthetic TIM-MARS selection and controller-output timing checks."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "issues/p125/tim_mars_episode.py"
SPEC = importlib.util.spec_from_file_location("p125_tim_mars_episode", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

BOX = (2.0, 4.0, 12.0, 14.0)


def frame(index, identities):
    return {
        "source_frame_number": index + 1,
        "normalized_frame_index": index,
        "logical_frame_stamp_ns": (index + 1) * 33_333_333,
        "tracks": [
            {"track_id": identity, "bbox_xyxy": list(BOX), "score": 0.8}
            for identity in identities
        ],
    }


class FakeTim:
    def __init__(self, selected_id):
        self.selected_id = selected_id
        self.messages = []
        self.images = []

    def add_image(self, stamp, image):
        self.images.append((stamp, image))
        return True

    def process_tracks(self, message):
        self.messages.append(message)
        target = next((track for track in message.tracks if track.id == self.selected_id), None)
        control_valid = target is not None and message.frame_id != 3
        return SimpleNamespace(output=SimpleNamespace(
            control_valid=control_valid,
            bbox=BOX if control_valid else None,
            target_track_id=self.selected_id if control_valid else None,
        ))


def test_tim_selection_starts_on_confirmation_and_uses_control_valid_only():
    frames = [frame(0, [7]), frame(1, [7]), frame(2, [7]), frame(3, [])]
    runtimes = []
    def factory(selected_id):
        runtime = FakeTim(selected_id)
        runtimes.append(runtime)
        return runtime
    boxes, identities = MODULE.tim_mars_authority_maps(
        tracker_frames=frames,
        initialization=SimpleNamespace(success=True, initialization_frame_index=1,
                                       initial_tracker_identity=7),
        runtime_factory=factory,
        image_for_frame=lambda _: "synthetic",
    )
    assert boxes == {0: None, 1: BOX, 2: None, 3: None}
    assert identities == {0: None, 1: 7, 2: None, 3: None}
    assert [message.frame_id for message in runtimes[0].messages] == [2, 3, 4]
    assert runtimes[0].messages[0].tracks[0].score == 0.8
    assert [stamp for stamp, _ in runtimes[0].images] == [66_666_666, 99_999_999, 133_333_332]


def test_failed_initialization_never_opens_tim_or_images():
    def forbidden(*args):
        raise AssertionError("failed selection opened runtime or image")
    boxes, identities = MODULE.tim_mars_authority_maps(
        tracker_frames=[frame(0, [7]), frame(1, [])],
        initialization=SimpleNamespace(success=False),
        runtime_factory=forbidden,
        image_for_frame=forbidden,
    )
    assert boxes == {0: None, 1: None}
    assert identities == {0: None, 1: None}


def test_missing_confirmation_frame_is_rejected():
    with pytest.raises(ValueError, match="confirmation frame"):
        MODULE.tim_mars_authority_maps(
            tracker_frames=[frame(0, [7])],
            initialization=SimpleNamespace(success=True, initialization_frame_index=1,
                                           initial_tracker_identity=7),
            runtime_factory=FakeTim,
            image_for_frame=lambda _: "synthetic",
        )


def test_sequence_scorer_retains_failed_initialization():
    scorer_path = MODULE_PATH.with_name("write_tim_mars_sequence.py")
    spec = importlib.util.spec_from_file_location("p125_tim_mars_sequence", scorer_path)
    assert spec is not None and spec.loader is not None
    scorer = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = scorer
    spec.loader.exec_module(scorer)
    episode = {
        "split": "val", "sequence_name": "synthetic", "dataset_identity": 3,
        "selection_frame_index": 0, "initialization_end_frame_inclusive": 1,
    }
    rows = [SimpleNamespace(
        normalized_frame_index=index, identity=3, bbox_xyxy=BOX,
        include_as_person_candidate=True, class_id=1,
    ) for index in (0, 1)]
    frames = [frame(index, [7, 8]) for index in (0, 1)]
    results = scorer.score_tim_mars_episodes(
        split="val", sequence_name="synthetic", episodes=[episode],
        gt_rows=rows, tracker_frames=frames,
        initialization_rules={"minimum_match_iou": 0.5,
                              "minimum_match_margin": 0.1, "confirmation_frames": 2},
        evaluation_rules={"target_iou_threshold": 0.3,
                          "unique_iou_margin": 0.1,
                          "ambiguous_region_output_coverage_threshold": 0.5},
        runtime_factory=lambda _: pytest.fail("failed selection opened TIM"),
        image_for_frame=lambda _: pytest.fail("failed selection opened image"),
    )
    assert results[0]["initialization"]["success"] is False
    assert results[0]["evaluation"]["scoring"]["counts"]["lost_suppressed"] == 2


def test_sequence_scorer_uses_confirmed_tim_publication():
    scorer_path = MODULE_PATH.with_name("write_tim_mars_sequence.py")
    spec = importlib.util.spec_from_file_location("p125_tim_mars_sequence_success", scorer_path)
    assert spec is not None and spec.loader is not None
    scorer = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = scorer
    spec.loader.exec_module(scorer)
    episode = {
        "split": "val", "sequence_name": "synthetic", "dataset_identity": 3,
        "selection_frame_index": 0, "initialization_end_frame_inclusive": 2,
    }
    rows = [SimpleNamespace(
        normalized_frame_index=index, identity=3, bbox_xyxy=BOX,
        include_as_person_candidate=True, class_id=1,
    ) for index in (0, 1, 2)]
    results = scorer.score_tim_mars_episodes(
        split="val", sequence_name="synthetic", episodes=[episode],
        gt_rows=rows, tracker_frames=[frame(index, [7]) for index in (0, 1, 2)],
        initialization_rules={"minimum_match_iou": 0.5,
                              "minimum_match_margin": 0.1, "confirmation_frames": 2},
        evaluation_rules={"target_iou_threshold": 0.3,
                          "unique_iou_margin": 0.1,
                          "ambiguous_region_output_coverage_threshold": 0.5},
        runtime_factory=FakeTim,
        image_for_frame=lambda _: "synthetic",
    )
    assert results[0]["initialization"]["success"] is True
    assert results[0]["initialization"]["initialization_frame_index"] == 1
    assert results[0]["evaluation"]["scoring"]["counts"]["correct"] == 1
    assert results[0]["evaluation"]["scoring"]["counts"]["lost_suppressed"] == 2


def test_existing_tim_runtime_accepts_logical_replay_messages():
    pytest.importorskip("sensor_msgs")
    import numpy as np
    root = MODULE_PATH.parents[3]
    sys.path.insert(0, str(root / "ros2_ws/src/thesis_bringup"))
    sys.path.insert(0, str(root / "ros2_ws/src/thesis_tracker"))
    from thesis_bringup.tim_mars.appearance_attachment import AppearanceAttachmentConfig
    from thesis_bringup.tim_mars.runtime import TimMarsRuntime, TimMarsRuntimeConfig
    from thesis_bringup.tim_mars.target_memory import TargetMemoryConfig

    def factory(selected_id):
        return TimMarsRuntime(config=TimMarsRuntimeConfig(
            memory=TargetMemoryConfig(image_width=40, image_height=40,
                                      appearance_enabled=False),
            appearance=AppearanceAttachmentConfig(enabled=False,
                max_image_age_ms=250, compute_min_interval_ms=250,
                cache_ttl_ms=750),
            image_width=40, image_height=40,
            selected_track_id=selected_id,
        ))

    boxes, identities = MODULE.tim_mars_authority_maps(
        tracker_frames=[frame(0, [7]), frame(1, [7])],
        initialization=SimpleNamespace(success=True, initialization_frame_index=0,
                                       initial_tracker_identity=7),
        runtime_factory=factory,
        image_for_frame=lambda _: np.zeros((40, 40, 3), dtype=np.uint8),
    )
    assert boxes[0] == BOX
    assert identities[0] == 7
