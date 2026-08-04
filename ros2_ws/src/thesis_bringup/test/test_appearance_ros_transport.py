"""Tests for the causal appearance ROS message boundary."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from thesis_bringup.tim_mars.appearance_async import (
    AppearanceBackendDescriptor,
    AppearanceEmbeddingRequest,
    AppearanceEmbeddingResult,
    CausalAppearanceRequestQueue,
)
from thesis_bringup.tim_mars.appearance_ros_transport import (
    request_from_ros_message,
    request_to_ros_message,
    result_from_ros_message,
    result_to_ros_message,
)
from thesis_bringup.tim_mars.appearance_worker import (
    DeterministicAppearanceWorker,
)


def descriptor() -> AppearanceBackendDescriptor:
    return AppearanceBackendDescriptor(
        name="test-reid",
        embedding_space="test-space:sha256",
        dimension=4,
        input_height=8,
        input_width=4,
        input_channels=3,
        input_layout="NHWC",
        input_dtype="uint8",
        raw_output_dtype="float32",
        embedding_dtype="float32",
        l2_normalized=True,
    )


def crop_bgr() -> np.ndarray:
    crop = np.arange(
        6 * 5 * 3,
        dtype=np.uint8,
    ).reshape(6, 5, 3)

    return crop


def request() -> AppearanceEmbeddingRequest:
    return AppearanceEmbeddingRequest(
        request_id=7,
        backend=descriptor(),
        submitted_ns=1_000,
        deadline_ns=5_000,
        source_frame_id=42,
        track_timestamp_ns=900,
        source_image_timestamp_ns=850,
        source_image_seq=3,
        frame_generation=4,
        candidate_index=2,
        track_id=11,
        track_generation=6,
        source_bbox=(10.5, 20.25, 50.75, 90.5),
        crop_bgr=crop_bgr(),
    )


def normalized_embedding() -> np.ndarray:
    value = np.ones(
        4,
        dtype=np.float32,
    )
    value /= np.linalg.norm(value)

    return value


def test_request_round_trip_preserves_complete_contract():
    original = request()
    source_crop = original.crop_bgr.copy()

    message = request_to_ros_message(original)
    restored = request_from_ros_message(message)

    assert restored.request_id == original.request_id
    assert restored.backend == original.backend
    assert restored.submitted_ns == original.submitted_ns
    assert restored.deadline_ns == original.deadline_ns
    assert restored.source_frame_id == original.source_frame_id
    assert restored.track_timestamp_ns == (
        original.track_timestamp_ns
    )
    assert restored.source_image_timestamp_ns == (
        original.source_image_timestamp_ns
    )
    assert restored.source_image_seq == original.source_image_seq
    assert restored.frame_generation == original.frame_generation
    assert restored.candidate_index == original.candidate_index
    assert restored.track_id == original.track_id
    assert restored.track_generation == original.track_generation
    assert restored.source_bbox == pytest.approx(
        original.source_bbox
    )
    assert np.array_equal(
        restored.crop_bgr,
        source_crop,
    )
    assert not restored.crop_bgr.flags.writeable

    assert message.crop_encoding == "bgr8"
    assert message.crop_height == 6
    assert message.crop_width == 5
    assert message.crop_step == 15
    assert len(message.crop_data) == 90

    assert np.array_equal(
        original.crop_bgr,
        source_crop,
    )


def test_request_serialization_copies_non_contiguous_crop():
    original = request()
    non_contiguous = original.crop_bgr[:, ::-1, :]

    assert not non_contiguous.flags.c_contiguous

    changed = replace(
        original,
        crop_bgr=non_contiguous,
    )

    restored = request_from_ros_message(
        request_to_ros_message(changed)
    )

    assert restored.crop_bgr.flags.c_contiguous
    assert np.array_equal(
        restored.crop_bgr,
        non_contiguous,
    )


def test_request_rejects_non_uint8_crop():
    changed = replace(
        request(),
        crop_bgr=crop_bgr().astype(np.float32),
    )

    with pytest.raises(
        ValueError,
        match="dtype uint8",
    ):
        request_to_ros_message(changed)


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        (
            "crop_encoding",
            "rgb8",
            "unsupported crop encoding",
        ),
        (
            "crop_step",
            999,
            "crop step mismatch",
        ),
    ],
)
def test_request_rejects_invalid_wire_crop_metadata(
    field,
    value,
    error,
):
    message = request_to_ros_message(
        request()
    )
    setattr(message, field, value)

    with pytest.raises(
        ValueError,
        match=error,
    ):
        request_from_ros_message(message)


def test_request_rejects_invalid_wire_crop_length():
    message = request_to_ros_message(
        request()
    )
    message.crop_data = message.crop_data[:-1]

    with pytest.raises(
        ValueError,
        match="crop byte length mismatch",
    ):
        request_from_ros_message(message)


def test_success_result_round_trip_is_immutable():
    original = AppearanceEmbeddingResult(
        request_id=7,
        backend_name="test-reid",
        embedding_space="test-space:sha256",
        dimension=4,
        started_ns=1_100,
        completed_ns=1_200,
        embedding=normalized_embedding(),
        error=None,
    )

    message = result_to_ros_message(original)
    restored = result_from_ros_message(message)

    assert message.succeeded
    assert message.error == ""
    assert len(message.embedding) == 4

    assert restored.request_id == original.request_id
    assert restored.backend_name == original.backend_name
    assert restored.embedding_space == original.embedding_space
    assert restored.dimension == original.dimension
    assert restored.started_ns == original.started_ns
    assert restored.completed_ns == original.completed_ns
    assert restored.error is None
    assert np.array_equal(
        restored.embedding,
        original.embedding,
    )
    assert not restored.embedding.flags.writeable


def test_failure_result_round_trip_is_explicit():
    original = AppearanceEmbeddingResult(
        request_id=7,
        backend_name="test-reid",
        embedding_space="test-space:sha256",
        dimension=4,
        started_ns=1_100,
        completed_ns=1_200,
        embedding=None,
        error="RuntimeError: synthetic failure",
    )

    message = result_to_ros_message(original)
    restored = result_from_ros_message(message)

    assert not message.succeeded
    assert len(message.embedding) == 0
    assert message.error == "RuntimeError: synthetic failure"

    assert restored.embedding is None
    assert restored.error == "RuntimeError: synthetic failure"


def test_success_result_rejects_error_text():
    message = result_to_ros_message(
        AppearanceEmbeddingResult(
            request_id=7,
            backend_name="test-reid",
            embedding_space="test-space:sha256",
            dimension=4,
            started_ns=1_100,
            completed_ns=1_200,
            embedding=normalized_embedding(),
            error=None,
        )
    )
    message.error = "contradiction"

    with pytest.raises(
        ValueError,
        match="contains an error",
    ):
        result_from_ros_message(message)


def test_failure_result_rejects_embedding_values():
    message = result_to_ros_message(
        AppearanceEmbeddingResult(
            request_id=7,
            backend_name="test-reid",
            embedding_space="test-space:sha256",
            dimension=4,
            started_ns=1_100,
            completed_ns=1_200,
            embedding=None,
            error="failure",
        )
    )
    message.embedding = [0.0]

    with pytest.raises(
        ValueError,
        match="contains embedding values",
    ):
        result_from_ros_message(message)


def test_result_rejects_wrong_dimension():
    result = AppearanceEmbeddingResult(
        request_id=7,
        backend_name="test-reid",
        embedding_space="test-space:sha256",
        dimension=5,
        started_ns=1_100,
        completed_ns=1_200,
        embedding=normalized_embedding(),
        error=None,
    )

    with pytest.raises(
        ValueError,
        match="dimension mismatch",
    ):
        result_to_ros_message(result)


def test_request_worker_result_round_trip_passes_causal_gate():
    original = request()
    queue = CausalAppearanceRequestQueue(
        capacity=2
    )

    submit = queue.submit(original)

    assert submit.accepted

    batch = queue.dequeue(
        max_items=1,
        now_ns=1_050,
    )

    assert batch.requests == (original,)

    transported_request = request_from_ros_message(
        request_to_ros_message(
            batch.requests[0]
        )
    )

    clock_values = iter(
        (1_100, 1_200)
    )

    worker = DeterministicAppearanceWorker(
        descriptor=descriptor(),
        prepare=lambda crop: crop,
        make_batch=lambda crop: crop,
        infer=lambda _batch: normalized_embedding(),
        postprocess=lambda value: value,
        clock_ns=lambda: next(clock_values),
    )

    worker_result = worker.run(
        transported_request
    )

    transported_result = result_from_ros_message(
        result_to_ros_message(worker_result)
    )

    decision = queue.complete(
        transported_result,
        now_ns=1_300,
        current_frame_generation=4,
        current_track_generations={
            11: 6,
        },
    )

    assert decision.accepted
    assert decision.reason == "accepted"
    assert decision.request_id == 7
    assert decision.track_id == 11
    assert np.array_equal(
        decision.embedding,
        normalized_embedding(),
    )
    assert not decision.embedding.flags.writeable
