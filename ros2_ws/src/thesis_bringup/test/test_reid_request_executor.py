"""Tests for the perception-owned bounded ReID executor."""

from __future__ import annotations

from pathlib import Path
import threading
import time

import numpy as np

from thesis_bringup.perception.reid_request_executor import (
    BoundedReidRequestExecutor,
)
from thesis_bringup.tim_mars.appearance_async import (
    AppearanceBackendDescriptor,
    AppearanceEmbeddingRequest,
)
from thesis_bringup.tim_mars.appearance_worker import (
    DeterministicAppearanceWorker,
)


def descriptor() -> AppearanceBackendDescriptor:
    return AppearanceBackendDescriptor(
        name="test-reid",
        embedding_space="test-reid-space",
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


def request(
    request_id: int,
    *,
    track_id: int = 1,
    source_image_seq: int | None = None,
    submitted_ns: int = 100,
    deadline_ns: int = 10_000_000_000,
) -> AppearanceEmbeddingRequest:
    sequence = (
        int(request_id)
        if source_image_seq is None
        else int(source_image_seq)
    )

    return AppearanceEmbeddingRequest(
        request_id=int(request_id),
        backend=descriptor(),
        submitted_ns=int(submitted_ns),
        deadline_ns=int(deadline_ns),
        source_frame_id=int(request_id),
        track_timestamp_ns=1_000 + int(request_id),
        source_image_timestamp_ns=900 + int(request_id),
        source_image_seq=sequence,
        frame_generation=1,
        candidate_index=0,
        track_id=int(track_id),
        track_generation=1,
        source_bbox=(1.0, 2.0, 5.0, 8.0),
        crop_bgr=np.zeros(
            (6, 4, 3),
            dtype=np.uint8,
        ),
    )


def wait_until(
    predicate,
    *,
    timeout_s: float = 2.0,
) -> bool:
    deadline = time.monotonic() + timeout_s

    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)

    return bool(predicate())


def normalized_embedding() -> np.ndarray:
    value = np.ones(
        4,
        dtype=np.float32,
    )
    value /= np.linalg.norm(value)
    return value


def successful_worker():
    return DeterministicAppearanceWorker(
        descriptor=descriptor(),
        prepare=lambda crop: crop,
        make_batch=lambda crop: crop,
        infer=lambda _batch: normalized_embedding(),
        postprocess=lambda value: value,
        clock_ns=time.monotonic_ns,
    )


def test_executor_runs_one_request_and_emits_success():
    results = []

    executor = BoundedReidRequestExecutor(
        worker=successful_worker(),
        result_sink=results.append,
        capacity=2,
    )

    decision = executor.submit(
        request(
            1,
            submitted_ns=time.monotonic_ns(),
            deadline_ns=(
                time.monotonic_ns()
                + 1_000_000_000
            ),
        )
    )

    assert decision.accepted
    assert wait_until(lambda: len(results) == 1)

    result = results[0]

    assert result.request_id == 1
    assert result.error is None
    assert result.embedding.shape == (4,)

    assert executor.close()


def test_executor_rejects_duplicate_request_id():
    gate = threading.Event()
    results = []

    worker = DeterministicAppearanceWorker(
        descriptor=descriptor(),
        prepare=lambda crop: crop,
        make_batch=lambda crop: crop,
        infer=lambda _batch: (
            gate.wait(timeout=1.0)
            or normalized_embedding()
        ),
        postprocess=lambda value: (
            normalized_embedding()
            if isinstance(value, bool)
            else value
        ),
        clock_ns=time.monotonic_ns,
    )

    executor = BoundedReidRequestExecutor(
        worker=worker,
        result_sink=results.append,
        capacity=2,
    )

    now_ns = time.monotonic_ns()
    original = request(
        2,
        submitted_ns=now_ns,
        deadline_ns=now_ns + 2_000_000_000,
    )

    assert executor.submit(original).accepted

    duplicate = executor.submit(original)

    assert not duplicate.accepted
    assert duplicate.reason == "duplicate_request_id"

    gate.set()
    assert wait_until(lambda: len(results) >= 2)

    assert any(
        result.error == "duplicate_request_id"
        for result in results
    )

    assert executor.close()


def test_queue_overflow_drops_oldest_queued_request():
    gate = threading.Event()
    started = threading.Event()
    results = []

    def infer(_batch):
        started.set()
        gate.wait(timeout=1.0)
        return normalized_embedding()

    worker = DeterministicAppearanceWorker(
        descriptor=descriptor(),
        prepare=lambda crop: crop,
        make_batch=lambda crop: crop,
        infer=infer,
        postprocess=lambda value: value,
        clock_ns=time.monotonic_ns,
    )

    executor = BoundedReidRequestExecutor(
        worker=worker,
        result_sink=results.append,
        capacity=1,
    )

    now_ns = time.monotonic_ns()

    assert executor.submit(
        request(
            10,
            track_id=10,
            submitted_ns=now_ns,
            deadline_ns=now_ns + 2_000_000_000,
        )
    ).accepted

    assert started.wait(timeout=1.0)

    assert executor.submit(
        request(
            11,
            track_id=11,
            submitted_ns=now_ns,
            deadline_ns=now_ns + 2_000_000_000,
        )
    ).accepted

    decision = executor.submit(
        request(
            12,
            track_id=12,
            submitted_ns=now_ns,
            deadline_ns=now_ns + 2_000_000_000,
        )
    )

    assert decision.accepted
    assert decision.reason == "accepted_with_drop"
    assert decision.dropped_request_ids == (11,)

    gate.set()

    assert wait_until(
        lambda: any(
            item.request_id == 11
            and item.error == "overflow_drop_oldest"
            for item in results
        )
    )

    assert executor.close()


def test_newer_same_track_request_supersedes_queued_request():
    gate = threading.Event()
    started = threading.Event()
    results = []

    def infer(_batch):
        started.set()
        gate.wait(timeout=1.0)
        return normalized_embedding()

    worker = DeterministicAppearanceWorker(
        descriptor=descriptor(),
        prepare=lambda crop: crop,
        make_batch=lambda crop: crop,
        infer=infer,
        postprocess=lambda value: value,
        clock_ns=time.monotonic_ns,
    )

    executor = BoundedReidRequestExecutor(
        worker=worker,
        result_sink=results.append,
        capacity=3,
    )

    now_ns = time.monotonic_ns()

    executor.submit(
        request(
            20,
            track_id=20,
            submitted_ns=now_ns,
            deadline_ns=now_ns + 2_000_000_000,
        )
    )

    assert started.wait(timeout=1.0)

    queued = request(
        21,
        track_id=7,
        source_image_seq=21,
        submitted_ns=now_ns,
        deadline_ns=now_ns + 2_000_000_000,
    )
    newer = request(
        22,
        track_id=7,
        source_image_seq=22,
        submitted_ns=now_ns,
        deadline_ns=now_ns + 2_000_000_000,
    )

    assert executor.submit(queued).accepted

    decision = executor.submit(newer)

    assert decision.accepted
    assert decision.reason == "accepted_with_drop"
    assert decision.dropped_request_ids == (21,)

    gate.set()

    assert wait_until(
        lambda: any(
            item.request_id == 21
            and item.error
            == "superseded_before_execution"
            for item in results
        )
    )

    assert executor.close()


def test_expired_request_fails_before_worker_execution():
    calls = []
    results = []

    worker = DeterministicAppearanceWorker(
        descriptor=descriptor(),
        prepare=lambda crop: crop,
        make_batch=lambda crop: crop,
        infer=lambda batch: (
            calls.append(batch)
            or normalized_embedding()
        ),
        postprocess=lambda value: value,
        clock_ns=time.monotonic_ns,
    )

    executor = BoundedReidRequestExecutor(
        worker=worker,
        result_sink=results.append,
        capacity=2,
    )

    now_ns = time.monotonic_ns()

    expired = request(
        30,
        submitted_ns=now_ns - 2_000_000,
        deadline_ns=now_ns - 1_000_000,
    )

    assert executor.submit(expired).accepted
    assert wait_until(lambda: len(results) == 1)

    assert calls == []
    assert results[0].error == (
        "expired_before_execution"
    )

    assert executor.close()


def test_shutdown_cancels_queued_work():
    gate = threading.Event()
    started = threading.Event()
    results = []

    def infer(_batch):
        started.set()
        gate.wait(timeout=1.0)
        return normalized_embedding()

    worker = DeterministicAppearanceWorker(
        descriptor=descriptor(),
        prepare=lambda crop: crop,
        make_batch=lambda crop: crop,
        infer=infer,
        postprocess=lambda value: value,
        clock_ns=time.monotonic_ns,
    )

    executor = BoundedReidRequestExecutor(
        worker=worker,
        result_sink=results.append,
        capacity=2,
    )

    now_ns = time.monotonic_ns()

    executor.submit(
        request(
            40,
            track_id=40,
            submitted_ns=now_ns,
            deadline_ns=now_ns + 2_000_000_000,
        )
    )

    assert started.wait(timeout=1.0)

    executor.submit(
        request(
            41,
            track_id=41,
            submitted_ns=now_ns,
            deadline_ns=now_ns + 2_000_000_000,
        )
    )

    close_result = []

    close_thread = threading.Thread(
        target=lambda: close_result.append(
            executor.close(timeout_s=2.0)
        )
    )
    close_thread.start()

    assert wait_until(
        lambda: any(
            item.request_id == 41
            and item.error == "cancelled_on_shutdown"
            for item in results
        )
    )

    gate.set()
    close_thread.join(timeout=2.0)

    assert close_result == [True]


def test_pipeline_source_contains_disabled_by_default_wiring():
    pipeline = (
        Path(__file__)
        .resolve()
        .parents[1]
        / "thesis_bringup"
        / "perception"
        / "perception_pipeline_node.py"
    ).read_text(encoding="utf-8")

    required = (
        'self.declare_parameter("reid_enabled", False)',
        '"reid_request_topic"',
        '"reid_result_topic"',
        '"reid_queue_capacity"',
        "reid_hef_path=(",
        "def _run_reid_inference(",
        "def _on_reid_request(",
        "def _setup_reid_service(",
        "BoundedReidRequestExecutor",
        "ReliabilityPolicy.BEST_EFFORT",
        "DurabilityPolicy.VOLATILE",
        "executor.close(",
    )

    for fragment in required:
        assert fragment in pipeline
