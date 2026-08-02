"""TIM-owned causal ledger for asynchronous RepVGG transport.

The coordinator is ROS-free and Hailo-free. It converts immutable staged
candidate crops into complete RepVGG requests, records each published request
as in-flight, validates returned results against current lifecycle generations,
and retains only the latest accepted observation for diagnostics.

It does not modify TIM-MARS candidates, CPU MARS features, positive memory,
hard-negative memory, or selected-target decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import numpy as np

from thesis_bringup.tim_mars.appearance_async import (
    AppearanceAsyncDiagnostics,
    AppearanceEmbeddingRequest,
    AppearanceEmbeddingResult,
    AppearanceResultDecision,
    CausalAppearanceRequestQueue,
)
from thesis_bringup.tim_mars.appearance_request_producer import (
    AppearanceRequestCrop,
)
from thesis_bringup.tim_mars.repvgg_reid_adapter import (
    REPVGG_BACKEND_DESCRIPTOR,
)


_UINT64_MAX = (1 << 64) - 1


@dataclass(frozen=True)
class AppearanceTransportBatch:
    """Requests ready for ROS publication after causal-ledger admission."""

    requests: tuple[AppearanceEmbeddingRequest, ...]
    dropped_request_ids: tuple[int, ...]
    expired_request_ids: tuple[int, ...]
    rejected_submissions: int


@dataclass(frozen=True)
class AcceptedAppearanceObservation:
    """One accepted RepVGG observation isolated from CPU MARS memory."""

    request_id: int
    track_id: int
    frame_generation: int
    track_generation: int
    source_frame_id: int
    source_image_timestamp_ns: int
    source_image_seq: int
    accepted_ns: int
    embedding: Any = field(
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        embedding = np.asarray(
            self.embedding,
            dtype=np.float32,
        )

        if embedding.ndim != 1:
            raise ValueError(
                "accepted observation embedding must be a vector"
            )

        if (
            embedding.size
            != REPVGG_BACKEND_DESCRIPTOR.dimension
        ):
            raise ValueError(
                "accepted observation dimension mismatch"
            )

        if not np.all(np.isfinite(embedding)):
            raise ValueError(
                "accepted observation must be finite"
            )

        owned = np.ascontiguousarray(
            embedding.copy(),
            dtype=np.float32,
        )
        owned.setflags(write=False)

        object.__setattr__(
            self,
            "embedding",
            owned,
        )


@dataclass(frozen=True)
class AppearanceTransportDiagnostics:
    """Snapshot of TIM-side request and result transport accounting."""

    queue: AppearanceAsyncDiagnostics
    constructed: int
    published: int
    cancelled: int
    expired_in_flight: int
    malformed_results: int
    last_result_reason: str | None
    last_accepted_request_id: int | None
    last_accepted_track_id: int | None


class TimAppearanceRequestTransport:
    """Construct, publish-track, validate, and cancel RepVGG work."""

    def __init__(
        self,
        *,
        capacity: int,
        deadline_ms: float,
    ) -> None:
        capacity = int(capacity)
        deadline_ms = float(deadline_ms)

        if capacity <= 0:
            raise ValueError(
                "transport capacity must be positive"
            )

        if deadline_ms <= 0.0:
            raise ValueError(
                "transport deadline must be positive"
            )

        self.capacity = capacity
        self.deadline_ns = max(
            1,
            int(round(deadline_ms * 1_000_000.0)),
        )

        self._queue = CausalAppearanceRequestQueue(
            capacity=capacity
        )
        self._next_request_id = 1
        self._requests_by_id: dict[
            int,
            AppearanceEmbeddingRequest,
        ] = {}

        self._constructed = 0
        self._published = 0
        self._cancelled = 0
        self._malformed_results = 0
        self._last_result_reason: str | None = None
        self._last_accepted: (
            AcceptedAppearanceObservation | None
        ) = None

    def _allocate_request_id(self) -> int:
        request_id = int(self._next_request_id)

        if request_id <= 0 or request_id > _UINT64_MAX:
            raise RuntimeError(
                "appearance request ID space exhausted"
            )

        self._next_request_id += 1
        return request_id

    def _request_from_crop(
        self,
        crop: AppearanceRequestCrop,
        *,
        now_ns: int,
    ) -> AppearanceEmbeddingRequest:
        return AppearanceEmbeddingRequest(
            request_id=self._allocate_request_id(),
            backend=REPVGG_BACKEND_DESCRIPTOR,
            submitted_ns=int(now_ns),
            deadline_ns=(
                int(now_ns) + self.deadline_ns
            ),
            source_frame_id=int(
                crop.source_frame_id
            ),
            track_timestamp_ns=int(
                crop.track_timestamp_ns
            ),
            source_image_timestamp_ns=int(
                crop.source_image_timestamp_ns
            ),
            source_image_seq=int(
                crop.source_image_seq
            ),
            frame_generation=int(
                crop.frame_generation
            ),
            candidate_index=int(
                crop.candidate_index
            ),
            track_id=int(crop.track_id),
            track_generation=int(
                crop.track_generation
            ),
            source_bbox=tuple(
                float(value)
                for value in crop.source_bbox
            ),
            crop_bgr=crop.crop_bgr,
        )

    def stage(
        self,
        crops: Sequence[AppearanceRequestCrop],
        *,
        now_ns: int,
    ) -> AppearanceTransportBatch:
        """Admit staged crops and return requests ready for publication."""
        now_ns = int(now_ns)

        if now_ns <= 0:
            raise ValueError(
                "transport staging time must be positive"
            )

        dropped: list[int] = []
        rejected = 0

        for crop in tuple(crops):
            request = self._request_from_crop(
                crop,
                now_ns=now_ns,
            )
            self._constructed += 1

            decision = self._queue.submit(request)

            if not decision.accepted:
                rejected += 1
                continue

            request_id = int(request.request_id)
            self._requests_by_id[
                request_id
            ] = request

            for dropped_id in (
                decision.dropped_request_ids
            ):
                dropped_id = int(dropped_id)
                dropped.append(dropped_id)
                self._requests_by_id.pop(
                    dropped_id,
                    None,
                )

        diagnostics = self._queue.diagnostics()

        if diagnostics.queued <= 0:
            return AppearanceTransportBatch(
                requests=(),
                dropped_request_ids=tuple(dropped),
                expired_request_ids=(),
                rejected_submissions=rejected,
            )

        batch = self._queue.dequeue(
            max_items=self.capacity,
            now_ns=now_ns,
        )

        for expired_id in batch.expired_request_ids:
            self._requests_by_id.pop(
                int(expired_id),
                None,
            )

        self._published += len(batch.requests)

        return AppearanceTransportBatch(
            requests=batch.requests,
            dropped_request_ids=tuple(dropped),
            expired_request_ids=(
                batch.expired_request_ids
            ),
            rejected_submissions=rejected,
        )

    def expire_in_flight(
        self,
        *,
        now_ns: int,
    ) -> tuple[int, ...]:
        """Expire overdue requests and reconcile transport ownership."""
        expired = self._queue.expire_in_flight(
            now_ns=int(now_ns)
        )

        for request_id in expired:
            self._requests_by_id.pop(
                int(request_id),
                None,
            )

        if expired:
            self._last_result_reason = (
                "expired_in_flight"
            )

        return expired

    def complete(
        self,
        result: AppearanceEmbeddingResult,
        *,
        now_ns: int,
        current_frame_generation: int,
        current_track_generations: Mapping[int, int],
    ) -> AppearanceResultDecision:
        """Validate one worker result and retain no decision-facing state."""
        request_id = int(result.request_id)
        request = self._requests_by_id.get(
            request_id
        )

        decision = self._queue.complete(
            result,
            now_ns=int(now_ns),
            current_frame_generation=int(
                current_frame_generation
            ),
            current_track_generations=(
                current_track_generations
            ),
        )

        self._requests_by_id.pop(
            request_id,
            None,
        )
        self._last_result_reason = str(
            decision.reason
        )

        if (
            decision.accepted
            and decision.embedding is not None
            and request is not None
            and decision.track_id is not None
        ):
            self._last_accepted = (
                AcceptedAppearanceObservation(
                    request_id=request_id,
                    track_id=int(
                        decision.track_id
                    ),
                    frame_generation=int(
                        request.frame_generation
                    ),
                    track_generation=int(
                        request.track_generation
                    ),
                    source_frame_id=int(
                        request.source_frame_id
                    ),
                    source_image_timestamp_ns=int(
                        request
                        .source_image_timestamp_ns
                    ),
                    source_image_seq=int(
                        request.source_image_seq
                    ),
                    accepted_ns=int(now_ns),
                    embedding=decision.embedding,
                )
            )

        return decision

    def reject_malformed_result(
        self,
        *,
        request_id: int,
        now_ns: int,
        reason: str,
        current_frame_generation: int,
        current_track_generations: Mapping[int, int],
    ) -> AppearanceResultDecision | None:
        """Resolve a malformed wire result for a known in-flight request."""
        request_id = int(request_id)
        request = self._requests_by_id.get(
            request_id
        )

        self._malformed_results += 1

        if request is None:
            return None

        timestamp_ns = max(
            int(request.submitted_ns),
            int(now_ns),
        )

        failure = AppearanceEmbeddingResult(
            request_id=request_id,
            backend_name=request.backend.name,
            embedding_space=(
                request.backend.embedding_space
            ),
            dimension=int(
                request.backend.dimension
            ),
            started_ns=timestamp_ns,
            completed_ns=timestamp_ns,
            embedding=None,
            error=(
                "malformed_result: "
                + str(reason)
            ),
        )

        return self.complete(
            failure,
            now_ns=int(now_ns),
            current_frame_generation=int(
                current_frame_generation
            ),
            current_track_generations=(
                current_track_generations
            ),
        )

    def cancel_all(
        self,
        *,
        reason: str,
    ) -> tuple[int, ...]:
        """Cancel all queued and in-flight work for one lifecycle reset."""
        request_ids = self._queue.cancel_all(
            reason=str(reason)
        )

        for request_id in request_ids:
            self._requests_by_id.pop(
                int(request_id),
                None,
            )

        self._cancelled += len(request_ids)
        self._last_accepted = None
        self._last_result_reason = (
            "cancelled:" + str(reason)
        )

        return request_ids

    @property
    def last_accepted_observation(
        self,
    ) -> AcceptedAppearanceObservation | None:
        """Return the latest accepted isolated RepVGG observation."""
        return self._last_accepted

    def diagnostics(
        self,
    ) -> AppearanceTransportDiagnostics:
        """Return immutable transport diagnostics."""
        observation = self._last_accepted
        queue = self._queue.diagnostics()

        return AppearanceTransportDiagnostics(
            queue=queue,
            constructed=int(self._constructed),
            published=int(self._published),
            cancelled=int(self._cancelled),
            expired_in_flight=int(
                queue.expired_in_flight
            ),
            malformed_results=int(
                self._malformed_results
            ),
            last_result_reason=(
                self._last_result_reason
            ),
            last_accepted_request_id=(
                None
                if observation is None
                else int(observation.request_id)
            ),
            last_accepted_track_id=(
                None
                if observation is None
                else int(observation.track_id)
            ),
        )


__all__ = [
    "AcceptedAppearanceObservation",
    "AppearanceTransportBatch",
    "AppearanceTransportDiagnostics",
    "TimAppearanceRequestTransport",
]
