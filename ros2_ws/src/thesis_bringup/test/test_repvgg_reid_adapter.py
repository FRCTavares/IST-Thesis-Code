"""Tests for the pure RepVGG Person ReID tensor adapter."""

from __future__ import annotations

import numpy as np
import pytest

from thesis_bringup.tim_mars.repvgg_reid_adapter import (
    postprocess_repvgg_embedding,
    prepare_repvgg_crop,
    REPVGG_BACKEND_DESCRIPTOR,
    repvgg_batch_tensor,
    REPVGG_EMBEDDING_DIMENSION,
    REPVGG_HEF_SHA256,
    REPVGG_INPUT_CHANNELS,
    REPVGG_INPUT_HEIGHT,
    REPVGG_INPUT_NAME,
    REPVGG_INPUT_WIDTH,
    REPVGG_OUTPUT_NAME,
)


def test_descriptor_records_the_tracked_hef_contract():
    descriptor = REPVGG_BACKEND_DESCRIPTOR

    assert descriptor.dimension == 512
    assert descriptor.input_height == 256
    assert descriptor.input_width == 128
    assert descriptor.input_channels == 3
    assert descriptor.input_layout == "NHWC"
    assert descriptor.input_dtype == "uint8"
    assert descriptor.raw_output_dtype == "float32"
    assert descriptor.embedding_dtype == "float32"
    assert descriptor.l2_normalized
    assert REPVGG_HEF_SHA256 in descriptor.embedding_space
    assert REPVGG_INPUT_NAME.endswith("/input_layer1")
    assert REPVGG_OUTPUT_NAME.endswith("/fc1")


def test_preprocess_resizes_and_converts_bgr_to_rgb():
    crop = np.empty(
        (7, 5, 3),
        dtype=np.uint8,
    )
    crop[...] = np.array(
        [10, 20, 30],
        dtype=np.uint8,
    )

    prepared = prepare_repvgg_crop(crop)

    assert prepared.rgb_uint8.shape == (
        REPVGG_INPUT_HEIGHT,
        REPVGG_INPUT_WIDTH,
        REPVGG_INPUT_CHANNELS,
    )
    assert prepared.rgb_uint8.dtype == np.uint8
    assert prepared.rgb_uint8.flags.c_contiguous
    assert prepared.source_height == 7
    assert prepared.source_width == 5
    assert prepared.rgb_uint8[0, 0].tolist() == [
        30,
        20,
        10,
    ]


def test_preprocess_does_not_mutate_source_crop():
    crop = np.arange(
        8 * 6 * 3,
        dtype=np.uint8,
    ).reshape(8, 6, 3)
    original = crop.copy()

    prepare_repvgg_crop(crop)

    assert np.array_equal(crop, original)


@pytest.mark.parametrize(
    "crop, message",
    [
        (
            np.zeros(
                (8, 6, 3),
                dtype=np.float32,
            ),
            "dtype uint8",
        ),
        (
            np.zeros(
                (8, 6),
                dtype=np.uint8,
            ),
            "three dimensions",
        ),
        (
            np.zeros(
                (8, 6, 4),
                dtype=np.uint8,
            ),
            "three BGR channels",
        ),
        (
            np.zeros(
                (0, 6, 3),
                dtype=np.uint8,
            ),
            "positive dimensions",
        ),
    ],
)
def test_preprocess_rejects_invalid_crop_contract(
    crop,
    message,
):
    with pytest.raises(
        ValueError,
        match=message,
    ):
        prepare_repvgg_crop(crop)


def test_batch_tensor_adds_one_batch_dimension():
    crop = np.zeros(
        (20, 10, 3),
        dtype=np.uint8,
    )
    prepared = prepare_repvgg_crop(crop)

    batch = repvgg_batch_tensor(prepared)

    assert batch.shape == (
        1,
        REPVGG_INPUT_HEIGHT,
        REPVGG_INPUT_WIDTH,
        REPVGG_INPUT_CHANNELS,
    )
    assert batch.dtype == np.uint8
    assert batch.flags.c_contiguous


def test_postprocess_accepts_one_row_float_batch_and_normalizes():
    raw = np.arange(
        1,
        REPVGG_EMBEDDING_DIMENSION + 1,
        dtype=np.float32,
    )[np.newaxis, :]

    embedding = postprocess_repvgg_embedding(raw)

    assert embedding.shape == (
        REPVGG_EMBEDDING_DIMENSION,
    )
    assert embedding.dtype == np.float32
    assert np.linalg.norm(embedding) == pytest.approx(
        1.0,
        abs=1e-6,
    )
    assert not embedding.flags.writeable


def test_postprocess_rejects_raw_uint8_output():
    raw = np.ones(
        REPVGG_EMBEDDING_DIMENSION,
        dtype=np.uint8,
    )

    with pytest.raises(
        ValueError,
        match="FLOAT32",
    ):
        postprocess_repvgg_embedding(raw)


@pytest.mark.parametrize(
    "raw, message",
    [
        (
            np.ones(
                (2, REPVGG_EMBEDDING_DIMENSION),
                dtype=np.float32,
            ),
            "vector or one-row batch",
        ),
        (
            np.ones(
                128,
                dtype=np.float32,
            ),
            "expected 512",
        ),
        (
            np.zeros(
                REPVGG_EMBEDDING_DIMENSION,
                dtype=np.float32,
            ),
            "zero or invalid norm",
        ),
        (
            np.full(
                REPVGG_EMBEDDING_DIMENSION,
                np.nan,
                dtype=np.float32,
            ),
            "non-finite",
        ),
    ],
)
def test_postprocess_rejects_invalid_output(
    raw,
    message,
):
    with pytest.raises(
        ValueError,
        match=message,
    ):
        postprocess_repvgg_embedding(raw)
