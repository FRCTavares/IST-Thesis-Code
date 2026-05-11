import numpy as np

from thesis_bringup.target_memory import CandidateTrack
from thesis_bringup.nodes.target_memory_node import TargetMemoryNode


def tr(track_id=1, bbox=(10, 10, 80, 90), score=0.9):
    return CandidateTrack(track_id=track_id, bbox=bbox, score=score)


def make_node_without_ros_init():
    # Bypass Node.__init__. We only test the pure helper method.
    node = object.__new__(TargetMemoryNode)
    node._appearance_enabled = False
    node._latest_image_bgr = None
    node._latest_image_seen_ns = None
    node._appearance_max_image_age_ms = 250.0
    node._last_appearance_candidates = 0
    node._last_appearance_features_valid = 0
    node._last_appearance_image_age_ms = None
    node._last_appearance_skip_reason = "disabled"
    return node


def test_attach_appearance_returns_same_candidates_when_disabled():
    node = make_node_without_ros_init()
    candidates = [tr()]

    out = node._attach_appearance_features(candidates)

    assert out is candidates
    assert out[0].appearance is None


    assert node._last_appearance_candidates == 1
    assert node._last_appearance_features_valid == 0
    assert node._last_appearance_skip_reason == "disabled"


def test_attach_appearance_returns_same_candidates_without_image():
    node = make_node_without_ros_init()
    node._appearance_enabled = True

    candidates = [tr()]
    out = node._attach_appearance_features(candidates)

    assert out is candidates
    assert out[0].appearance is None


def test_attach_appearance_adds_feature_for_fresh_image():
    import time
    from thesis_bringup.appearance_memory import AppearanceConfig

    node = make_node_without_ros_init()
    node._appearance_enabled = True
    node._appearance_cfg = AppearanceConfig(h_bins=16, s_bins=8, min_bbox_height=30)
    node._latest_image_seen_ns = time.monotonic_ns()

    image = np.zeros((120, 120, 3), dtype=np.uint8)
    image[:, :, 2] = 255
    node._latest_image_bgr = image

    candidates = [tr(bbox=(10, 10, 90, 100))]
    out = node._attach_appearance_features(candidates)

    assert out is not candidates
    assert out[0].appearance is not None
    assert out[0].appearance.shape == (16 * 8 * 2,)
    assert np.isclose(np.linalg.norm(out[0].appearance), 1.0)


    assert node._last_appearance_candidates == 1
    assert node._last_appearance_features_valid == 1
    assert node._last_appearance_image_age_ms is not None
    assert node._last_appearance_skip_reason == "ok"


def test_attach_appearance_rejects_stale_image():
    import time
    from thesis_bringup.appearance_memory import AppearanceConfig

    node = make_node_without_ros_init()
    node._appearance_enabled = True
    node._appearance_cfg = AppearanceConfig(h_bins=16, s_bins=8, min_bbox_height=30)
    node._appearance_max_image_age_ms = 10.0
    node._latest_image_seen_ns = time.monotonic_ns() - int(100e6)

    image = np.zeros((120, 120, 3), dtype=np.uint8)
    image[:, :, 2] = 255
    node._latest_image_bgr = image

    candidates = [tr(bbox=(10, 10, 90, 100))]
    out = node._attach_appearance_features(candidates)

    assert out is candidates
    assert out[0].appearance is None


def test_attach_appearance_rejects_tiny_bbox():
    import time
    from thesis_bringup.appearance_memory import AppearanceConfig

    node = make_node_without_ros_init()
    node._appearance_enabled = True
    node._appearance_cfg = AppearanceConfig(h_bins=16, s_bins=8, min_bbox_height=30)
    node._latest_image_seen_ns = time.monotonic_ns()

    image = np.zeros((120, 120, 3), dtype=np.uint8)
    image[:, :, 2] = 255
    node._latest_image_bgr = image

    candidates = [tr(bbox=(10, 10, 90, 20))]
    out = node._attach_appearance_features(candidates)

    assert out is not candidates
    assert out[0].appearance is None


def test_image_derived_appearance_can_change_tim_match_decision():
    import time

    from thesis_bringup.appearance_memory import AppearanceConfig
    from thesis_bringup.target_memory import (
        TargetIdentityMemory,
        TargetMemoryConfig,
        TargetState,
    )

    node = make_node_without_ros_init()
    node._appearance_enabled = True
    node._appearance_cfg = AppearanceConfig(h_bins=16, s_bins=8, min_bbox_height=30)
    node._appearance_max_image_age_ms = 250.0

    # Frame 0: operator selects a red target.
    initial_image = np.zeros((180, 220, 3), dtype=np.uint8)
    initial_image[40:150, 50:100, 2] = 255  # red in BGR

    node._latest_image_bgr = initial_image
    node._latest_image_seen_ns = time.monotonic_ns()

    selected = node._attach_appearance_features([
        tr(track_id=5, bbox=(50, 40, 100, 150), score=0.90)
    ])[0]

    assert selected.appearance is not None

    tim = TargetIdentityMemory(
        TargetMemoryConfig(
            image_width=220,
            image_height=180,
            max_uncertain_frames=1,
            max_lost_frames=8,
            appearance_enabled=True,
            appearance_weight=0.50,
            appearance_min_similarity=0.30,
            appearance_ambiguous_only=False,
            ambiguity_margin=0.001,
        )
    )
    tim.select(selected)

    # Frame 1: the geometrically closest candidate is blue, while the correct
    # red target shifted to the side. Appearance should let TIM select red.
    current_image = np.zeros((180, 220, 3), dtype=np.uint8)
    current_image[40:150, 50:100, 0] = 255   # wrong candidate, blue in BGR
    current_image[40:150, 105:155, 2] = 255  # correct candidate, red in BGR

    node._latest_image_bgr = current_image
    node._latest_image_seen_ns = time.monotonic_ns()

    candidates = node._attach_appearance_features([
        tr(track_id=10, bbox=(50, 40, 100, 150), score=0.90),
        tr(track_id=11, bbox=(105, 40, 155, 150), score=0.90),
    ])

    assert candidates[0].appearance is not None
    assert candidates[1].appearance is not None

    out = tim.update(candidates)

    assert out.best_score is not None
    assert out.best_score.track_id == 11
    assert out.best_score.appearance_used
    assert out.target_track_id == 11
    assert out.state == TargetState.REACQUIRED

