"""Pure preprocessing and postprocessing for Hailo RepVGG Person ReID.

The tracked HEF has this host-visible tensor contract:

* input: UINT8 NHWC 256x128x3;
* output: one 512-dimensional embedding.

The source image used by TIM-MARS is BGR. The model contract is RGB, so this
adapter resizes a copied candidate crop and converts BGR to RGB. Input
normalization is compiled into the HEF and must not be duplicated on the host.

The future Hailo worker must request FLOAT32 host output from HailoRT. Raw
UINT8 output is deliberately rejected here to prevent accidental use of
quantized bytes as cosine-space embeddings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from thesis_bringup.tim_mars.appearance_async import (
    AppearanceBackendDescriptor,
)


REPVGG_HEF_SHA256 = (
    "f6e172a073896b5ff2640b9f861e804b"
    "23c8093102518d2d0aa2d6e40e047a34"
)

REPVGG_INPUT_NAME = (
    "repvgg_a0_person_reid_512/input_layer1"
)
REPVGG_OUTPUT_NAME = (
    "repvgg_a0_person_reid_512/fc1"
)

REPVGG_INPUT_HEIGHT = 256
REPVGG_INPUT_WIDTH = 128
REPVGG_INPUT_CHANNELS = 3
REPVGG_EMBEDDING_DIMENSION = 512

REPVGG_EMBEDDING_SPACE = (
    "repvgg-a0-person-reid-512:"
    + REPVGG_HEF_SHA256
)

REPVGG_BACKEND_DESCRIPTOR = AppearanceBackendDescriptor(
    name="hailo-repvgg-a0-person-reid-512",
    embedding_space=REPVGG_EMBEDDING_SPACE,
    dimension=REPVGG_EMBEDDING_DIMENSION,
    input_height=REPVGG_INPUT_HEIGHT,
    input_width=REPVGG_INPUT_WIDTH,
    input_channels=REPVGG_INPUT_CHANNELS,
    input_layout="NHWC",
    input_dtype="uint8",
    raw_output_dtype="float32",
    embedding_dtype="float32",
    l2_normalized=True,
)


@dataclass(frozen=True)
class RepVggPreparedCrop:
    """One validated host tensor ready for HailoRT input."""

    rgb_uint8: np.ndarray
    source_height: int
    source_width: int
    resize_interpolation: str = "linear"

    def __post_init__(self) -> None:
        expected_shape = (
            REPVGG_INPUT_HEIGHT,
            REPVGG_INPUT_WIDTH,
            REPVGG_INPUT_CHANNELS,
        )

        if self.rgb_uint8.shape != expected_shape:
            raise ValueError(
                "prepared RepVGG crop has shape "
                f"{self.rgb_uint8.shape}; expected {expected_shape}"
            )

        if self.rgb_uint8.dtype != np.uint8:
            raise ValueError(
                "prepared RepVGG crop must be uint8"
            )

        if not self.rgb_uint8.flags.c_contiguous:
            raise ValueError(
                "prepared RepVGG crop must be C-contiguous"
            )

        if int(self.source_height) <= 0:
            raise ValueError(
                "source crop height must be positive"
            )

        if int(self.source_width) <= 0:
            raise ValueError(
                "source crop width must be positive"
            )


def prepare_repvgg_crop(
    crop_bgr: Any,
) -> RepVggPreparedCrop:
    """Convert one copied BGR candidate crop to fixed RGB UINT8 NHWC."""
    crop = np.asarray(crop_bgr)

    if crop.dtype != np.uint8:
        raise ValueError(
            "RepVGG input crop must have dtype uint8"
        )

    if crop.ndim != 3:
        raise ValueError(
            "RepVGG input crop must have three dimensions"
        )

    if crop.shape[2] != REPVGG_INPUT_CHANNELS:
        raise ValueError(
            "RepVGG input crop must contain three BGR channels"
        )

    source_height = int(crop.shape[0])
    source_width = int(crop.shape[1])

    if source_height <= 0 or source_width <= 0:
        raise ValueError(
            "RepVGG input crop must have positive dimensions"
        )

    if not np.all(np.isfinite(crop)):
        raise ValueError(
            "RepVGG input crop contains non-finite values"
        )

    resized_bgr = cv2.resize(
        crop,
        (
            REPVGG_INPUT_WIDTH,
            REPVGG_INPUT_HEIGHT,
        ),
        interpolation=cv2.INTER_LINEAR,
    )

    rgb = cv2.cvtColor(
        resized_bgr,
        cv2.COLOR_BGR2RGB,
    )

    prepared = np.ascontiguousarray(
        rgb,
        dtype=np.uint8,
    )

    return RepVggPreparedCrop(
        rgb_uint8=prepared,
        source_height=source_height,
        source_width=source_width,
    )


def repvgg_batch_tensor(
    prepared: RepVggPreparedCrop,
) -> np.ndarray:
    """Add the single-frame batch dimension required by inference."""
    batch = np.ascontiguousarray(
        prepared.rgb_uint8[np.newaxis, ...],
        dtype=np.uint8,
    )

    expected_shape = (
        1,
        REPVGG_INPUT_HEIGHT,
        REPVGG_INPUT_WIDTH,
        REPVGG_INPUT_CHANNELS,
    )

    if batch.shape != expected_shape:
        raise ValueError(
            f"RepVGG batch has shape {batch.shape}; "
            f"expected {expected_shape}"
        )

    return batch


def postprocess_repvgg_embedding(
    raw_output: Any,
) -> np.ndarray:
    """Validate and L2-normalize one FLOAT32 RepVGG embedding."""
    raw = np.asarray(raw_output)

    if not np.issubdtype(
        raw.dtype,
        np.floating,
    ):
        raise ValueError(
            "RepVGG host output must be floating point; "
            "configure HailoRT output VStreams as FLOAT32"
        )

    if raw.ndim == 2 and raw.shape[0] == 1:
        raw = raw[0]

    if raw.ndim != 1:
        raise ValueError(
            "RepVGG output must be a vector or one-row batch"
        )

    if raw.size != REPVGG_EMBEDDING_DIMENSION:
        raise ValueError(
            "RepVGG output dimension is "
            f"{raw.size}; expected "
            f"{REPVGG_EMBEDDING_DIMENSION}"
        )

    embedding = np.asarray(
        raw,
        dtype=np.float32,
    )

    if not np.all(np.isfinite(embedding)):
        raise ValueError(
            "RepVGG output contains non-finite values"
        )

    norm = float(np.linalg.norm(embedding))

    if not np.isfinite(norm) or norm <= 1e-12:
        raise ValueError(
            "RepVGG output has zero or invalid norm"
        )

    normalized = np.ascontiguousarray(
        embedding / norm,
        dtype=np.float32,
    )
    normalized.setflags(write=False)

    return normalized


__all__ = [
    "REPVGG_BACKEND_DESCRIPTOR",
    "REPVGG_EMBEDDING_DIMENSION",
    "REPVGG_EMBEDDING_SPACE",
    "REPVGG_HEF_SHA256",
    "REPVGG_INPUT_CHANNELS",
    "REPVGG_INPUT_HEIGHT",
    "REPVGG_INPUT_NAME",
    "REPVGG_INPUT_WIDTH",
    "REPVGG_OUTPUT_NAME",
    "RepVggPreparedCrop",
    "postprocess_repvgg_embedding",
    "prepare_repvgg_crop",
    "repvgg_batch_tensor",
]
