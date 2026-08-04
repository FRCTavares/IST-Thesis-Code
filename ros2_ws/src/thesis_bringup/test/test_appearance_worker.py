"""Tests for queue-to-worker-to-result causal integration."""

from __future__ import annotations

from collections import deque

import numpy as np

from thesis_bringup.tim_mars.appearance_async import (
    AppearanceBackendDescriptor,
    AppearanceEmbeddingRequest,
    CausalAppearanceRequestQueue,
)
from thesis_bringup.tim_mars.appearance_worker import (
    make_deterministic_repvgg_worker,
)
from thesis_bringup.tim_mars.repvgg_reid_adapter import (
    REPVGG_BACKEND_DESCRIPTOR,
    REPVGG_EMBEDDING_DIMENSION,
    REPVGG_INPUT_CHANNELS,
    REPVGG_INPUT_HEIGHT,
    REPVGG_INPUT_WIDTH,
)


class Clock:
    def __init__(self, *values):
        self.values = deque(int(value) for value in values)

    def __call__(self):
        return self.values.popleft()


def request(
    request_id=1,
    *,
    backend=REPVGG_BACKEND_DESCRIPTOR,
    frame_generation=2,
    track_id=7,
    track_generation=3,
):
    crop = np.empty(
        (40, 20, 3),
        dtype=np.uint8,
    )
    crop[...] = np.array(
        [10, 20, 30],
        dtype=np.uint8,
    )

    return AppearanceEmbeddingRequest(
        request_id=request_id,
        backend=backend,
        submitted_ns=2_000_000,
        deadline_ns=3_000_000,
        source_frame_id=20,
        track_timestamp_ns=1_000_000,
        source_image_timestamp_ns=900_000,
        source_image_seq=4,
        frame_generation=frame_generation,
        candidate_index=0,
        track_id=track_id,
        track_generation=track_generation,
        source_bbox=(10.0, 20.0, 30.0, 60.0),
        crop_bgr=crop,
    )


def deterministic_raw_output():
    return np.arange(
        1,
        REPVGG_EMBEDDING_DIMENSION + 1,
        dtype=np.float32,
    )[np.newaxis, :]


def test_worker_receives_uint8_rgb_batch():
    observed = {}

    def infer(batch):
        observed["shape"] = batch.shape
        observed["dtype"] = batch.dtype
        observed["pixel"] = batch[0, 0, 0].tolist()
        observed["contiguous"] = batch.flags.c_contiguous
        return deterministic_raw_output()

    worker = make_deterministic_repvgg_worker(
        infer=infer,
        clock_ns=Clock(
            2_100_000,
            2_200_000,
        ),
    )

    result = worker.run(request())

    assert result.error is None
    assert observed == {
        "shape": (
            1,
            REPVGG_INPUT_HEIGHT,
            REPVGG_INPUT_WIDTH,
            REPVGG_INPUT_CHANNELS,
        ),
        "dtype": np.dtype(np.uint8),
        "pixel": [30, 20, 10],
        "contiguous": True,
    }
    assert result.embedding is not None
    assert result.embedding.shape == (
        REPVGG_EMBEDDING_DIMENSION,
    )
    assert np.linalg.norm(
        result.embedding
    ) == np.float32(1.0)


def test_worker_failure_is_returned_in_result_envelope():
    def infer(_batch):
        raise RuntimeError("synthetic inference failure")

    worker = make_deterministic_repvgg_worker(
        infer=infer,
        clock_ns=Clock(
            2_100_000,
            2_200_000,
        ),
    )

    result = worker.run(request())

    assert result.embedding is None
    assert result.error == (
        "RuntimeError: synthetic inference failure"
    )
    assert result.started_ns == 2_100_000
    assert result.completed_ns == 2_200_000


def test_worker_rejects_incompatible_request_descriptor():
    incompatible = AppearanceBackendDescriptor(
        name="cpu-mars",
        embedding_space="mars-small128-v1",
        dimension=128,
        input_height=128,
        input_width=64,
        input_channels=3,
        input_layout="NHWC",
        input_dtype="uint8",
        raw_output_dtype="float32",
        embedding_dtype="float32",
        l2_normalized=True,
    )

    worker = make_deterministic_repvgg_worker(
        infer=lambda _batch: deterministic_raw_output(),
        clock_ns=Clock(
            2_100_000,
            2_200_000,
        ),
    )

    result = worker.run(
        request(backend=incompatible)
    )

    assert result.embedding is None
    assert result.error is not None
    assert "backend descriptor mismatch" in result.error


def test_raw_uint8_worker_output_is_explicit_failure():
    worker = make_deterministic_repvgg_worker(
        infer=lambda _batch: np.ones(
            (
                1,
                REPVGG_EMBEDDING_DIMENSION,
            ),
            dtype=np.uint8,
        ),
        clock_ns=Clock(
            2_100_000,
            2_200_000,
        ),
    )

    result = worker.run(request())

    assert result.embedding is None
    assert result.error is not None
    assert "FLOAT32" in result.error


def test_queue_worker_and_causal_result_gate_accept_matching_result():
    queue = CausalAppearanceRequestQueue(
        capacity=2
    )

    submitted = queue.submit(request())

    assert submitted.accepted

    batch = queue.dequeue(
        max_items=1,
        now_ns=2_050_000,
    )

    assert len(batch.requests) == 1

    worker = make_deterministic_repvgg_worker(
        infer=lambda _batch: deterministic_raw_output(),
        clock_ns=Clock(
            2_100_000,
            2_200_000,
        ),
    )

    worker_result = worker.run(
        batch.requests[0]
    )

    decision = queue.complete(
        worker_result,
        now_ns=2_300_000,
        current_frame_generation=2,
        current_track_generations={
            7: 3,
        },
    )

    assert decision.accepted
    assert decision.reason == "accepted"
    assert decision.track_id == 7
    assert decision.embedding is not None
    assert decision.embedding.shape == (
        REPVGG_EMBEDDING_DIMENSION,
    )


def test_queue_rejects_worker_result_after_frame_generation_changes():
    queue = CausalAppearanceRequestQueue(
        capacity=2
    )

    queue.submit(request())

    batch = queue.dequeue(
        max_items=1,
        now_ns=2_050_000,
    )

    worker = make_deterministic_repvgg_worker(
        infer=lambda _batch: deterministic_raw_output(),
        clock_ns=Clock(
            2_100_000,
            2_200_000,
        ),
    )

    worker_result = worker.run(
        batch.requests[0]
    )

    decision = queue.complete(
        worker_result,
        now_ns=2_300_000,
        current_frame_generation=3,
        current_track_generations={
            7: 3,
        },
    )

    assert not decision.accepted
    assert decision.reason == (
        "frame_generation_mismatch"
    )


def test_queue_rejects_explicit_worker_failure():
    queue = CausalAppearanceRequestQueue(
        capacity=2
    )

    queue.submit(request())

    batch = queue.dequeue(
        max_items=1,
        now_ns=2_050_000,
    )

    worker = make_deterministic_repvgg_worker(
        infer=lambda _batch: (
            _ for _ in ()
        ).throw(
            RuntimeError("device unavailable")
        ),
        clock_ns=Clock(
            2_100_000,
            2_200_000,
        ),
    )

    worker_result = worker.run(
        batch.requests[0]
    )

    decision = queue.complete(
        worker_result,
        now_ns=2_300_000,
        current_frame_generation=2,
        current_track_generations={
            7: 3,
        },
    )

    assert not decision.accepted
    assert decision.reason == "backend_failure"
