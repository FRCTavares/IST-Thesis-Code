"""Hardware-independent worker boundary for asynchronous appearance inference.

This module does not import HailoRT, ROS, or cv_bridge. It converts one causal
request into one causal result by using injected preprocessing, inference, and
postprocessing callables.

The deterministic worker is intended for integration tests and contract
validation before a threaded Hailo worker is introduced.
"""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic_ns
from typing import Any, Callable, Protocol

import numpy as np

from thesis_bringup.tim_mars.appearance_async import (
    AppearanceBackendDescriptor,
    AppearanceEmbeddingRequest,
    AppearanceEmbeddingResult,
)
from thesis_bringup.tim_mars.repvgg_reid_adapter import (
    postprocess_repvgg_embedding,
    prepare_repvgg_crop,
    REPVGG_BACKEND_DESCRIPTOR,
    repvgg_batch_tensor,
)


class AppearanceRequestWorker(Protocol):
    """Worker interface consumed by a future asynchronous executor."""

    descriptor: AppearanceBackendDescriptor

    def run(
        self,
        request: AppearanceEmbeddingRequest,
    ) -> AppearanceEmbeddingResult:
        ...


@dataclass
class DeterministicAppearanceWorker:
    """Execute one request synchronously through injected pure boundaries."""

    descriptor: AppearanceBackendDescriptor
    prepare: Callable[[Any], Any]
    make_batch: Callable[[Any], np.ndarray]
    infer: Callable[[np.ndarray], Any]
    postprocess: Callable[[Any], np.ndarray]
    clock_ns: Callable[[], int] = monotonic_ns

    def _result(
        self,
        *,
        request: AppearanceEmbeddingRequest,
        started_ns: int,
        completed_ns: int,
        embedding: np.ndarray | None,
        error: str | None,
    ) -> AppearanceEmbeddingResult:
        return AppearanceEmbeddingResult(
            request_id=int(request.request_id),
            backend_name=self.descriptor.name,
            embedding_space=self.descriptor.embedding_space,
            dimension=int(self.descriptor.dimension),
            started_ns=int(started_ns),
            completed_ns=max(
                int(started_ns),
                int(completed_ns),
            ),
            embedding=embedding,
            error=error,
        )

    def run(
        self,
        request: AppearanceEmbeddingRequest,
    ) -> AppearanceEmbeddingResult:
        """Run one request and express every failure in the result envelope."""
        started_ns = int(self.clock_ns())

        if request.backend != self.descriptor:
            return self._result(
                request=request,
                started_ns=started_ns,
                completed_ns=int(self.clock_ns()),
                embedding=None,
                error=(
                    "backend descriptor mismatch: "
                    f"request={request.backend.name}, "
                    f"worker={self.descriptor.name}"
                ),
            )

        try:
            prepared = self.prepare(request.crop_bgr)
            batch = self.make_batch(prepared)
            raw_output = self.infer(batch)
            embedding = self.postprocess(raw_output)
            error = None
        except Exception as exc:
            embedding = None
            error = (
                f"{type(exc).__name__}: {exc}"
            )

        return self._result(
            request=request,
            started_ns=started_ns,
            completed_ns=int(self.clock_ns()),
            embedding=embedding,
            error=error,
        )


def make_deterministic_repvgg_worker(
    *,
    infer: Callable[[np.ndarray], Any],
    clock_ns: Callable[[], int] = monotonic_ns,
) -> DeterministicAppearanceWorker:
    """Construct the deterministic worker for the tracked RepVGG contract."""
    return DeterministicAppearanceWorker(
        descriptor=REPVGG_BACKEND_DESCRIPTOR,
        prepare=prepare_repvgg_crop,
        make_batch=repvgg_batch_tensor,
        infer=infer,
        postprocess=postprocess_repvgg_embedding,
        clock_ns=clock_ns,
    )


__all__ = [
    "AppearanceRequestWorker",
    "DeterministicAppearanceWorker",
    "make_deterministic_repvgg_worker",
]
