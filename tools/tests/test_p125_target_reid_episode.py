"""Synthetic Target-ReID episode timing and publication tests."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import numpy as np


MODULE_PATH = Path(__file__).resolve().parents[1] / "issues/p125/target_reid_episode.py"
SPEC = importlib.util.spec_from_file_location("p125_target_reid_episode", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def frame(index, tracks):
    return {
        "normalized_frame_index": index,
        "logical_frame_stamp_ns": (index + 1) * 1_000_000_000,
        "tracks": [
            {"track_id": identity, "bbox_xyxy": list(box), "score": 0.8}
            for identity, box in tracks
        ],
    }


BOX = (2.0, 4.0, 12.0, 14.0)
OTHER = (20.0, 25.0, 30.0, 35.0)


class FakeRuntime:
    def __init__(self, selected_id):
        self.selected_id = selected_id
        self.stamps = []
        self.messages = []

    def add_image(self, stamp, image):
        self.stamps.append(stamp)
        return image == "synthetic"

    def process_tracks(self, message):
        self.messages.append(message)
        selected = next((track for track in message.tracks if track.id == self.selected_id), None)
        bootstrap = len(self.messages) == 1
        candidate = None if bootstrap or selected is None else SimpleNamespace(
            track_id=selected.id,
            bbox_xyxy=(selected.cx - selected.w / 2, selected.cy - selected.h / 2,
                       selected.cx + selected.w / 2, selected.cy + selected.h / 2),
        )
        return SimpleNamespace(
            anchor_ready=True,
            decision=SimpleNamespace(published=candidate is not None, selected_candidate=candidate),
        )


def test_confirmation_is_anchor_only_and_later_publications_are_scored():
    frames = [
        frame(0, [(7, BOX)]),
        frame(1, [(7, BOX)]),
        frame(2, [(7, BOX), (8, OTHER)]),
        frame(3, [(8, OTHER)]),
    ]
    runtimes = []
    def factory(selected_id):
        runtime = FakeRuntime(selected_id)
        runtimes.append(runtime)
        return runtime
    boxes, identities, bootstrap = MODULE.target_reid_authority_maps(
        tracker_frames=frames,
        initialization=SimpleNamespace(success=True, initialization_frame_index=1,
                                       initial_tracker_identity=7),
        runtime_factory=factory,
        image_for_frame=lambda _: "synthetic",
    )
    assert bootstrap == 1
    assert boxes == {0: None, 1: None, 2: BOX, 3: None}
    assert identities == {0: None, 1: None, 2: 7, 3: None}
    assert runtimes[0].stamps == [2_000_000_000, 3_000_000_000, 4_000_000_000]
    assert runtimes[0].messages[0].tracks[0].cx == 7.0


def test_failed_initialization_never_opens_runtime_or_images():
    frames = [frame(0, [(7, BOX)]), frame(1, [])]
    def forbidden(*args):
        raise AssertionError("failure must not invoke runtime or image reader")
    boxes, identities, bootstrap = MODULE.target_reid_authority_maps(
        tracker_frames=frames,
        initialization=SimpleNamespace(success=False),
        runtime_factory=forbidden,
        image_for_frame=forbidden,
    )
    assert boxes == {0: None, 1: None}
    assert identities == {0: None, 1: None}
    assert bootstrap is None


def test_anchor_failure_retains_no_output_for_episode():
    class NoAnchor(FakeRuntime):
        def process_tracks(self, message):
            result = super().process_tracks(message)
            result.anchor_ready = False
            return result
    boxes, identities, bootstrap = MODULE.target_reid_authority_maps(
            tracker_frames=[frame(0, [(7, BOX)])],
            initialization=SimpleNamespace(success=True, initialization_frame_index=0,
                                           initial_tracker_identity=7),
            runtime_factory=NoAnchor,
            image_for_frame=lambda _: "synthetic",
        )
    assert boxes == {0: None}
    assert identities == {0: None}
    assert bootstrap is None


def test_sequence_scorer_retains_failed_initialization():
    scorer_path = MODULE_PATH.with_name("write_target_reid_sequence.py")
    spec = importlib.util.spec_from_file_location("p125_target_reid_sequence", scorer_path)
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
    frames = [frame(index, [(7, BOX), (8, BOX)]) for index in (0, 1)]
    result = scorer.score_target_reid_episodes(
        split="val", sequence_name="synthetic", episodes=[episode],
        gt_rows=rows, tracker_frames=frames,
        initialization_rules={"minimum_match_iou": 0.5,
                              "minimum_match_margin": 0.1, "confirmation_frames": 2},
        evaluation_rules={"target_iou_threshold": 0.3,
                          "unique_iou_margin": 0.1,
                          "ambiguous_region_output_coverage_threshold": 0.5},
        runtime_factory=lambda _: pytest.fail("failed initialization opened runtime"),
        image_for_frame=lambda _: pytest.fail("failed initialization opened image"),
    )
    assert result[0]["initialization"]["success"] is False
    assert result[0]["anchor_bootstrap_frame_index"] is None
    assert result[0]["evaluation"]["scoring"]["counts"]["lost_suppressed"] == 2


def test_existing_target_reid_runtime_accepts_logical_replay_messages():
    pytest.importorskip("sensor_msgs")
    root = MODULE_PATH.parents[3]
    sys.path.insert(0, str(root / "tools/analysis"))
    sys.path.insert(0, str(root / "ros2_ws/src/thesis_bringup"))
    sys.path.insert(0, str(root / "ros2_ws/src/thesis_tracker"))
    from p058_target_reid_runtime import TargetReIdRuntime

    class SyntheticAppearance:
        def encode(self, _image, boxes):
            return [np.array([1.0, 0.0], dtype=np.float32) for _ in boxes]

    def factory(selected_id):
        return TargetReIdRuntime(
            model_path="synthetic", selected_track_id=selected_id,
            threshold=0.9, image_width=40, image_height=40,
            mars_backend=SyntheticAppearance(),
        )

    boxes, identities, bootstrap = MODULE.target_reid_authority_maps(
        tracker_frames=[frame(0, [(7, BOX)]), frame(1, [(7, BOX)])],
        initialization=SimpleNamespace(success=True, initialization_frame_index=0,
                                       initial_tracker_identity=7),
        runtime_factory=factory,
        image_for_frame=lambda _: np.zeros((40, 40, 3), dtype=np.uint8),
    )
    assert bootstrap == 0
    assert boxes == {0: None, 1: BOX}
    assert identities == {0: None, 1: 7}
