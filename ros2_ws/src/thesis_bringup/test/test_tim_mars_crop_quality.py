"""Tests for TIM-MARS crop-quality measurement and geometry provenance."""

from types import SimpleNamespace

import pytest

from thesis_bringup.tim_mars.appearance_attachment import (
    AppearanceAttachmentConfig,
)
from thesis_bringup.tim_mars.crop_quality import (
    CropQualityThresholds,
    measure_crop_qualities,
)
from thesis_bringup.tim_mars.runtime import (
    TimMarsRuntime,
    TimMarsRuntimeConfig,
)
from thesis_bringup.tim_mars.target_memory import (
    TargetMemoryConfig,
)


def thresholds(**overrides):
    values = {
        "min_width_px": 12.0,
        "min_height_px": 24.0,
        "max_clipping_fraction": 0.10,
        "min_aspect_ratio": 0.20,
        "max_aspect_ratio": 1.00,
        "max_overlap_iou_for_memory": 0.10,
        "min_centre_distance_norm_for_memory": 0.04,
    }
    values.update(overrides)
    return CropQualityThresholds(**values)


def test_clean_crop_is_encoding_and_memory_eligible():
    quality = measure_crop_qualities(
        [(100.0, 100.0, 140.0, 180.0)],
        image_width=640,
        image_height=480,
        thresholds=thresholds(),
    )[0]

    assert quality.crop_width_px == 40.0
    assert quality.crop_height_px == 80.0
    assert quality.clipping_fraction == 0.0
    assert quality.aspect_ratio == 0.5
    assert quality.max_iou_with_other == 0.0
    assert quality.min_centre_distance_norm == 1.0
    assert quality.encoding_eligible
    assert quality.memory_update_eligible
    assert quality.rejection_reasons == ()


def test_tiny_crop_is_rejected_before_encoding():
    quality = measure_crop_qualities(
        [(10.0, 10.0, 18.0, 30.0)],
        image_width=640,
        image_height=480,
        thresholds=thresholds(),
    )[0]

    assert not quality.encoding_eligible
    assert not quality.memory_update_eligible
    assert "crop_too_narrow" in quality.rejection_reasons
    assert "crop_too_short" in quality.rejection_reasons


def test_clipping_fraction_uses_unclipped_requested_area():
    quality = measure_crop_qualities(
        [(-10.0, 10.0, 30.0, 60.0)],
        image_width=640,
        image_height=480,
        thresholds=thresholds(
            max_clipping_fraction=0.20,
        ),
    )[0]

    assert quality.crop_width_px == 30.0
    assert quality.crop_height_px == 50.0
    assert quality.clipping_fraction == pytest.approx(
        0.25
    )
    assert not quality.encoding_eligible
    assert "crop_too_clipped" in quality.rejection_reasons


def test_overlap_blocks_memory_but_not_encoding():
    qualities = measure_crop_qualities(
        [
            (100.0, 100.0, 160.0, 240.0),
            (125.0, 100.0, 185.0, 240.0),
        ],
        image_width=640,
        image_height=480,
        thresholds=thresholds(),
    )

    assert all(
        quality.encoding_eligible
        for quality in qualities
    )
    assert all(
        not quality.memory_update_eligible
        for quality in qualities
    )
    assert all(
        "overlap_with_person"
        in quality.rejection_reasons
        for quality in qualities
    )


def test_close_centres_block_memory_without_overlap():
    qualities = measure_crop_qualities(
        [
            (100.0, 100.0, 120.0, 160.0),
            (125.0, 100.0, 145.0, 160.0),
        ],
        image_width=640,
        image_height=480,
        thresholds=thresholds(),
    )

    assert qualities[0].max_iou_with_other == 0.0
    assert qualities[0].encoding_eligible
    assert not qualities[0].memory_update_eligible
    assert (
        "group_centre_too_close"
        in qualities[0].rejection_reasons
    )


def test_runtime_preserves_unclipped_candidate_bbox():
    runtime = TimMarsRuntime(
        TimMarsRuntimeConfig(
            memory=TargetMemoryConfig(
                image_width=100.0,
                image_height=100.0,
            ),
            appearance=AppearanceAttachmentConfig(
                enabled=False,
                max_image_age_ms=250.0,
                compute_min_interval_ms=250.0,
                cache_ttl_ms=750.0,
            ),
            image_width=100.0,
            image_height=100.0,
        )
    )

    track = SimpleNamespace(
        id=1,
        cx=2.0,
        cy=50.0,
        w=20.0,
        h=40.0,
        score=0.9,
    )

    candidate = runtime.candidate_from_track(track)

    assert candidate.unclipped_bbox == (
        -8.0,
        30.0,
        12.0,
        70.0,
    )
    assert candidate.bbox == (
        0.0,
        30.0,
        12.0,
        70.0,
    )


def test_large_unclipped_wide_crop_is_encoding_eligible_but_not_memory_eligible():
    """Wide valid crops may support comparison without contaminating memory."""
    quality = measure_crop_qualities(
        [
            (
                80.0,
                100.0,
                562.0,
                482.0,
            )
        ],
        image_width=640,
        image_height=640,
        thresholds=thresholds(),
    )[0]

    assert quality.crop_width_px == 482.0
    assert quality.crop_height_px == 382.0
    assert quality.clipping_fraction == 0.0
    assert quality.aspect_ratio == pytest.approx(
        482.0 / 382.0
    )

    # Issue #89: this geometry is technically usable by MARS for
    # comparison/reacquisition, but remains outside the conservative
    # positive-memory aspect-ratio contract.
    assert quality.encoding_eligible
    assert not quality.memory_update_eligible
    assert (
        "aspect_ratio_too_wide"
        in quality.rejection_reasons
    )
