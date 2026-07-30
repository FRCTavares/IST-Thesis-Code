"""Tests for the TIM-owned causal RepVGG transport ledger."""

import numpy as np

from thesis_bringup.tim_mars.appearance_async import (
    AppearanceEmbeddingResult,
)
from thesis_bringup.tim_mars.appearance_request_producer import (
    AppearanceRequestCrop,
)
from thesis_bringup.tim_mars.appearance_request_transport import (
    TimAppearanceRequestTransport,
)
from thesis_bringup.tim_mars.repvgg_reid_adapter import (
    REPVGG_BACKEND_DESCRIPTOR,
)


def crop(
    *,
    track_id: int = 7,
    candidate_index: int = 0,
    source_frame_id: int = 42,
    source_image_seq: int = 900,
    frame_generation: int = 3,
    track_generation: int = 5,
) -> AppearanceRequestCrop:
    """Construct one deterministic immutable staged crop."""
    return AppearanceRequestCrop(
        source_frame_id=source_frame_id,
        track_timestamp_ns=1_000,
        source_image_timestamp_ns=900,
        source_image_seq=source_image_seq,
        frame_generation=frame_generation,
        candidate_index=candidate_index,
        track_id=track_id,
        track_generation=track_generation,
        source_bbox=(
            10.0,
            20.0,
            50.0,
            100.0,
        ),
        crop_bgr=np.zeros(
            (80, 40, 3),
            dtype=np.uint8,
        ),
    )


def embedding() -> np.ndarray:
    """Return one normalized 512D RepVGG embedding."""
    value = np.ones(
        REPVGG_BACKEND_DESCRIPTOR.dimension,
        dtype=np.float32,
    )
    value /= np.linalg.norm(value)
    return value


def success_result(
    request,
    *,
    started_ns: int = 1_100,
    completed_ns: int = 1_200,
) -> AppearanceEmbeddingResult:
    """Construct a successful result matching one request."""
    return AppearanceEmbeddingResult(
        request_id=int(request.request_id),
        backend_name=request.backend.name,
        embedding_space=(
            request.backend.embedding_space
        ),
        dimension=int(
            request.backend.dimension
        ),
        started_ns=started_ns,
        completed_ns=completed_ns,
        embedding=embedding(),
        error=None,
    )


def test_stage_constructs_complete_request_and_marks_in_flight():
    """Move an admitted request immediately into the causal ledger."""
    transport = TimAppearanceRequestTransport(
        capacity=4,
        deadline_ms=500.0,
    )

    batch = transport.stage(
        (crop(),),
        now_ns=1_000,
    )

    assert len(batch.requests) == 1
    assert batch.dropped_request_ids == ()
    assert batch.expired_request_ids == ()
    assert batch.rejected_submissions == 0

    request = batch.requests[0]

    assert request.request_id == 1
    assert request.backend == (
        REPVGG_BACKEND_DESCRIPTOR
    )
    assert request.submitted_ns == 1_000
    assert request.deadline_ns == 500_001_000
    assert request.source_frame_id == 42
    assert request.source_image_seq == 900
    assert request.frame_generation == 3
    assert request.candidate_index == 0
    assert request.track_id == 7
    assert request.track_generation == 5
    assert not request.crop_bgr.flags.writeable

    diagnostics = transport.diagnostics()

    assert diagnostics.constructed == 1
    assert diagnostics.published == 1
    assert diagnostics.queue.queued == 0
    assert diagnostics.queue.in_flight == 1


def test_stage_applies_bounded_latest_batch_policy():
    """Drop the oldest request before publishing an oversized batch."""
    transport = TimAppearanceRequestTransport(
        capacity=2,
        deadline_ms=500.0,
    )

    batch = transport.stage(
        (
            crop(
                track_id=1,
                candidate_index=0,
            ),
            crop(
                track_id=2,
                candidate_index=1,
            ),
            crop(
                track_id=3,
                candidate_index=2,
            ),
        ),
        now_ns=1_000,
    )

    assert tuple(
        request.request_id
        for request in batch.requests
    ) == (2, 3)
    assert batch.dropped_request_ids == (1,)
    assert (
        transport.diagnostics()
        .queue.drop_reasons[
            "overflow_drop_oldest"
        ]
        == 1
    )


def test_successful_result_is_validated_and_isolated():
    """Retain an immutable observation without touching CPU memory."""
    transport = TimAppearanceRequestTransport(
        capacity=4,
        deadline_ms=500.0,
    )

    request = transport.stage(
        (crop(),),
        now_ns=1_000,
    ).requests[0]

    decision = transport.complete(
        success_result(request),
        now_ns=1_300,
        current_frame_generation=3,
        current_track_generations={
            7: 5,
        },
    )

    assert decision.accepted
    assert decision.reason == "accepted"
    assert not decision.embedding.flags.writeable

    observation = (
        transport.last_accepted_observation
    )

    assert observation is not None
    assert observation.request_id == 1
    assert observation.track_id == 7
    assert observation.frame_generation == 3
    assert observation.track_generation == 5
    assert observation.source_frame_id == 42
    assert observation.source_image_seq == 900
    assert not observation.embedding.flags.writeable

    diagnostics = transport.diagnostics()

    assert diagnostics.queue.accepted_results == 1
    assert diagnostics.last_result_reason == "accepted"
    assert diagnostics.last_accepted_request_id == 1
    assert diagnostics.last_accepted_track_id == 7


def test_current_generation_mismatch_rejects_result():
    """Reject a result from a previous source-frame lifecycle."""
    transport = TimAppearanceRequestTransport(
        capacity=4,
        deadline_ms=500.0,
    )

    request = transport.stage(
        (crop(),),
        now_ns=1_000,
    ).requests[0]

    decision = transport.complete(
        success_result(request),
        now_ns=1_300,
        current_frame_generation=4,
        current_track_generations={
            7: 5,
        },
    )

    assert not decision.accepted
    assert (
        decision.reason
        == "frame_generation_mismatch"
    )
    assert (
        transport.last_accepted_observation
        is None
    )


def test_track_generation_mismatch_rejects_result():
    """Reject a result from a reused numeric track ID."""
    transport = TimAppearanceRequestTransport(
        capacity=4,
        deadline_ms=500.0,
    )

    request = transport.stage(
        (crop(),),
        now_ns=1_000,
    ).requests[0]

    decision = transport.complete(
        success_result(request),
        now_ns=1_300,
        current_frame_generation=3,
        current_track_generations={
            7: 6,
        },
    )

    assert not decision.accepted
    assert (
        decision.reason
        == "track_generation_mismatch"
    )


def test_cancelled_request_rejects_late_result():
    """Make late results unknown after an explicit lifecycle reset."""
    transport = TimAppearanceRequestTransport(
        capacity=4,
        deadline_ms=500.0,
    )

    request = transport.stage(
        (crop(),),
        now_ns=1_000,
    ).requests[0]

    cancelled = transport.cancel_all(
        reason="operator_clear"
    )

    assert cancelled == (1,)

    decision = transport.complete(
        success_result(request),
        now_ns=1_300,
        current_frame_generation=4,
        current_track_generations={},
    )

    assert not decision.accepted
    assert (
        decision.reason
        == "unknown_or_not_in_flight"
    )
    assert transport.diagnostics().cancelled == 1


def test_malformed_result_resolves_known_in_flight_request():
    """Convert malformed wire data into one explicit rejected result."""
    transport = TimAppearanceRequestTransport(
        capacity=4,
        deadline_ms=500.0,
    )

    request = transport.stage(
        (crop(),),
        now_ns=1_000,
    ).requests[0]

    decision = transport.reject_malformed_result(
        request_id=request.request_id,
        now_ns=1_300,
        reason="invalid embedding payload",
        current_frame_generation=3,
        current_track_generations={
            7: 5,
        },
    )

    assert decision is not None
    assert not decision.accepted
    assert decision.reason == "backend_failure"

    diagnostics = transport.diagnostics()

    assert diagnostics.malformed_results == 1
    assert diagnostics.queue.in_flight == 0


def test_request_ids_are_process_local_and_monotonic():
    """Allocate monotonically increasing IDs for one coordinator lifetime."""
    transport = TimAppearanceRequestTransport(
        capacity=4,
        deadline_ms=500.0,
    )

    first = transport.stage(
        (
            crop(
                track_id=1,
                candidate_index=0,
            ),
        ),
        now_ns=1_000,
    ).requests[0]

    second = transport.stage(
        (
            crop(
                track_id=2,
                candidate_index=1,
                source_image_seq=901,
            ),
        ),
        now_ns=1_100,
    ).requests[0]

    assert first.request_id == 1
    assert second.request_id == 2
