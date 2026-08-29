"""Pure post-MOT Target-ReID baseline for Issue #58.

The baseline deliberately isolates ordinary target appearance matching from
TIM-MARS policy.

Contract:
- the operator-selected target is represented by one fixed appearance anchor;
- every current tracker candidate may provide one appearance embedding;
- candidates are ranked only by cosine similarity to the fixed anchor;
- the highest-similarity candidate is published only when its similarity is
  greater than or equal to the configured threshold;
- otherwise the output is LOST.

Explicitly excluded:
- geometry fusion;
- tracker-ID preference;
- temporal confirmation;
- adaptive or trusted appearance-memory updates;
- hard-negative memory;
- TIM-MARS state-machine authority;
- candidate margins or recovery heuristics.

This module is ROS-free and performs no embedding extraction or bag I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np


@dataclass(frozen=True)
class TargetReIdCandidate:
    """One current post-MOT candidate with optional appearance evidence."""

    track_id: int
    bbox_xyxy: tuple[float, float, float, float]
    appearance: Any | None


@dataclass(frozen=True)
class TargetReIdDecision:
    """One stateless Target-ReID publication decision."""

    selected_candidate: TargetReIdCandidate | None
    similarity: float | None
    threshold: float

    @property
    def published(self) -> bool:
        return self.selected_candidate is not None


def _normalised_vector(value: Any | None) -> np.ndarray | None:
    """Return a finite unit vector, or None for unusable appearance evidence."""
    if value is None:
        return None

    vector = np.asarray(value, dtype=np.float32)

    if vector.ndim != 1 or vector.size == 0:
        return None

    if not np.all(np.isfinite(vector)):
        return None

    norm = float(np.linalg.norm(vector))
    if norm <= 1e-12:
        return None

    return vector / norm


def cosine_similarity(a: Any | None, b: Any | None) -> float | None:
    """Return cosine similarity for compatible usable vectors."""
    a_vector = _normalised_vector(a)
    b_vector = _normalised_vector(b)

    if a_vector is None or b_vector is None:
        return None

    if a_vector.shape != b_vector.shape:
        return None

    return float(np.dot(a_vector, b_vector))


def select_target_reid_candidate(
    *,
    anchor: Any | None,
    candidates: Sequence[TargetReIdCandidate],
    threshold: float,
) -> TargetReIdDecision:
    """Select the most anchor-similar candidate or return LOST.

    Equal-similarity ties retain the earliest candidate in input order so that
    replay behavior is deterministic without introducing an additional policy.
    """
    threshold = float(threshold)

    if not np.isfinite(threshold):
        raise ValueError("threshold must be finite")

    anchor_vector = _normalised_vector(anchor)

    if anchor_vector is None:
        return TargetReIdDecision(
            selected_candidate=None,
            similarity=None,
            threshold=threshold,
        )

    best_candidate: TargetReIdCandidate | None = None
    best_similarity: float | None = None

    for candidate in candidates:
        similarity = cosine_similarity(
            anchor_vector,
            candidate.appearance,
        )

        if similarity is None:
            continue

        if best_similarity is None or similarity > best_similarity:
            best_candidate = candidate
            best_similarity = similarity

    if (
        best_candidate is None
        or best_similarity is None
        or best_similarity < threshold
    ):
        return TargetReIdDecision(
            selected_candidate=None,
            similarity=best_similarity,
            threshold=threshold,
        )

    return TargetReIdDecision(
        selected_candidate=best_candidate,
        similarity=best_similarity,
        threshold=threshold,
    )
