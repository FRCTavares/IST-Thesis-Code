"""Bounded single-worker executor for perception-owned ReID requests.

The executor is independent of ROS and HailoRT. It accepts validated causal
requests, keeps a bounded latest-data queue, executes one request at a time,
and emits an explicit result for success, rejection, expiry, cancellation,
or backend failure.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
import threading
from time import monotonic_ns
from typing import Callable

from thesis_bringup.tim_mars.appearance_async import (
    AppearanceEmbeddingRequest,
    AppearanceEmbeddingResult,
)
from thesis_bringup.tim_mars.appearance_worker import (
    AppearanceRequestWorker,
)


@dataclass(frozen=True)
class ReidExecutorDecision:
    """Outcome of submitting one request to the executor."""

    accepted: bool
    reason: str
    depth: int
    dropped_request_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class ReidExecutorDiagnostics:
    """Immutable bounded-executor accounting snapshot."""

    accepting: bool
    queued: int
    in_flight_request_id: int | None
    maximum_queued: int
    submitted: int
    executed: int
    succeeded: int
    failed: int
    rejected: int
    emitted_results: int
    reasons: dict[str, int]


class BoundedReidRequestExecutor:
    """Execute causal ReID requests on one dedicated bounded worker."""

    def __init__(
        self,
        *,
        worker: AppearanceRequestWorker,
        result_sink: Callable[
            [AppearanceEmbeddingResult],
            None,
        ],
        capacity: int,
        clock_ns: Callable[[], int] = monotonic_ns,
        thread_name: str = "perception_reid_worker",
    ) -> None:
        capacity = int(capacity)

        if capacity <= 0:
            raise ValueError(
                "ReID executor capacity must be positive"
            )

        self.worker = worker
        self.result_sink = result_sink
        self.capacity = capacity
        self.clock_ns = clock_ns

        self._cv = threading.Condition()
        self._queued: deque[
            AppearanceEmbeddingRequest
        ] = deque()
        self._accepting = True
        self._stop = False
        self._in_flight_request_id: int | None = None

        self._recent_request_ids: deque[int] = deque()
        self._recent_request_id_set: set[int] = set()
        self._recent_request_limit = max(
            256,
            capacity * 32,
        )

        self._submitted = 0
        self._executed = 0
        self._succeeded = 0
        self._failed = 0
        self._rejected = 0
        self._emitted_results = 0
        self._maximum_queued = 0
        self._reasons: Counter[str] = Counter()

        self._thread = threading.Thread(
            target=self._worker_loop,
            name=str(thread_name),
            daemon=True,
        )
        self._thread.start()

    def _remember_request_id_locked(
        self,
        request_id: int,
    ) -> None:
        request_id = int(request_id)

        self._recent_request_ids.append(request_id)
        self._recent_request_id_set.add(request_id)

        while (
            len(self._recent_request_ids)
            > self._recent_request_limit
        ):
            old = self._recent_request_ids.popleft()
            self._recent_request_id_set.discard(old)

    def _is_duplicate_locked(
        self,
        request_id: int,
    ) -> bool:
        request_id = int(request_id)

        if request_id in self._recent_request_id_set:
            return True

        if self._in_flight_request_id == request_id:
            return True

        return any(
            int(item.request_id) == request_id
            for item in self._queued
        )

    def _failure_result(
        self,
        request: AppearanceEmbeddingRequest,
        *,
        reason: str,
    ) -> AppearanceEmbeddingResult:
        now_ns = max(
            1,
            int(self.clock_ns()),
        )
        started_ns = max(
            int(request.submitted_ns),
            now_ns,
        )

        return AppearanceEmbeddingResult(
            request_id=int(request.request_id),
            backend_name=request.backend.name,
            embedding_space=(
                request.backend.embedding_space
            ),
            dimension=int(request.backend.dimension),
            started_ns=started_ns,
            completed_ns=started_ns,
            embedding=None,
            error=str(reason),
        )

    def _emit(
        self,
        result: AppearanceEmbeddingResult,
        *,
        reason: str,
    ) -> None:
        try:
            self.result_sink(result)
        finally:
            with self._cv:
                self._emitted_results += 1
                self._reasons[str(reason)] += 1

                if result.error is None:
                    self._succeeded += 1
                else:
                    self._failed += 1

    def submit(
        self,
        request: AppearanceEmbeddingRequest,
    ) -> ReidExecutorDecision:
        """Submit one request using newest-per-track queue semantics."""
        failures: list[
            tuple[AppearanceEmbeddingRequest, str]
        ] = []
        accepted = False
        reason = "accepted"
        dropped_ids: list[int] = []

        with self._cv:
            request_id = int(request.request_id)

            if not self._accepting:
                self._rejected += 1
                reason = "executor_not_accepting"
                failures.append((request, reason))
            elif self._is_duplicate_locked(request_id):
                self._rejected += 1
                reason = "duplicate_request_id"
                failures.append((request, reason))
            else:
                same_track = None

                for queued in self._queued:
                    if queued.track_key == request.track_key:
                        same_track = queued
                        break

                if same_track is not None:
                    if (
                        request.source_order
                        <= same_track.source_order
                    ):
                        self._rejected += 1
                        reason = (
                            "not_newer_than_queued_same_track"
                        )
                        failures.append((request, reason))
                    else:
                        self._queued.remove(same_track)
                        dropped_ids.append(
                            int(same_track.request_id)
                        )
                        failures.append(
                            (
                                same_track,
                                "superseded_before_execution",
                            )
                        )

                if not failures or (
                    failures
                    and failures[-1][0] is not request
                ):
                    if len(self._queued) >= self.capacity:
                        oldest = self._queued.popleft()
                        dropped_ids.append(
                            int(oldest.request_id)
                        )
                        failures.append(
                            (
                                oldest,
                                "overflow_drop_oldest",
                            )
                        )

                    self._queued.append(request)
                    self._remember_request_id_locked(
                        request_id
                    )
                    self._submitted += 1
                    self._maximum_queued = max(
                        self._maximum_queued,
                        len(self._queued),
                    )
                    accepted = True
                    reason = (
                        "accepted_with_drop"
                        if dropped_ids
                        else "accepted"
                    )
                    self._cv.notify()

            depth = len(self._queued)

        for dropped, drop_reason in failures:
            self._emit(
                self._failure_result(
                    dropped,
                    reason=drop_reason,
                ),
                reason=drop_reason,
            )

        return ReidExecutorDecision(
            accepted=accepted,
            reason=reason,
            depth=depth,
            dropped_request_ids=tuple(dropped_ids),
        )

    def _worker_loop(self) -> None:
        while True:
            request = None

            with self._cv:
                while not self._stop and not self._queued:
                    self._cv.wait(timeout=0.2)

                if self._stop and not self._queued:
                    return

                if self._queued:
                    request = self._queued.popleft()
                    self._in_flight_request_id = int(
                        request.request_id
                    )

            if request is None:
                continue

            now_ns = max(
                1,
                int(self.clock_ns()),
            )

            if now_ns > int(request.deadline_ns):
                result = self._failure_result(
                    request,
                    reason="expired_before_execution",
                )
                emit_reason = "expired_before_execution"
            else:
                result = self.worker.run(request)
                emit_reason = (
                    "backend_success"
                    if result.error is None
                    else "backend_failure"
                )

            with self._cv:
                self._executed += 1

            self._emit(
                result,
                reason=emit_reason,
            )

            with self._cv:
                self._in_flight_request_id = None
                self._cv.notify_all()

    def close(
        self,
        *,
        timeout_s: float = 5.0,
    ) -> bool:
        """Stop accepting requests, cancel queued work, and join."""
        cancelled: list[
            AppearanceEmbeddingRequest
        ] = []

        with self._cv:
            if not self._accepting and self._stop:
                thread = self._thread
            else:
                self._accepting = False
                self._stop = True

                while self._queued:
                    cancelled.append(
                        self._queued.popleft()
                    )

                self._cv.notify_all()
                thread = self._thread

        for request in cancelled:
            self._emit(
                self._failure_result(
                    request,
                    reason="cancelled_on_shutdown",
                ),
                reason="cancelled_on_shutdown",
            )

        thread.join(
            timeout=max(
                0.0,
                float(timeout_s),
            )
        )

        return not thread.is_alive()

    def diagnostics(
        self,
    ) -> ReidExecutorDiagnostics:
        """Return an immutable accounting snapshot."""
        with self._cv:
            return ReidExecutorDiagnostics(
                accepting=bool(self._accepting),
                queued=len(self._queued),
                in_flight_request_id=(
                    self._in_flight_request_id
                ),
                maximum_queued=int(
                    self._maximum_queued
                ),
                submitted=int(self._submitted),
                executed=int(self._executed),
                succeeded=int(self._succeeded),
                failed=int(self._failed),
                rejected=int(self._rejected),
                emitted_results=int(
                    self._emitted_results
                ),
                reasons=dict(self._reasons),
            )


__all__ = [
    "BoundedReidRequestExecutor",
    "ReidExecutorDecision",
    "ReidExecutorDiagnostics",
]
