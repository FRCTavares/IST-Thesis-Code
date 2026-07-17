"""Hard-negative appearance memory for TIM-MARS.

Hard negatives are bounded appearance prototypes of nearby non-selected tracks
observed during trusted selected-target continuity. Each prototype retains
provenance describing which tracker IDs and selected lineages contributed to it.

The store remains compatible with legacy raw-feature entries so old diagnostic
tests and locally constructed memories continue to work.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Sequence

from thesis_bringup.tim_mars.appearance_memory import (
    cosine_similarity,
    update_feature_memory,
)
from thesis_bringup.tim_mars.geometry_scoring import clamp01
from thesis_bringup.tim_mars.types import (
    CandidateScore,
    CandidateTrack,
    TargetMemoryConfig,
    TargetState,
)


@dataclass(frozen=True)
class HardNegativeEntry:
    """A distractor prototype with bounded learning provenance."""

    appearance: Any
    source_track_ids: tuple[int, ...]
    selected_track_ids: tuple[int, ...]
    source: str
    observations: int
    positive_similarity: float
    geometry_strength: float


def _append_unique(
    values: tuple[int, ...],
    value: int,
) -> tuple[int, ...]:
    value = int(value)
    if value in values:
        return values
    return values + (value,)


def _appearance_of(entry: Any) -> Any:
    if isinstance(entry, HardNegativeEntry):
        return entry.appearance
    return entry


class HardNegativeMemory:
    """Small bounded memory of distractor appearance prototypes."""

    def __init__(self) -> None:
        self._memory: List[Any] = []

    def __len__(self) -> int:
        return len(self._memory)

    @property
    def entries(self) -> tuple[HardNegativeEntry, ...]:
        """Return provenance-bearing views of stored prototypes."""

        result = []
        for entry in self._memory:
            if isinstance(entry, HardNegativeEntry):
                result.append(entry)
                continue

            result.append(
                HardNegativeEntry(
                    appearance=entry,
                    source_track_ids=(),
                    selected_track_ids=(),
                    source="legacy_unattributed",
                    observations=1,
                    positive_similarity=0.0,
                    geometry_strength=0.0,
                )
            )

        return tuple(result)

    def clear(self) -> None:
        self._memory = []

    def reconcile_selected(
        self,
        appearance: Any,
        cfg: TargetMemoryConfig,
    ) -> None:
        """Remove prototypes matching a trusted selected identity."""

        if appearance is None or not self._memory:
            return

        threshold = float(
            cfg.hard_negative_min_candidate_similarity
        )
        self._memory = [
            entry
            for entry in self._memory
            if clamp01(
                cosine_similarity(
                    _appearance_of(entry),
                    appearance,
                )
            )
            < threshold
        ]

    def similarity(
        self,
        appearance: Any,
        cfg: TargetMemoryConfig,
    ) -> float:
        if not cfg.hard_negative_memory_enabled:
            return 0.0
        if appearance is None or not self._memory:
            return 0.0

        return max(
            clamp01(
                cosine_similarity(
                    _appearance_of(entry),
                    appearance,
                )
            )
            for entry in self._memory
        )

    def should_reject(
        self,
        best: CandidateScore,
        cfg: TargetMemoryConfig,
    ) -> bool:
        if not cfg.hard_negative_memory_enabled:
            return False
        if not best.geometry_allows_appearance:
            return False
        return bool(best.hard_negative_reject)

    def update(
        self,
        *,
        candidates: Sequence[CandidateTrack],
        scores_sorted: List[CandidateScore],
        selected_track_id: int | None,
        positive_appearance: Any,
        state: TargetState,
        cfg: TargetMemoryConfig,
    ) -> None:
        if not cfg.hard_negative_memory_enabled:
            return
        if not cfg.appearance_enabled:
            return
        if state != TargetState.LOCKED:
            return
        if selected_track_id is None:
            return
        if positive_appearance is None:
            return

        max_entries = max(
            1,
            int(cfg.hard_negative_max_entries),
        )
        min_candidate_similarity = float(
            cfg.hard_negative_min_candidate_similarity
        )
        max_positive_similarity = max(
            0.0,
            float(
                cfg.hard_negative_max_positive_similarity
            ),
        )

        by_id = {
            int(candidate.track_id): candidate
            for candidate in candidates
        }

        for score in scores_sorted:
            track_id = int(score.track_id)

            if track_id == int(selected_track_id):
                continue
            if not score.geometry_allows_appearance:
                continue

            geometry = max(
                float(score.distance),
                float(score.iou),
            )
            if geometry < cfg.hard_negative_min_geometry:
                continue

            candidate = by_id.get(track_id)
            if candidate is None:
                continue
            if candidate.appearance is None:
                continue
            if not candidate.appearance_memory_update_eligible:
                continue

            positive_similarity = float(
                score.appearance_raw
            )
            if (
                positive_similarity
                < min_candidate_similarity
            ):
                continue

            if (
                positive_similarity
                > max_positive_similarity
            ):
                continue

            updated = False

            for index, raw_entry in enumerate(
                self._memory
            ):
                memory_appearance = _appearance_of(
                    raw_entry
                )
                similarity = clamp01(
                    cosine_similarity(
                        memory_appearance,
                        candidate.appearance,
                    )
                )

                if similarity < min_candidate_similarity:
                    continue

                updated_appearance = (
                    update_feature_memory(
                        memory_appearance,
                        candidate.appearance,
                        alpha=(
                            cfg
                            .hard_negative_update_alpha
                        ),
                    )
                )
                if updated_appearance is None:
                    continue

                if isinstance(
                    raw_entry,
                    HardNegativeEntry,
                ):
                    source_track_ids = _append_unique(
                        raw_entry.source_track_ids,
                        track_id,
                    )
                    selected_track_ids = _append_unique(
                        raw_entry.selected_track_ids,
                        int(selected_track_id),
                    )
                    observations = (
                        raw_entry.observations + 1
                    )
                else:
                    source_track_ids = (track_id,)
                    selected_track_ids = (
                        int(selected_track_id),
                    )
                    observations = 2

                self._memory[index] = (
                    HardNegativeEntry(
                        appearance=updated_appearance,
                        source_track_ids=(
                            source_track_ids
                        ),
                        selected_track_ids=(
                            selected_track_ids
                        ),
                        source=(
                            "trusted_locked_distractor"
                        ),
                        observations=observations,
                        positive_similarity=(
                            positive_similarity
                        ),
                        geometry_strength=geometry,
                    )
                )
                updated = True
                break

            if not updated:
                prototype = update_feature_memory(
                    None,
                    candidate.appearance,
                    alpha=1.0,
                )
                if prototype is None:
                    continue

                self._memory.append(
                    HardNegativeEntry(
                        appearance=prototype,
                        source_track_ids=(track_id,),
                        selected_track_ids=(
                            int(selected_track_id),
                        ),
                        source=(
                            "trusted_locked_distractor"
                        ),
                        observations=1,
                        positive_similarity=(
                            positive_similarity
                        ),
                        geometry_strength=geometry,
                    )
                )

            if len(self._memory) > max_entries:
                self._memory = (
                    self._memory[-max_entries:]
                )


__all__ = [
    "HardNegativeEntry",
    "HardNegativeMemory",
]
