"""Deterministic composed fault matrix for P044 observational ReID.

These tests compose the TIM-owned causal request ledger with the
perception-owned bounded executor. RepVGG remains observational: successful
results may be retained only as isolated observations, while failed, missing,
expired, cancelled, and late results must never become accepted observations.
"""

from __future__ import annotations

import time
from typing import Callable

import numpy as np

from thesis_bringup.perception.reid_request_executor import (
    BoundedReidRequestExecutor,
)
from thesis_bringup.tim_mars.appearance_async import (
    AppearanceEmbeddingResult,
    AppearanceResultDecision,
)
from thesis_bringup.tim_mars.appearance_request_producer import (
    AppearanceRequestCrop,
)
from thesis_bringup.tim_mars.appearance_request_transport import (
    TimAppearanceRequestTransport,
)
from thesis_bringup.tim_mars.appearance_worker import (
    DeterministicAppearanceWorker,
)
from thesis_bringup.tim_mars.repvgg_reid_adapter import (
    REPVGG_BACKEND_DESCRIPTOR,
)


TRACK_ID = 7
FRAME_GENERATION = 3
TRACK_GENERATION = 5


def request_crop() -> AppearanceRequestCrop:
    """Return one deterministic causal request crop."""
    return AppearanceRequestCrop(
        source_frame_id=42,
        track_timestamp_ns=1_000,
        source_image_timestamp_ns=900,
        source_image_seq=12,
        frame_generation=FRAME_GENERATION,
        candidate_index=0,
        track_id=TRACK_ID,
        track_generation=TRACK_GENERATION,
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


def normalized_embedding() -> np.ndarray:
    """Return a finite normalized RepVGG-space embedding."""
    value = np.ones(
        REPVGG_BACKEND_DESCRIPTOR.dimension,
        dtype=np.float32,
    )
    value /= np.linalg.norm(value)
    return value


def worker(
    *,
    fail: bool = False,
) -> DeterministicAppearanceWorker:
    """Return a deterministic success or explicit-failure worker."""

    def infer(_batch):
        if fail:
            raise RuntimeError(
                "synthetic P044 backend failure"
            )

        return normalized_embedding()

    return DeterministicAppearanceWorker(
        descriptor=REPVGG_BACKEND_DESCRIPTOR,
        prepare=lambda crop: crop,
        make_batch=lambda crop: crop,
        infer=infer,
        postprocess=lambda value: value,
        clock_ns=time.monotonic_ns,
    )


def wait_until(
    predicate: Callable[[], bool],
    *,
    timeout_s: float = 2.0,
) -> bool:
    """Wait for one asynchronous executor outcome."""
    deadline = time.monotonic() + timeout_s

    while time.monotonic() < deadline:
        if predicate():
            return True

        time.sleep(0.01)

    return bool(predicate())


def new_transport() -> TimAppearanceRequestTransport:
    """Construct one isolated TIM-side ledger."""
    return TimAppearanceRequestTransport(
        capacity=4,
        deadline_ms=500.0,
    )


def stage_request(
    transport: TimAppearanceRequestTransport,
):
    """Stage one request and assert causal in-flight ownership."""
    batch = transport.stage(
        (request_crop(),),
        now_ns=time.monotonic_ns(),
    )

    assert len(batch.requests) == 1
    assert batch.dropped_request_ids == ()
    assert batch.expired_request_ids == ()
    assert batch.rejected_submissions == 0

    request = batch.requests[0]

    assert (
        transport.diagnostics()
        .queue
        .in_flight
        == 1
    )

    return request


def complete(
    transport: TimAppearanceRequestTransport,
    result: AppearanceEmbeddingResult,
    *,
    now_ns: int | None = None,
) -> AppearanceResultDecision:
    """Apply one result using the unchanged causal generations."""
    timestamp_ns = (
        int(result.completed_ns)
        if now_ns is None
        else int(now_ns)
    )

    return transport.complete(
        result,
        now_ns=timestamp_ns,
        current_frame_generation=FRAME_GENERATION,
        current_track_generations={
            TRACK_ID: TRACK_GENERATION,
        },
    )


def test_baseline_success_is_retained_only_as_observational_state():
    """Accept one valid result without creating a decision-facing path."""
    transport = new_transport()
    decisions: list[AppearanceResultDecision] = []

    executor = BoundedReidRequestExecutor(
        worker=worker(),
        result_sink=lambda result: decisions.append(
            complete(
                transport,
                result,
            )
        ),
        capacity=2,
    )

    try:
        request = stage_request(transport)

        submission = executor.submit(request)

        assert submission.accepted
        assert submission.reason == "accepted"
        assert wait_until(
            lambda: len(decisions) == 1
        )

        decision = decisions[0]

        assert decision.accepted
        assert decision.reason == "accepted"

        observation = (
            transport.last_accepted_observation
        )

        assert observation is not None
        assert observation.request_id == (
            request.request_id
        )
        assert observation.track_id == TRACK_ID
        assert (
            observation.frame_generation
            == FRAME_GENERATION
        )
        assert (
            observation.track_generation
            == TRACK_GENERATION
        )

        diagnostics = transport.diagnostics()

        assert diagnostics.queue.in_flight == 0
        assert diagnostics.queue.accepted_results == 1
        assert diagnostics.queue.rejected_results == 0
        assert diagnostics.last_result_reason == "accepted"

        executor_diagnostics = executor.diagnostics()

        assert executor_diagnostics.executed == 1
        assert executor_diagnostics.succeeded == 1
        assert executor_diagnostics.failed == 0
        assert (
            executor_diagnostics.reasons[
                "backend_success"
            ]
            == 1
        )
    finally:
        assert executor.close()


def test_suppressed_result_expires_and_late_delivery_is_rejected():
    """Model BEST_EFFORT result loss followed by delayed delivery."""
    transport = new_transport()
    withheld_results: list[
        AppearanceEmbeddingResult
    ] = []

    executor = BoundedReidRequestExecutor(
        worker=worker(),
        result_sink=withheld_results.append,
        capacity=2,
    )

    try:
        request = stage_request(transport)

        assert executor.submit(request).accepted
        assert wait_until(
            lambda: len(withheld_results) == 1
        )

        expired = transport.expire_in_flight(
            now_ns=request.deadline_ns + 1
        )

        assert expired == (
            request.request_id,
        )

        diagnostics = transport.diagnostics()

        assert diagnostics.queue.in_flight == 0
        assert diagnostics.expired_in_flight == 1
        assert (
            diagnostics.queue.drop_reasons[
                "expired_in_flight"
            ]
            == 1
        )
        assert (
            diagnostics.last_result_reason
            == "expired_in_flight"
        )
        assert (
            transport.last_accepted_observation
            is None
        )

        late = complete(
            transport,
            withheld_results[0],
            now_ns=request.deadline_ns + 2,
        )

        assert not late.accepted
        assert (
            late.reason
            == "unknown_or_not_in_flight"
        )
        assert (
            transport.last_accepted_observation
            is None
        )
        assert (
            transport.diagnostics()
            .queue
            .in_flight
            == 0
        )
    finally:
        assert executor.close()


def test_backend_failure_reconciles_without_accepted_observation():
    """Resolve an explicit executor failure and clear TIM ownership."""
    transport = new_transport()
    decisions: list[AppearanceResultDecision] = []

    executor = BoundedReidRequestExecutor(
        worker=worker(fail=True),
        result_sink=lambda result: decisions.append(
            complete(
                transport,
                result,
            )
        ),
        capacity=2,
    )

    try:
        request = stage_request(transport)

        assert executor.submit(request).accepted
        assert wait_until(
            lambda: len(decisions) == 1
        )

        decision = decisions[0]

        assert not decision.accepted
        assert decision.reason == "backend_failure"
        assert (
            transport.last_accepted_observation
            is None
        )

        diagnostics = transport.diagnostics()

        assert diagnostics.queue.in_flight == 0
        assert diagnostics.queue.accepted_results == 0
        assert diagnostics.queue.rejected_results == 1
        assert (
            diagnostics.queue.result_reasons[
                "backend_failure"
            ]
            == 1
        )
        assert (
            diagnostics.last_result_reason
            == "backend_failure"
        )

        executor_diagnostics = executor.diagnostics()

        assert executor_diagnostics.executed == 1
        assert executor_diagnostics.succeeded == 0
        assert executor_diagnostics.failed == 1
        assert (
            executor_diagnostics.reasons[
                "backend_failure"
            ]
            == 1
        )
    finally:
        assert executor.close()


def test_lifecycle_cancel_rejects_delayed_success():
    """Reject a result delivered after an operator lifecycle reset."""
    transport = new_transport()
    withheld_results: list[
        AppearanceEmbeddingResult
    ] = []

    executor = BoundedReidRequestExecutor(
        worker=worker(),
        result_sink=withheld_results.append,
        capacity=2,
    )

    try:
        request = stage_request(transport)

        assert executor.submit(request).accepted
        assert wait_until(
            lambda: len(withheld_results) == 1
        )

        cancelled = transport.cancel_all(
            reason="operator_clear"
        )

        assert cancelled == (
            request.request_id,
        )

        cancelled_diagnostics = (
            transport.diagnostics()
        )

        assert cancelled_diagnostics.cancelled == 1
        assert (
            cancelled_diagnostics.queue.in_flight
            == 0
        )
        assert (
            cancelled_diagnostics.last_result_reason
            == "cancelled:operator_clear"
        )
        assert (
            transport.last_accepted_observation
            is None
        )

        delayed = complete(
            transport,
            withheld_results[0],
        )

        assert not delayed.accepted
        assert (
            delayed.reason
            == "unknown_or_not_in_flight"
        )
        assert (
            transport.last_accepted_observation
            is None
        )
        assert (
            transport.diagnostics()
            .queue
            .in_flight
            == 0
        )
    finally:
        assert executor.close()
