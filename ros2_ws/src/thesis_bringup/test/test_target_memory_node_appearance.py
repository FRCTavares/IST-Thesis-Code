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
    return node


def test_attach_appearance_returns_same_candidates_when_disabled():
    node = make_node_without_ros_init()
    candidates = [tr()]

    out = node._attach_appearance_features(candidates)

    assert out is candidates
    assert out[0].appearance is None


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
