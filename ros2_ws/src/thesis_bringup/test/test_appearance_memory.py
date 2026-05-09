import numpy as np

from thesis_bringup.appearance_memory import (
    AppearanceConfig,
    bbox_cxcywh_to_xyxy,
    clip_xyxy_bbox,
    cosine_similarity,
    extract_crop,
    extract_hsv_upper_lower_feature,
    update_feature_memory,
)


def test_bbox_cxcywh_to_xyxy():
    assert bbox_cxcywh_to_xyxy(50, 60, 20, 10) == (40, 55, 60, 65)


def test_clip_xyxy_bbox_clips_to_image():
    out = clip_xyxy_bbox((-10, -5, 120, 90), image_width=100, image_height=80)
    assert out == (0, 0, 100, 80)


def test_extract_crop_rejects_tiny_bbox():
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    crop = extract_crop(image, (10, 10, 50, 20), min_height=30)
    assert crop is None


def test_extract_hsv_feature_shape():
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    image[:, :, 1] = 255

    cfg = AppearanceConfig(h_bins=16, s_bins=8, min_bbox_height=30)
    feat = extract_hsv_upper_lower_feature(image, (10, 10, 90, 90), cfg)

    assert feat is not None
    assert feat.shape == (16 * 8 * 2,)
    assert np.isclose(np.linalg.norm(feat), 1.0)


def test_same_colour_similarity_high():
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    image[:, :, 2] = 255

    cfg = AppearanceConfig()
    a = extract_hsv_upper_lower_feature(image, (10, 10, 90, 90), cfg)
    b = extract_hsv_upper_lower_feature(image, (20, 20, 80, 80), cfg)

    assert cosine_similarity(a, b) > 0.99


def test_different_colour_similarity_lower():
    red = np.zeros((100, 100, 3), dtype=np.uint8)
    red[:, :, 2] = 255

    blue = np.zeros((100, 100, 3), dtype=np.uint8)
    blue[:, :, 0] = 255

    cfg = AppearanceConfig()
    a = extract_hsv_upper_lower_feature(red, (10, 10, 90, 90), cfg)
    b = extract_hsv_upper_lower_feature(blue, (10, 10, 90, 90), cfg)

    assert cosine_similarity(a, b) < 0.5


def test_update_feature_memory_initialises_and_normalises():
    candidate = np.ones(256, dtype=np.float32)
    memory = update_feature_memory(None, candidate)

    assert memory is not None
    assert np.isclose(np.linalg.norm(memory), 1.0)


def test_update_feature_memory_keeps_existing_on_none_candidate():
    memory = np.ones(256, dtype=np.float32)
    candidate = None

    out = update_feature_memory(memory, candidate)

    assert out is memory
