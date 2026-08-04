"""Strict ROS conversion for causal asynchronous appearance messages."""

from __future__ import annotations

from array import array
from typing import Any

import numpy as np

from thesis_bringup.tim_mars.appearance_async import (
    AppearanceBackendDescriptor,
    AppearanceEmbeddingRequest,
    AppearanceEmbeddingResult,
)
from thesis_msgs.msg import (
    AppearanceEmbeddingRequest as AppearanceEmbeddingRequestMsg,
    AppearanceEmbeddingResult as AppearanceEmbeddingResultMsg,
)


_UINT32_MAX = (1 << 32) - 1
_UINT64_MAX = (1 << 64) - 1
_INT64_MIN = -(1 << 63)
_INT64_MAX = (1 << 63) - 1
_CROP_ENCODING = "bgr8"
_CROP_CHANNELS = 3


def _require_integer_range(
    value: Any,
    *,
    name: str,
    minimum: int,
    maximum: int,
) -> int:
    result = int(value)

    if result < int(minimum) or result > int(maximum):
        raise ValueError(
            f"{name}={result} is outside "
            f"[{int(minimum)}, {int(maximum)}]"
        )

    return result


def _require_uint32(
    value: Any,
    *,
    name: str,
) -> int:
    return _require_integer_range(
        value,
        name=name,
        minimum=0,
        maximum=_UINT32_MAX,
    )


def _require_uint64(
    value: Any,
    *,
    name: str,
) -> int:
    return _require_integer_range(
        value,
        name=name,
        minimum=0,
        maximum=_UINT64_MAX,
    )


def _require_int64(
    value: Any,
    *,
    name: str,
) -> int:
    return _require_integer_range(
        value,
        name=name,
        minimum=_INT64_MIN,
        maximum=_INT64_MAX,
    )


def _require_non_empty_text(
    value: Any,
    *,
    name: str,
) -> str:
    result = str(value)

    if not result.strip():
        raise ValueError(f"{name} must be non-empty")

    return result


def _request_crop_to_wire(
    crop_bgr: Any,
) -> tuple[np.ndarray, int, int, int]:
    crop = np.asarray(crop_bgr)

    if crop.dtype != np.uint8:
        raise ValueError(
            "appearance request crop must have dtype uint8"
        )

    if crop.ndim != 3:
        raise ValueError(
            "appearance request crop must be HWC"
        )

    if int(crop.shape[2]) != _CROP_CHANNELS:
        raise ValueError(
            "appearance request crop must contain three BGR channels"
        )

    height = int(crop.shape[0])
    width = int(crop.shape[1])

    if height <= 0 or width <= 0:
        raise ValueError(
            "appearance request crop must be non-empty"
        )

    contiguous = np.ascontiguousarray(
        crop,
        dtype=np.uint8,
    )
    step = width * _CROP_CHANNELS

    return contiguous, height, width, step


def _descriptor_to_request_message(
    descriptor: AppearanceBackendDescriptor,
    message: AppearanceEmbeddingRequestMsg,
) -> None:
    message.backend_name = _require_non_empty_text(
        descriptor.name,
        name="backend.name",
    )
    message.embedding_space = _require_non_empty_text(
        descriptor.embedding_space,
        name="backend.embedding_space",
    )
    message.backend_dimension = _require_uint32(
        descriptor.dimension,
        name="backend.dimension",
    )
    message.backend_input_height = _require_uint32(
        descriptor.input_height,
        name="backend.input_height",
    )
    message.backend_input_width = _require_uint32(
        descriptor.input_width,
        name="backend.input_width",
    )
    message.backend_input_channels = _require_uint32(
        descriptor.input_channels,
        name="backend.input_channels",
    )
    message.backend_input_layout = _require_non_empty_text(
        descriptor.input_layout,
        name="backend.input_layout",
    )
    message.backend_input_dtype = _require_non_empty_text(
        descriptor.input_dtype,
        name="backend.input_dtype",
    )
    message.backend_raw_output_dtype = _require_non_empty_text(
        descriptor.raw_output_dtype,
        name="backend.raw_output_dtype",
    )
    message.backend_embedding_dtype = _require_non_empty_text(
        descriptor.embedding_dtype,
        name="backend.embedding_dtype",
    )
    message.backend_l2_normalized = bool(
        descriptor.l2_normalized
    )


def _descriptor_from_request_message(
    message: AppearanceEmbeddingRequestMsg,
) -> AppearanceBackendDescriptor:
    return AppearanceBackendDescriptor(
        name=_require_non_empty_text(
            message.backend_name,
            name="backend_name",
        ),
        embedding_space=_require_non_empty_text(
            message.embedding_space,
            name="embedding_space",
        ),
        dimension=_require_uint32(
            message.backend_dimension,
            name="backend_dimension",
        ),
        input_height=_require_uint32(
            message.backend_input_height,
            name="backend_input_height",
        ),
        input_width=_require_uint32(
            message.backend_input_width,
            name="backend_input_width",
        ),
        input_channels=_require_uint32(
            message.backend_input_channels,
            name="backend_input_channels",
        ),
        input_layout=_require_non_empty_text(
            message.backend_input_layout,
            name="backend_input_layout",
        ),
        input_dtype=_require_non_empty_text(
            message.backend_input_dtype,
            name="backend_input_dtype",
        ),
        raw_output_dtype=_require_non_empty_text(
            message.backend_raw_output_dtype,
            name="backend_raw_output_dtype",
        ),
        embedding_dtype=_require_non_empty_text(
            message.backend_embedding_dtype,
            name="backend_embedding_dtype",
        ),
        l2_normalized=bool(
            message.backend_l2_normalized
        ),
    )


def request_to_ros_message(
    request: AppearanceEmbeddingRequest,
) -> AppearanceEmbeddingRequestMsg:
    """Serialize one validated causal request into its ROS message."""
    message = AppearanceEmbeddingRequestMsg()

    message.request_id = _require_uint64(
        request.request_id,
        name="request_id",
    )
    _descriptor_to_request_message(
        request.backend,
        message,
    )

    message.submitted_ns = _require_int64(
        request.submitted_ns,
        name="submitted_ns",
    )
    message.deadline_ns = _require_int64(
        request.deadline_ns,
        name="deadline_ns",
    )

    message.source_frame_id = _require_uint64(
        request.source_frame_id,
        name="source_frame_id",
    )
    message.track_timestamp_ns = _require_int64(
        request.track_timestamp_ns,
        name="track_timestamp_ns",
    )
    message.source_image_timestamp_ns = _require_int64(
        request.source_image_timestamp_ns,
        name="source_image_timestamp_ns",
    )
    message.source_image_seq = _require_uint64(
        request.source_image_seq,
        name="source_image_seq",
    )

    message.frame_generation = _require_uint64(
        request.frame_generation,
        name="frame_generation",
    )
    message.candidate_index = _require_uint64(
        request.candidate_index,
        name="candidate_index",
    )
    message.track_id = _require_uint64(
        request.track_id,
        name="track_id",
    )
    message.track_generation = _require_uint64(
        request.track_generation,
        name="track_generation",
    )

    bbox = tuple(
        float(value)
        for value in request.source_bbox
    )

    if len(bbox) != 4:
        raise ValueError(
            "source_bbox must contain four values"
        )

    if not all(
        np.isfinite(value)
        for value in bbox
    ):
        raise ValueError(
            "source_bbox must contain finite values"
        )

    message.source_bbox_xyxy = list(bbox)

    crop, height, width, step = _request_crop_to_wire(
        request.crop_bgr
    )

    message.crop_height = _require_uint32(
        height,
        name="crop_height",
    )
    message.crop_width = _require_uint32(
        width,
        name="crop_width",
    )
    message.crop_step = _require_uint32(
        step,
        name="crop_step",
    )
    message.crop_encoding = _CROP_ENCODING
    message.crop_data = array(
        "B",
        crop.tobytes(order="C"),
    )

    return message


def request_from_ros_message(
    message: AppearanceEmbeddingRequestMsg,
) -> AppearanceEmbeddingRequest:
    """Deserialize and validate one ROS causal request."""
    descriptor = _descriptor_from_request_message(
        message
    )

    height = _require_uint32(
        message.crop_height,
        name="crop_height",
    )
    width = _require_uint32(
        message.crop_width,
        name="crop_width",
    )
    step = _require_uint32(
        message.crop_step,
        name="crop_step",
    )

    if height <= 0 or width <= 0:
        raise ValueError(
            "crop dimensions must be positive"
        )

    encoding = str(message.crop_encoding)

    if encoding != _CROP_ENCODING:
        raise ValueError(
            "unsupported crop encoding "
            f"{encoding!r}; expected {_CROP_ENCODING!r}"
        )

    expected_step = width * _CROP_CHANNELS

    if step != expected_step:
        raise ValueError(
            "crop step mismatch "
            f"(got={step}, expected={expected_step})"
        )

    raw = bytes(message.crop_data)
    expected_size = height * step

    if len(raw) != expected_size:
        raise ValueError(
            "crop byte length mismatch "
            f"(got={len(raw)}, expected={expected_size})"
        )

    crop = np.frombuffer(
        raw,
        dtype=np.uint8,
    ).reshape(
        height,
        width,
        _CROP_CHANNELS,
    ).copy()
    crop.setflags(write=False)

    bbox = tuple(
        float(value)
        for value in message.source_bbox_xyxy
    )

    return AppearanceEmbeddingRequest(
        request_id=_require_uint64(
            message.request_id,
            name="request_id",
        ),
        backend=descriptor,
        submitted_ns=_require_int64(
            message.submitted_ns,
            name="submitted_ns",
        ),
        deadline_ns=_require_int64(
            message.deadline_ns,
            name="deadline_ns",
        ),
        source_frame_id=_require_uint64(
            message.source_frame_id,
            name="source_frame_id",
        ),
        track_timestamp_ns=_require_int64(
            message.track_timestamp_ns,
            name="track_timestamp_ns",
        ),
        source_image_timestamp_ns=_require_int64(
            message.source_image_timestamp_ns,
            name="source_image_timestamp_ns",
        ),
        source_image_seq=_require_uint64(
            message.source_image_seq,
            name="source_image_seq",
        ),
        frame_generation=_require_uint64(
            message.frame_generation,
            name="frame_generation",
        ),
        candidate_index=_require_uint64(
            message.candidate_index,
            name="candidate_index",
        ),
        track_id=_require_uint64(
            message.track_id,
            name="track_id",
        ),
        track_generation=_require_uint64(
            message.track_generation,
            name="track_generation",
        ),
        source_bbox=bbox,
        crop_bgr=crop,
    )


def _validated_success_embedding(
    embedding: Any,
    *,
    dimension: int,
) -> np.ndarray:
    value = np.asarray(embedding)

    if value.dtype != np.float32:
        raise ValueError(
            "successful embedding must have dtype float32"
        )

    if value.ndim != 1:
        raise ValueError(
            "successful embedding must be a vector"
        )

    if int(value.size) != int(dimension):
        raise ValueError(
            "successful embedding dimension mismatch "
            f"(got={value.size}, expected={dimension})"
        )

    if not np.all(np.isfinite(value)):
        raise ValueError(
            "successful embedding must be finite"
        )

    return np.ascontiguousarray(
        value,
        dtype=np.float32,
    )


def result_to_ros_message(
    result: AppearanceEmbeddingResult,
) -> AppearanceEmbeddingResultMsg:
    """Serialize one explicit worker result into its ROS message."""
    message = AppearanceEmbeddingResultMsg()

    message.request_id = _require_uint64(
        result.request_id,
        name="request_id",
    )
    message.backend_name = _require_non_empty_text(
        result.backend_name,
        name="backend_name",
    )
    message.embedding_space = _require_non_empty_text(
        result.embedding_space,
        name="embedding_space",
    )
    message.dimension = _require_uint32(
        result.dimension,
        name="dimension",
    )
    message.started_ns = _require_int64(
        result.started_ns,
        name="started_ns",
    )
    message.completed_ns = _require_int64(
        result.completed_ns,
        name="completed_ns",
    )

    if int(message.started_ns) <= 0:
        raise ValueError(
            "started_ns must be positive"
        )

    if int(message.completed_ns) < int(message.started_ns):
        raise ValueError(
            "completed_ns precedes started_ns"
        )

    if result.error is None:
        if result.embedding is None:
            raise ValueError(
                "successful result has no embedding"
            )

        embedding = _validated_success_embedding(
            result.embedding,
            dimension=int(message.dimension),
        )

        message.succeeded = True
        message.embedding = array(
            "f",
            embedding.tolist(),
        )
        message.error = ""
        return message

    error = _require_non_empty_text(
        result.error,
        name="error",
    )

    if result.embedding is not None:
        raise ValueError(
            "failed result must not contain an embedding"
        )

    message.succeeded = False
    message.embedding = array("f")
    message.error = error

    return message


def result_from_ros_message(
    message: AppearanceEmbeddingResultMsg,
) -> AppearanceEmbeddingResult:
    """Deserialize and validate one explicit ROS worker result."""
    request_id = _require_uint64(
        message.request_id,
        name="request_id",
    )
    backend_name = _require_non_empty_text(
        message.backend_name,
        name="backend_name",
    )
    embedding_space = _require_non_empty_text(
        message.embedding_space,
        name="embedding_space",
    )
    dimension = _require_uint32(
        message.dimension,
        name="dimension",
    )
    started_ns = _require_int64(
        message.started_ns,
        name="started_ns",
    )
    completed_ns = _require_int64(
        message.completed_ns,
        name="completed_ns",
    )

    if started_ns <= 0:
        raise ValueError(
            "started_ns must be positive"
        )

    if completed_ns < started_ns:
        raise ValueError(
            "completed_ns precedes started_ns"
        )

    if bool(message.succeeded):
        if str(message.error):
            raise ValueError(
                "successful result contains an error"
            )

        embedding = np.asarray(
            message.embedding,
            dtype=np.float32,
        ).copy()

        embedding = _validated_success_embedding(
            embedding,
            dimension=dimension,
        )
        embedding.setflags(write=False)

        error = None
    else:
        error = _require_non_empty_text(
            message.error,
            name="error",
        )

        if len(message.embedding) != 0:
            raise ValueError(
                "failed result contains embedding values"
            )

        embedding = None

    return AppearanceEmbeddingResult(
        request_id=request_id,
        backend_name=backend_name,
        embedding_space=embedding_space,
        dimension=dimension,
        started_ns=started_ns,
        completed_ns=completed_ns,
        embedding=embedding,
        error=error,
    )


__all__ = [
    "request_from_ros_message",
    "request_to_ros_message",
    "result_from_ros_message",
    "result_to_ros_message",
]
