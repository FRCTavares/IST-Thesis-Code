"""Focused tests for the Issue #44 observational embedding extractor."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[2]

EXTRACTOR = (
    ROOT
    / "tools"
    / "analysis"
    / "extract_p044_observational_embeddings.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "p044_observational_embedding_extractor",
        EXTRACTOR,
    )

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def request_message():
    return SimpleNamespace(
        crop_height=2,
        crop_width=2,
        crop_step=8,
        crop_encoding="bgr8",
        crop_data=[
            1, 2, 3,
            4, 5, 6,
            90, 91,
            7, 8, 9,
            10, 11, 12,
            92, 93,
        ],
    )


def test_decode_crop_preserves_pixels_and_removes_padding():
    module = load_module()

    crop = module.decode_crop(request_message())

    assert crop.shape == (2, 2, 3)
    assert crop.dtype == np.uint8
    assert crop.flags.c_contiguous

    assert crop.tolist() == [
        [
            [1, 2, 3],
            [4, 5, 6],
        ],
        [
            [7, 8, 9],
            [10, 11, 12],
        ],
    ]


def test_decode_crop_rejects_wrong_encoding():
    module = load_module()
    message = request_message()
    message.crop_encoding = "rgb8"

    with pytest.raises(
        ValueError,
        match="unsupported crop encoding",
    ):
        module.decode_crop(message)


def test_decode_crop_rejects_short_rows():
    module = load_module()
    message = request_message()
    message.crop_step = 5
    message.crop_data = message.crop_data[:10]

    with pytest.raises(
        ValueError,
        match="crop step",
    ):
        module.decode_crop(message)


def test_decode_crop_rejects_wrong_byte_length():
    module = load_module()
    message = request_message()
    message.crop_data = message.crop_data[:-1]

    with pytest.raises(
        ValueError,
        match="crop byte length mismatch",
    ):
        module.decode_crop(message)


def test_validate_vector_accepts_finite_nonzero_vector():
    module = load_module()

    source = np.ones(
        128,
        dtype=np.float32,
    )
    source /= np.linalg.norm(source)

    vector, norm = module.validate_vector(
        source,
        dimension=128,
        label="MARS",
    )

    assert vector.shape == (128,)
    assert vector.dtype == np.float32
    assert norm == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("values", "message"),
    [
        (
            np.ones(512, dtype=np.float32),
            "dimension mismatch",
        ),
        (
            np.zeros(128, dtype=np.float32),
            "zero or invalid norm",
        ),
        (
            np.full(
                128,
                np.nan,
                dtype=np.float32,
            ),
            "non-finite",
        ),
    ],
)
def test_validate_vector_rejects_invalid_values(
    values,
    message,
):
    module = load_module()

    with pytest.raises(
        ValueError,
        match=message,
    ):
        module.validate_vector(
            values,
            dimension=128,
            label="MARS",
        )


def test_storage_identifier_defaults_to_mcap(tmp_path):
    module = load_module()

    assert (
        module.storage_identifier(tmp_path)
        == "mcap"
    )


def test_source_preserves_observational_boundary():
    source = EXTRACTOR.read_text(
        encoding="utf-8"
    )

    required = (
        "MarsReIdBackend",
        'REQUEST_TOPIC = "/appearance/reid/request"',
        'RESULT_TOPIC = "/appearance/reid/result"',
        'STATUS_TOPIC = "/target_memory_mars/status"',
        '"cpu_mars_authoritative": True',
        '"repvgg_observational_only": True',
        '"cross_model_similarity_computed": False',
        '"runtime_modified": False',
        '"canonical_policy_changed": False',
        "paired_embeddings.jsonl",
        "rejected_observations.jsonl",
    )

    for token in required:
        assert token in source, token

    forbidden = (
        "np.dot(mars_vector, repvgg_vector)",
        "np.dot(repvgg_vector, mars_vector)",
        "mars_vector @ repvgg_vector",
        "repvgg_vector @ mars_vector",
        "cosine_similarity(mars_vector",
        "cosine_similarity(repvgg_vector",
    )

    for token in forbidden:
        assert token not in source, token
