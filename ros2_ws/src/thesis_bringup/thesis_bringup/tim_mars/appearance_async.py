"""Causal request and result contracts for asynchronous ReID inference.

This module is deliberately ROS-free and Hailo-free. It defines the lifecycle
boundary needed before TIM-MARS may submit appearance work to an asynchronous
accelerator.

The contract does not select targets, mutate target memory, perform inference,
or attach results to candidates. It provides:

* explicit embedding-space descriptors;
* safe startup fallback resolution;
* one-crop requests with complete causal provenance;
* a bounded latest-data queue;
* explicit overflow, supersession, and expiry accounting;
* result validation against current frame and tracker generations;
* rejection of late, reordered, failed, malformed, or incompatible results.

CPU MARS and the available Hailo RepVGG model are different embedding spaces.
Their vectors must never share one appearance memory merely because both are
called ReID embeddings.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Mapping

import numpy as np

from thesis_bringup.tim_mars.types import BBox


@dataclass(frozen=True)
class AppearanceBackendDescriptor:
    """Stable identity and tensor contract for one embedding backend."""

    name: str
    embedding_space: str
    dimension: int
    input_height: int
    input_width: int
    input_channels: int = 3
    input_layout: str = "NHWC"
    input_dtype: str = "uint8"
    raw_output_dtype: str = "float32"
    embedding_dtype: str = "float32"
    l2_normalized: bool = True

    def __post_init__(self) -> None:
        if not str(self.name).strip():
            raise ValueError("backend name must be non-empty")
        if not str(self.embedding_space).strip():
            raise ValueError("embedding space must be non-empty")
        if int(self.dimension) <= 0:
            raise ValueError("embedding dimension must be positive")
        if int(self.input_height) <= 0:
            raise ValueError("input height must be positive")
        if int(self.input_width) <= 0:
            raise ValueError("input width must be positive")
        if int(self.input_channels) <= 0:
            raise ValueError("input channels must be positive")
        if str(self.input_layout) not in {"NHWC", "NCHW"}:
            raise ValueError("input layout must be NHWC or NCHW")

    def representation_compatible_with(
        self,
        other: "AppearanceBackendDescriptor",
    ) -> bool:
        """Return whether both backends may safely share appearance memory."""
        return bool(
            self.embedding_space == other.embedding_space
            and int(self.dimension) == int(other.dimension)
            and self.embedding_dtype == other.embedding_dtype
            and bool(self.l2_normalized) == bool(other.l2_normalized)
        )


@dataclass(frozen=True)
class AppearanceBackendResolution:
    """Result of selecting a primary backend or a safe startup fallback."""

    backend: AppearanceBackendDescriptor | None
    mode: str
    reason: str


def resolve_appearance_backend(
    *,
    primary: AppearanceBackendDescriptor,
    primary_available: bool,
    fallback: AppearanceBackendDescriptor | None = None,
) -> AppearanceBackendResolution:
    """Resolve a backend without mixing incompatible representations.

    Fallback is a startup/session decision. An unavailable 512D RepVGG backend
    must not silently fall back to a 128D MARS backend while retaining existing
    appearance memory.
    """
    if bool(primary_available):
        return AppearanceBackendResolution(
            backend=primary,
            mode="primary",
            reason="primary_available",
        )

    if fallback is None:
        return AppearanceBackendResolution(
            backend=None,
            mode="fail_closed",
            reason="primary_unavailable_no_fallback",
        )

    if not primary.representation_compatible_with(fallback):
        return AppearanceBackendResolution(
            backend=None,
            mode="fail_closed",
            reason="incompatible_fallback_embedding_space",
        )

    return AppearanceBackendResolution(
        backend=fallback,
        mode="fallback",
        reason="compatible_fallback",
    )


@dataclass(frozen=True)
class AppearanceEmbeddingRequest:
    """One causally identified candidate crop submitted for embedding."""

    request_id: int
    backend: AppearanceBackendDescriptor
    submitted_ns: int
    deadline_ns: int

    source_frame_id: int
    track_timestamp_ns: int
    source_image_timestamp_ns: int
    source_image_seq: int

    frame_generation: int
    candidate_index: int
    track_id: int
    track_generation: int

    source_bbox: BBox
    crop_bgr: Any = field(
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if int(self.request_id) <= 0:
            raise ValueError("request_id must be positive")
        if int(self.submitted_ns) <= 0:
            raise ValueError("submitted_ns must be positive")
        if int(self.deadline_ns) < int(self.submitted_ns):
            raise ValueError("deadline precedes submission")
        if int(self.source_frame_id) <= 0:
            raise ValueError("source_frame_id must be positive")
        if int(self.track_timestamp_ns) <= 0:
            raise ValueError("track_timestamp_ns must be positive")
        if int(self.source_image_timestamp_ns) <= 0:
            raise ValueError(
                "source_image_timestamp_ns must be positive"
            )
        if (
            int(self.source_image_timestamp_ns)
            > int(self.track_timestamp_ns)
        ):
            raise ValueError(
                "appearance image must not be newer than the track frame"
            )
        if int(self.source_image_seq) < 0:
            raise ValueError("source_image_seq must be non-negative")
        if int(self.frame_generation) <= 0:
            raise ValueError("frame_generation must be positive")
        if int(self.candidate_index) < 0:
            raise ValueError("candidate_index must be non-negative")
        if int(self.track_id) <= 0:
            raise ValueError("track_id must be positive")
        if int(self.track_generation) <= 0:
            raise ValueError("track_generation must be positive")

        bbox = tuple(float(value) for value in self.source_bbox)

        if len(bbox) != 4:
            raise ValueError("source_bbox must contain four values")
        if not all(isfinite(value) for value in bbox):
            raise ValueError("source_bbox must be finite")
        if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
            raise ValueError("source_bbox must have positive area")

    @property
    def track_key(self) -> tuple[int, int, int]:
        """Identity key protected by frame and tracker generations."""
        return (
            int(self.frame_generation),
            int(self.track_id),
            int(self.track_generation),
        )

    @property
    def source_order(self) -> tuple[int, int, int]:
        """Monotonic observation ordering used for stale-result rejection."""
        return (
            int(self.source_image_timestamp_ns),
            int(self.source_image_seq),
            int(self.request_id),
        )


@dataclass(frozen=True)
class AppearanceEmbeddingResult:
    """Postprocessed result returned by an asynchronous backend worker."""

    request_id: int
    backend_name: str
    embedding_space: str
    dimension: int
    started_ns: int
    completed_ns: int
    embedding: Any = field(
        default=None,
        repr=False,
        compare=False,
    )
    error: str | None = None


@dataclass(frozen=True)
class AppearanceQueueDecision:
    """Outcome of attempting to enqueue one request."""

    accepted: bool
    reason: str
    depth: int
    dropped_request_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class AppearanceDequeueBatch:
    """Requests moved from the bounded queue into the in-flight set."""

    requests: tuple[AppearanceEmbeddingRequest, ...]
    expired_request_ids: tuple[int, ...]
    depth: int
    in_flight: int


@dataclass(frozen=True)
class AppearanceResultDecision:
    """Outcome of attempting to apply one asynchronous result."""

    accepted: bool
    reason: str
    request_id: int
    track_id: int | None
    embedding: np.ndarray | None = field(
        default=None,
        repr=False,
        compare=False,
    )


@dataclass(frozen=True)
class AppearanceAsyncDiagnostics:
    """Snapshot of queue and result-gate accounting."""

    queued: int
    in_flight: int
    maximum_queued: int
    submitted: int
    dequeued: int
    accepted_results: int
    rejected_submissions: int
    rejected_results: int
    drop_reasons: dict[str, int]
    result_reasons: dict[str, int]


class CausalAppearanceRequestQueue:
    """Bounded latest-data queue and causal asynchronous result gate."""

    def __init__(self, *, capacity: int) -> None:
        capacity = int(capacity)

        if capacity <= 0:
            raise ValueError("queue capacity must be positive")

        self.capacity = capacity
        self._queued: deque[AppearanceEmbeddingRequest] = deque()
        self._in_flight: dict[int, AppearanceEmbeddingRequest] = {}
        self._seen_request_ids: set[int] = set()

        self._last_accepted_source_order: dict[
            tuple[int, int, int],
            tuple[int, int, int],
        ] = {}

        self._submitted = 0
        self._dequeued = 0
        self._accepted_results = 0
        self._rejected_submissions = 0
        self._rejected_results = 0
        self._maximum_queued = 0

        self._drop_reasons: Counter[str] = Counter()
        self._result_reasons: Counter[str] = Counter()

    def _submission_rejection(
        self,
        reason: str,
    ) -> AppearanceQueueDecision:
        self._rejected_submissions += 1
        self._drop_reasons[str(reason)] += 1

        return AppearanceQueueDecision(
            accepted=False,
            reason=str(reason),
            depth=len(self._queued),
        )

    def submit(
        self,
        request: AppearanceEmbeddingRequest,
    ) -> AppearanceQueueDecision:
        """Submit a request, retaining the newest queued crop per track."""
        request_id = int(request.request_id)

        if request_id in self._seen_request_ids:
            return self._submission_rejection(
                "duplicate_request_id"
            )

        same_track: AppearanceEmbeddingRequest | None = None

        for queued in self._queued:
            if queued.track_key == request.track_key:
                same_track = queued
                break

        dropped: list[int] = []

        if same_track is not None:
            if request.source_order <= same_track.source_order:
                return self._submission_rejection(
                    "not_newer_than_queued_same_track"
                )

            self._queued.remove(same_track)
            dropped.append(int(same_track.request_id))
            self._drop_reasons["superseded_same_track"] += 1

        if len(self._queued) >= self.capacity:
            oldest = self._queued.popleft()
            dropped.append(int(oldest.request_id))
            self._drop_reasons["overflow_drop_oldest"] += 1

        self._queued.append(request)
        self._seen_request_ids.add(request_id)
        self._submitted += 1
        self._maximum_queued = max(
            self._maximum_queued,
            len(self._queued),
        )

        reason = (
            "accepted_with_drop"
            if dropped
            else "accepted"
        )

        return AppearanceQueueDecision(
            accepted=True,
            reason=reason,
            depth=len(self._queued),
            dropped_request_ids=tuple(dropped),
        )

    def dequeue(
        self,
        *,
        max_items: int,
        now_ns: int,
    ) -> AppearanceDequeueBatch:
        """Move non-expired requests into the in-flight set."""
        max_items = int(max_items)
        now_ns = int(now_ns)

        if max_items <= 0:
            raise ValueError("max_items must be positive")
        if now_ns <= 0:
            raise ValueError("now_ns must be positive")

        retained: deque[AppearanceEmbeddingRequest] = deque()
        expired: list[int] = []

        while self._queued:
            request = self._queued.popleft()

            if now_ns > int(request.deadline_ns):
                expired.append(int(request.request_id))
                self._drop_reasons["expired_before_dequeue"] += 1
            else:
                retained.append(request)

        self._queued = retained
        selected: list[AppearanceEmbeddingRequest] = []

        while self._queued and len(selected) < max_items:
            request = self._queued.popleft()
            request_id = int(request.request_id)
            self._in_flight[request_id] = request
            selected.append(request)

        self._dequeued += len(selected)

        return AppearanceDequeueBatch(
            requests=tuple(selected),
            expired_request_ids=tuple(expired),
            depth=len(self._queued),
            in_flight=len(self._in_flight),
        )

    def _result_rejection(
        self,
        *,
        result: AppearanceEmbeddingResult,
        request: AppearanceEmbeddingRequest | None,
        reason: str,
    ) -> AppearanceResultDecision:
        self._rejected_results += 1
        self._result_reasons[str(reason)] += 1

        return AppearanceResultDecision(
            accepted=False,
            reason=str(reason),
            request_id=int(result.request_id),
            track_id=(
                int(request.track_id)
                if request is not None
                else None
            ),
        )

    def complete(
        self,
        result: AppearanceEmbeddingResult,
        *,
        now_ns: int,
        current_frame_generation: int,
        current_track_generations: Mapping[int, int],
    ) -> AppearanceResultDecision:
        """Validate one completed embedding before it may enter cache state."""
        request_id = int(result.request_id)
        request = self._in_flight.pop(request_id, None)

        if request is None:
            return self._result_rejection(
                result=result,
                request=None,
                reason="unknown_or_not_in_flight",
            )

        now_ns = int(now_ns)

        if (
            int(result.started_ns) < int(request.submitted_ns)
            or int(result.completed_ns) < int(result.started_ns)
            or int(result.completed_ns) > now_ns
        ):
            return self._result_rejection(
                result=result,
                request=request,
                reason="invalid_result_timing",
            )

        if (
            int(result.completed_ns) > int(request.deadline_ns)
            or now_ns > int(request.deadline_ns)
        ):
            return self._result_rejection(
                result=result,
                request=request,
                reason="deadline_expired_before_apply",
            )

        descriptor = request.backend

        if (
            str(result.backend_name) != descriptor.name
            or str(result.embedding_space)
            != descriptor.embedding_space
            or int(result.dimension) != int(descriptor.dimension)
        ):
            return self._result_rejection(
                result=result,
                request=request,
                reason="backend_contract_mismatch",
            )

        if (
            int(current_frame_generation)
            != int(request.frame_generation)
        ):
            return self._result_rejection(
                result=result,
                request=request,
                reason="frame_generation_mismatch",
            )

        active_track_generation = current_track_generations.get(
            int(request.track_id)
        )

        if active_track_generation is None:
            return self._result_rejection(
                result=result,
                request=request,
                reason="track_not_active",
            )

        if (
            int(active_track_generation)
            != int(request.track_generation)
        ):
            return self._result_rejection(
                result=result,
                request=request,
                reason="track_generation_mismatch",
            )

        previous_order = self._last_accepted_source_order.get(
            request.track_key
        )

        if (
            previous_order is not None
            and request.source_order <= previous_order
        ):
            return self._result_rejection(
                result=result,
                request=request,
                reason="superseded_result",
            )

        if result.error is not None or result.embedding is None:
            return self._result_rejection(
                result=result,
                request=request,
                reason="backend_failure",
            )

        embedding = np.asarray(
            result.embedding,
            dtype=np.float32,
        )

        if embedding.ndim != 1:
            return self._result_rejection(
                result=result,
                request=request,
                reason="embedding_not_vector",
            )

        if embedding.size != int(descriptor.dimension):
            return self._result_rejection(
                result=result,
                request=request,
                reason="embedding_dimension_mismatch",
            )

        if not np.all(np.isfinite(embedding)):
            return self._result_rejection(
                result=result,
                request=request,
                reason="embedding_non_finite",
            )

        norm = float(np.linalg.norm(embedding))

        if norm <= 1e-12:
            return self._result_rejection(
                result=result,
                request=request,
                reason="embedding_zero_norm",
            )

        if descriptor.l2_normalized and not np.isclose(
            norm,
            1.0,
            rtol=1e-3,
            atol=1e-3,
        ):
            return self._result_rejection(
                result=result,
                request=request,
                reason="embedding_not_l2_normalized",
            )

        accepted = embedding.copy()
        accepted.setflags(write=False)

        self._last_accepted_source_order[
            request.track_key
        ] = request.source_order
        self._accepted_results += 1
        self._result_reasons["accepted"] += 1

        return AppearanceResultDecision(
            accepted=True,
            reason="accepted",
            request_id=request_id,
            track_id=int(request.track_id),
            embedding=accepted,
        )

    def cancel_all(self, *, reason: str) -> tuple[int, ...]:
        """Cancel queued and in-flight work during lifecycle reset."""
        request_ids = [
            int(request.request_id)
            for request in self._queued
        ]
        request_ids.extend(self._in_flight)

        self._queued.clear()
        self._in_flight.clear()

        if request_ids:
            self._drop_reasons[
                f"cancelled:{str(reason)}"
            ] += len(request_ids)

        return tuple(request_ids)

    def diagnostics(self) -> AppearanceAsyncDiagnostics:
        """Return an immutable accounting snapshot."""
        return AppearanceAsyncDiagnostics(
            queued=len(self._queued),
            in_flight=len(self._in_flight),
            maximum_queued=int(self._maximum_queued),
            submitted=int(self._submitted),
            dequeued=int(self._dequeued),
            accepted_results=int(self._accepted_results),
            rejected_submissions=int(self._rejected_submissions),
            rejected_results=int(self._rejected_results),
            drop_reasons=dict(self._drop_reasons),
            result_reasons=dict(self._result_reasons),
        )


__all__ = [
    "AppearanceAsyncDiagnostics",
    "AppearanceBackendDescriptor",
    "AppearanceBackendResolution",
    "AppearanceDequeueBatch",
    "AppearanceEmbeddingRequest",
    "AppearanceEmbeddingResult",
    "AppearanceQueueDecision",
    "AppearanceResultDecision",
    "CausalAppearanceRequestQueue",
    "resolve_appearance_backend",
]
