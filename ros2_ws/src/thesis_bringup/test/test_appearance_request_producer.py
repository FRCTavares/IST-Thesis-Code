"""Tests for pure causal appearance request-crop staging."""

from types import SimpleNamespace

import numpy as np
import pytest

from thesis_bringup.tim_mars.appearance_request_producer import (
    AppearanceRequestCrop,
    build_appearance_request_crops,
)
from thesis_bringup.tim_mars.target_memory import CandidateTrack


def candidate(
    track_id: int,
    bbox,
) -> CandidateTrack:
    """Construct one candidate with unchanged source geometry."""
    return CandidateTrack(
        track_id=int(track_id),
        bbox=tuple(float(value) for value in bbox),
        score=0.9,
        unclipped_bbox=tuple(
            float(value)
            for value in bbox
        ),
    )


def quality(
    *,
    encoding_eligible: bool,
):
    """Return the minimum crop-quality contract used by the producer."""
    return SimpleNamespace(
        encoding_eligible=bool(
            encoding_eligible
        )
    )


def source_image() -> np.ndarray:
    """Construct a deterministic source image."""
    return np.arange(
        240 * 320 * 3,
        dtype=np.uint8,
    ).reshape(240, 320, 3)


def test_stages_requested_crop_with_complete_provenance():
    """Map, copy and freeze one requested crop."""
    image = source_image()
    original = image.copy()

    candidates = (
        candidate(
            7,
            (100.0, 160.0, 300.0, 480.0),
        ),
        candidate(
            9,
            (320.0, 160.0, 520.0, 480.0),
        ),
    )

    staged = build_appearance_request_crops(
        candidates=candidates,
        requested_candidate_indices=(0,),
        crop_quality_by_track_id={
            7: quality(encoding_eligible=True),
            9: quality(encoding_eligible=True),
        },
        image_bgr=image,
        candidate_frame_width=640.0,
        candidate_frame_height=640.0,
        source_frame_id=42,
        track_timestamp_ns=1_000,
        source_image_timestamp_ns=900,
        source_image_seq=900,
        frame_generation=3,
        track_generation_by_id={
            7: 5,
            9: 2,
        },
    )

    assert len(staged) == 1

    request_crop = staged[0]

    assert isinstance(
        request_crop,
        AppearanceRequestCrop,
    )
    assert request_crop.source_frame_id == 42
    assert request_crop.track_timestamp_ns == 1_000
    assert request_crop.source_image_timestamp_ns == 900
    assert request_crop.source_image_seq == 900
    assert request_crop.frame_generation == 3
    assert request_crop.candidate_index == 0
    assert request_crop.track_id == 7
    assert request_crop.track_generation == 5
    assert request_crop.source_bbox == pytest.approx(
        (
            50.0,
            60.0,
            150.0,
            180.0,
        )
    )
    assert request_crop.crop_bgr.shape == (
        120,
        100,
        3,
    )
    assert request_crop.crop_bgr.dtype == np.uint8
    assert request_crop.crop_bgr.flags.c_contiguous
    assert not request_crop.crop_bgr.flags.writeable
    assert np.array_equal(
        request_crop.crop_bgr,
        original[60:180, 50:150],
    )

    image.fill(0)

    assert np.array_equal(
        request_crop.crop_bgr,
        original[60:180, 50:150],
    )


def test_filters_requested_but_encoding_ineligible_crop():
    """Do not stage crops rejected by existing crop-quality policy."""
    staged = build_appearance_request_crops(
        candidates=(
            candidate(
                7,
                (100.0, 100.0, 200.0, 300.0),
            ),
        ),
        requested_candidate_indices=(0,),
        crop_quality_by_track_id={
            7: quality(
                encoding_eligible=False
            ),
        },
        image_bgr=source_image(),
        candidate_frame_width=640.0,
        candidate_frame_height=640.0,
        source_frame_id=1,
        track_timestamp_ns=1_000,
        source_image_timestamp_ns=900,
        source_image_seq=900,
        frame_generation=1,
        track_generation_by_id={7: 1},
    )

    assert staged == ()


def test_rejects_requested_candidate_without_generation():
    """A request must never invent tracker-instance ownership."""
    with pytest.raises(
        ValueError,
        match="no active track generation",
    ):
        build_appearance_request_crops(
            candidates=(
                candidate(
                    7,
                    (
                        100.0,
                        100.0,
                        200.0,
                        300.0,
                    ),
                ),
            ),
            requested_candidate_indices=(0,),
            crop_quality_by_track_id={
                7: quality(
                    encoding_eligible=True
                ),
            },
            image_bgr=source_image(),
            candidate_frame_width=640.0,
            candidate_frame_height=640.0,
            source_frame_id=1,
            track_timestamp_ns=1_000,
            source_image_timestamp_ns=900,
            source_image_seq=900,
            frame_generation=1,
            track_generation_by_id={},
        )


def test_rejects_noncausal_image_timestamp():
    """Reject a future image before any transport object is built."""
    with pytest.raises(
        ValueError,
        match="must not be newer",
    ):
        AppearanceRequestCrop(
            source_frame_id=1,
            track_timestamp_ns=900,
            source_image_timestamp_ns=901,
            source_image_seq=901,
            frame_generation=1,
            candidate_index=0,
            track_id=7,
            track_generation=1,
            source_bbox=(
                1.0,
                2.0,
                5.0,
                8.0,
            ),
            crop_bgr=np.zeros(
                (6, 4, 3),
                dtype=np.uint8,
            ),
        )
