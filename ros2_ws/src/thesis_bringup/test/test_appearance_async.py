"""Tests for the hardware-independent asynchronous ReID contract."""

from __future__ import annotations

import numpy as np
import pytest

from thesis_bringup.tim_mars.appearance_async import (
    AppearanceBackendDescriptor,
    AppearanceEmbeddingRequest,
    AppearanceEmbeddingResult,
    CausalAppearanceRequestQueue,
    resolve_appearance_backend,
)


def descriptor(
    *,
    name="repvgg-hailo",
    space="repvgg-a0-person-reid-512-v1",
    dimension=512,
):
    return AppearanceBackendDescriptor(
        name=name,
        embedding_space=space,
        dimension=dimension,
        input_height=256,
        input_width=128,
        input_channels=3,
        input_layout="NHWC",
        input_dtype="uint8",
        raw_output_dtype="uint8",
        embedding_dtype="float32",
        l2_normalized=True,
    )


def request(
    request_id,
    *,
    track_id=7,
    track_generation=3,
    frame_generation=2,
    image_timestamp_ns=900,
    image_seq=4,
    submitted_ns=1_000,
    deadline_ns=2_000,
    backend=None,
):
    return AppearanceEmbeddingRequest(
        request_id=request_id,
        backend=backend or descriptor(),
        submitted_ns=submitted_ns,
        deadline_ns=deadline_ns,
        source_frame_id=20,
        track_timestamp_ns=950,
        source_image_timestamp_ns=image_timestamp_ns,
        source_image_seq=image_seq,
        frame_generation=frame_generation,
        candidate_index=0,
        track_id=track_id,
        track_generation=track_generation,
        source_bbox=(10.0, 20.0, 50.0, 120.0),
        crop_bgr=np.zeros((100, 40, 3), dtype=np.uint8),
    )


def unit_embedding(dimension=512):
    value = np.ones(dimension, dtype=np.float32)
    return value / np.linalg.norm(value)


def result(
    request_id,
    *,
    backend=None,
    started_ns=1_200,
    completed_ns=1_500,
    embedding=None,
    error=None,
):
    backend = backend or descriptor()

    return AppearanceEmbeddingResult(
        request_id=request_id,
        backend_name=backend.name,
        embedding_space=backend.embedding_space,
        dimension=backend.dimension,
        started_ns=started_ns,
        completed_ns=completed_ns,
        embedding=(
            unit_embedding(backend.dimension)
            if embedding is None and error is None
            else embedding
        ),
        error=error,
    )


def dequeue_one(queue, *, now_ns=1_100):
    batch = queue.dequeue(
        max_items=1,
        now_ns=now_ns,
    )
    assert len(batch.requests) == 1
    return batch.requests[0]


def complete(
    queue,
    completed_result,
    *,
    now_ns=1_600,
    frame_generation=2,
    track_generations=None,
):
    return queue.complete(
        completed_result,
        now_ns=now_ns,
        current_frame_generation=frame_generation,
        current_track_generations=(
            {7: 3}
            if track_generations is None
            else track_generations
        ),
    )


def test_backend_resolution_uses_available_primary():
    primary = descriptor()
    fallback = descriptor(name="repvgg-cpu")

    resolved = resolve_appearance_backend(
        primary=primary,
        primary_available=True,
        fallback=fallback,
    )

    assert resolved.backend is primary
    assert resolved.mode == "primary"
    assert resolved.reason == "primary_available"


def test_backend_resolution_accepts_only_compatible_fallback():
    primary = descriptor()
    fallback = descriptor(name="repvgg-cpu")

    resolved = resolve_appearance_backend(
        primary=primary,
        primary_available=False,
        fallback=fallback,
    )

    assert resolved.backend is fallback
    assert resolved.mode == "fallback"
    assert resolved.reason == "compatible_fallback"


def test_backend_resolution_rejects_mars_as_repvgg_fallback():
    primary = descriptor()
    mars = AppearanceBackendDescriptor(
        name="cpu-mars-small128",
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

    resolved = resolve_appearance_backend(
        primary=primary,
        primary_available=False,
        fallback=mars,
    )

    assert resolved.backend is None
    assert resolved.mode == "fail_closed"
    assert (
        resolved.reason
        == "incompatible_fallback_embedding_space"
    )


def test_request_rejects_noncausal_future_image():
    with pytest.raises(
        ValueError,
        match="must not be newer",
    ):
        AppearanceEmbeddingRequest(
            request_id=1,
            backend=descriptor(),
            submitted_ns=1_000,
            deadline_ns=2_000,
            source_frame_id=20,
            track_timestamp_ns=900,
            source_image_timestamp_ns=901,
            source_image_seq=4,
            frame_generation=2,
            candidate_index=0,
            track_id=7,
            track_generation=3,
            source_bbox=(10.0, 20.0, 50.0, 120.0),
            crop_bgr=np.zeros(
                (100, 40, 3),
                dtype=np.uint8,
            ),
        )


def test_queue_dequeues_requests_fifo():
    queue = CausalAppearanceRequestQueue(capacity=3)

    assert queue.submit(
        request(1, track_id=7)
    ).accepted
    assert queue.submit(
        request(2, track_id=8)
    ).accepted

    batch = queue.dequeue(
        max_items=2,
        now_ns=1_100,
    )

    assert [
        item.request_id
        for item in batch.requests
    ] == [1, 2]
    assert batch.depth == 0
    assert batch.in_flight == 2


def test_newer_same_track_request_supersedes_queued_crop():
    queue = CausalAppearanceRequestQueue(capacity=3)

    queue.submit(
        request(
            1,
            image_timestamp_ns=800,
            image_seq=3,
        )
    )
    decision = queue.submit(
        request(
            2,
            image_timestamp_ns=900,
            image_seq=4,
        )
    )

    assert decision.accepted
    assert decision.reason == "accepted_with_drop"
    assert decision.dropped_request_ids == (1,)

    batch = queue.dequeue(
        max_items=1,
        now_ns=1_100,
    )

    assert batch.requests[0].request_id == 2
    assert (
        queue.diagnostics()
        .drop_reasons["superseded_same_track"]
        == 1
    )


def test_older_same_track_request_is_rejected():
    queue = CausalAppearanceRequestQueue(capacity=3)

    queue.submit(
        request(
            2,
            image_timestamp_ns=900,
            image_seq=4,
        )
    )
    decision = queue.submit(
        request(
            1,
            image_timestamp_ns=800,
            image_seq=3,
        )
    )

    assert not decision.accepted
    assert (
        decision.reason
        == "not_newer_than_queued_same_track"
    )


def test_queue_overflow_drops_oldest_queued_request():
    queue = CausalAppearanceRequestQueue(capacity=2)

    queue.submit(request(1, track_id=7))
    queue.submit(request(2, track_id=8))
    decision = queue.submit(request(3, track_id=9))

    assert decision.accepted
    assert decision.dropped_request_ids == (1,)

    batch = queue.dequeue(
        max_items=2,
        now_ns=1_100,
    )

    assert [
        item.request_id
        for item in batch.requests
    ] == [2, 3]
    assert (
        queue.diagnostics()
        .drop_reasons["overflow_drop_oldest"]
        == 1
    )


def test_expired_request_never_becomes_in_flight():
    queue = CausalAppearanceRequestQueue(capacity=2)
    queue.submit(request(1, deadline_ns=1_050))

    batch = queue.dequeue(
        max_items=1,
        now_ns=1_100,
    )

    assert batch.requests == ()
    assert batch.expired_request_ids == (1,)
    assert batch.in_flight == 0


def test_matching_result_is_accepted():
    queue = CausalAppearanceRequestQueue(capacity=2)
    queue.submit(request(1))
    dequeue_one(queue)

    decision = complete(queue, result(1))

    assert decision.accepted
    assert decision.reason == "accepted"
    assert decision.track_id == 7
    assert decision.embedding is not None
    assert decision.embedding.shape == (512,)
    assert not decision.embedding.flags.writeable


def test_result_after_deadline_is_rejected():
    queue = CausalAppearanceRequestQueue(capacity=2)
    queue.submit(request(1, deadline_ns=1_400))
    dequeue_one(queue)

    decision = complete(
        queue,
        result(
            1,
            started_ns=1_200,
            completed_ns=1_500,
        ),
        now_ns=1_600,
    )

    assert not decision.accepted
    assert (
        decision.reason
        == "deadline_expired_before_apply"
    )


def test_result_from_old_frame_generation_is_rejected():
    queue = CausalAppearanceRequestQueue(capacity=2)
    queue.submit(request(1))
    dequeue_one(queue)

    decision = complete(
        queue,
        result(1),
        frame_generation=3,
    )

    assert not decision.accepted
    assert decision.reason == "frame_generation_mismatch"


def test_result_from_reused_tracker_id_is_rejected():
    queue = CausalAppearanceRequestQueue(capacity=2)
    queue.submit(request(1))
    dequeue_one(queue)

    decision = complete(
        queue,
        result(1),
        track_generations={7: 4},
    )

    assert not decision.accepted
    assert decision.reason == "track_generation_mismatch"


def test_older_result_is_rejected_after_newer_result_applied():
    queue = CausalAppearanceRequestQueue(capacity=2)

    queue.submit(
        request(
            1,
            image_timestamp_ns=800,
            image_seq=3,
        )
    )
    dequeue_one(queue)

    queue.submit(
        request(
            2,
            image_timestamp_ns=900,
            image_seq=4,
        )
    )
    dequeue_one(queue)

    newer = complete(
        queue,
        result(
            2,
            started_ns=1_250,
            completed_ns=1_400,
        ),
        now_ns=1_450,
    )
    older = complete(
        queue,
        result(
            1,
            started_ns=1_200,
            completed_ns=1_500,
        ),
        now_ns=1_600,
    )

    assert newer.accepted
    assert not older.accepted
    assert older.reason == "superseded_result"


def test_embedding_dimension_mismatch_is_rejected():
    queue = CausalAppearanceRequestQueue(capacity=2)
    queue.submit(request(1))
    dequeue_one(queue)

    decision = complete(
        queue,
        result(
            1,
            embedding=unit_embedding(128),
        ),
    )

    assert not decision.accepted
    assert decision.reason == "embedding_dimension_mismatch"


def test_unnormalized_embedding_is_rejected():
    queue = CausalAppearanceRequestQueue(capacity=2)
    queue.submit(request(1))
    dequeue_one(queue)

    decision = complete(
        queue,
        result(
            1,
            embedding=np.ones(
                512,
                dtype=np.float32,
            ),
        ),
    )

    assert not decision.accepted
    assert decision.reason == "embedding_not_l2_normalized"


def test_backend_failure_is_explicitly_rejected():
    queue = CausalAppearanceRequestQueue(capacity=2)
    queue.submit(request(1))
    dequeue_one(queue)

    decision = complete(
        queue,
        result(
            1,
            embedding=None,
            error="hailo unavailable",
        ),
    )

    assert not decision.accepted
    assert decision.reason == "backend_failure"


def test_cancel_all_removes_queued_and_in_flight_work():
    queue = CausalAppearanceRequestQueue(capacity=3)

    queue.submit(request(1, track_id=7))
    queue.submit(request(2, track_id=8))
    queue.dequeue(max_items=1, now_ns=1_100)

    cancelled = queue.cancel_all(
        reason="target_clear"
    )

    assert set(cancelled) == {1, 2}

    diagnostics = queue.diagnostics()

    assert diagnostics.queued == 0
    assert diagnostics.in_flight == 0
    assert (
        diagnostics.drop_reasons[
            "cancelled:target_clear"
        ]
        == 2
    )
