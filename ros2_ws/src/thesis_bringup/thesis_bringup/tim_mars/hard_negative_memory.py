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
    HardNegativeMemoryEvent,
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


def _positive_exclusion_similarity(
    score: CandidateScore,
    cfg: TargetMemoryConfig,
) -> float:
    """Return trusted positive support used to block negative admission.

    Protected mode excludes target-like candidates using the immutable
    operator anchor and trusted gallery. The adaptive prototype is deliberately
    not allowed to weaken that protection. Legacy mode retains the previous
    appearance-score behaviour.
    """
    fallback = max(
        float(score.positive_similarity),
        float(score.appearance_raw),
    )

    if not cfg.appearance_protected_memory_enabled:
        return fallback

    protected_similarity = max(
        float(score.protected_anchor_similarity),
        float(score.trusted_gallery_similarity),
    )

    if protected_similarity > 0.0:
        return protected_similarity

    return fallback


class HardNegativeMemory:
    """Small bounded memory of distractor appearance prototypes."""

    def __init__(self) -> None:
        self._memory: List[Any] = []
        self._pending: List[HardNegativeEntry] = []

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

    @property
    def pending_entries(self) -> tuple[HardNegativeEntry, ...]:
        """Return staged evidence that cannot reject candidates yet."""
        return tuple(self._pending)

    def clear(self) -> None:
        self._memory = []
        self._pending = []

    def discard_pending(
        self,
        *,
        selected_track_id: int | None = None,
    ) -> tuple[HardNegativeMemoryEvent, ...]:
        """Expire staged evidence after trusted continuity is broken."""
        memory_size = len(self._memory)
        events = tuple(
            HardNegativeMemoryEvent(
                action="expire_pending",
                source=entry.source,
                selected_track_id=selected_track_id,
                source_track_ids=entry.source_track_ids,
                selected_track_ids=entry.selected_track_ids,
                observations=entry.observations,
                positive_similarity=entry.positive_similarity,
                geometry_strength=entry.geometry_strength,
                memory_size=memory_size,
            )
            for entry in self._pending
        )
        self._pending = []
        return events

    def reconcile_selected(
        self,
        appearance: Any,
        cfg: TargetMemoryConfig,
        *,
        selected_track_id: int | None = None,
    ) -> tuple[HardNegativeMemoryEvent, ...]:
        """Remove negative evidence incompatible with a selected identity."""
        if appearance is None:
            return ()

        threshold = float(
            cfg.hard_negative_min_candidate_similarity
        )
        retained = []
        removed = []

        for raw_entry in self._memory:
            similarity = clamp01(
                cosine_similarity(
                    _appearance_of(raw_entry),
                    appearance,
                )
            )

            if similarity < threshold:
                retained.append(raw_entry)
                continue

            if isinstance(raw_entry, HardNegativeEntry):
                entry = raw_entry
            else:
                entry = HardNegativeEntry(
                    appearance=raw_entry,
                    source_track_ids=(),
                    selected_track_ids=(),
                    source="legacy_unattributed",
                    observations=1,
                    positive_similarity=0.0,
                    geometry_strength=0.0,
                )

            removed.append((entry, similarity))

        self._memory = retained
        memory_size = len(self._memory)
        events = [
            HardNegativeMemoryEvent(
                action="reconcile",
                source=entry.source,
                selected_track_id=selected_track_id,
                source_track_ids=entry.source_track_ids,
                selected_track_ids=entry.selected_track_ids,
                observations=entry.observations,
                positive_similarity=entry.positive_similarity,
                geometry_strength=entry.geometry_strength,
                prototype_similarity=similarity,
                memory_size=memory_size,
            )
            for entry, similarity in removed
        ]

        pending_retained = []
        for entry in self._pending:
            similarity = clamp01(
                cosine_similarity(
                    entry.appearance,
                    appearance,
                )
            )
            same_lineage = (
                selected_track_id is None
                or int(selected_track_id)
                in entry.selected_track_ids
            )

            if same_lineage and similarity < threshold:
                pending_retained.append(entry)
                continue

            events.append(
                HardNegativeMemoryEvent(
                    action="discard_pending",
                    source=entry.source,
                    selected_track_id=selected_track_id,
                    source_track_ids=entry.source_track_ids,
                    selected_track_ids=entry.selected_track_ids,
                    observations=entry.observations,
                    positive_similarity=entry.positive_similarity,
                    geometry_strength=entry.geometry_strength,
                    prototype_similarity=similarity,
                    memory_size=memory_size,
                )
            )

        self._pending = pending_retained
        return tuple(events)

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
    ) -> tuple[HardNegativeMemoryEvent, ...]:
        if not cfg.hard_negative_memory_enabled:
            return ()
        if not cfg.appearance_enabled:
            return ()
        if state != TargetState.LOCKED:
            return ()
        if selected_track_id is None:
            return ()
        if positive_appearance is None:
            return ()

        events = []
        max_entries = max(
            1,
            int(cfg.hard_negative_max_entries),
        )
        required_observations = max(
            1,
            int(cfg.hard_negative_confirm_observations),
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
        pending_snapshot = list(self._pending)
        pending_touched = set()
        pending_updates = {}
        pending_promoted = set()
        pending_new = []

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

            positive_similarity = (
                _positive_exclusion_similarity(
                    score,
                    cfg,
                )
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

                entry = HardNegativeEntry(
                    appearance=updated_appearance,
                    source_track_ids=source_track_ids,
                    selected_track_ids=selected_track_ids,
                    source="trusted_locked_distractor",
                    observations=observations,
                    positive_similarity=positive_similarity,
                    geometry_strength=geometry,
                )
                self._memory[index] = entry
                events.append(
                    HardNegativeMemoryEvent(
                        action="merge",
                        source=entry.source,
                        source_track_id=track_id,
                        selected_track_id=int(selected_track_id),
                        source_track_ids=entry.source_track_ids,
                        selected_track_ids=entry.selected_track_ids,
                        observations=entry.observations,
                        positive_similarity=entry.positive_similarity,
                        geometry_strength=entry.geometry_strength,
                        prototype_similarity=similarity,
                        memory_size=len(self._memory),
                    )
                )
                updated = True
                break

            if updated:
                continue

            pending_index = None
            pending_similarity = 0.0
            for index, pending_entry in enumerate(
                pending_snapshot
            ):
                if index in pending_touched:
                    continue
                if (
                    int(selected_track_id)
                    not in pending_entry.selected_track_ids
                ):
                    continue

                similarity = clamp01(
                    cosine_similarity(
                        pending_entry.appearance,
                        candidate.appearance,
                    )
                )
                if similarity < min_candidate_similarity:
                    continue

                pending_index = index
                pending_similarity = similarity
                break

            if pending_index is not None:
                pending_entry = pending_snapshot[
                    pending_index
                ]
                updated_appearance = (
                    update_feature_memory(
                        pending_entry.appearance,
                        candidate.appearance,
                        alpha=(
                            cfg
                            .hard_negative_update_alpha
                        ),
                    )
                )
                if updated_appearance is None:
                    continue

                observations = (
                    pending_entry.observations + 1
                )
                source_track_ids = _append_unique(
                    pending_entry.source_track_ids,
                    track_id,
                )
                selected_track_ids = _append_unique(
                    pending_entry.selected_track_ids,
                    int(selected_track_id),
                )
                pending_touched.add(pending_index)

                if observations >= required_observations:
                    entry = HardNegativeEntry(
                        appearance=updated_appearance,
                        source_track_ids=source_track_ids,
                        selected_track_ids=selected_track_ids,
                        source="trusted_locked_distractor",
                        observations=observations,
                        positive_similarity=positive_similarity,
                        geometry_strength=geometry,
                    )
                    self._memory.append(entry)
                    pending_promoted.add(pending_index)
                    events.append(
                        HardNegativeMemoryEvent(
                            action="insert",
                            source=entry.source,
                            source_track_id=track_id,
                            selected_track_id=int(selected_track_id),
                            source_track_ids=entry.source_track_ids,
                            selected_track_ids=entry.selected_track_ids,
                            observations=entry.observations,
                            positive_similarity=entry.positive_similarity,
                            geometry_strength=entry.geometry_strength,
                            prototype_similarity=(
                                pending_similarity
                            ),
                            memory_size=min(
                                len(self._memory),
                                max_entries,
                            ),
                        )
                    )
                else:
                    entry = HardNegativeEntry(
                        appearance=updated_appearance,
                        source_track_ids=source_track_ids,
                        selected_track_ids=selected_track_ids,
                        source=(
                            "trusted_locked_distractor_pending"
                        ),
                        observations=observations,
                        positive_similarity=positive_similarity,
                        geometry_strength=geometry,
                    )
                    pending_updates[pending_index] = entry
                    events.append(
                        HardNegativeMemoryEvent(
                            action="stage",
                            source=entry.source,
                            source_track_id=track_id,
                            selected_track_id=int(selected_track_id),
                            source_track_ids=entry.source_track_ids,
                            selected_track_ids=entry.selected_track_ids,
                            observations=entry.observations,
                            positive_similarity=entry.positive_similarity,
                            geometry_strength=entry.geometry_strength,
                            prototype_similarity=(
                                pending_similarity
                            ),
                            memory_size=len(self._memory),
                        )
                    )
            else:
                prototype = update_feature_memory(
                    None,
                    candidate.appearance,
                    alpha=1.0,
                )
                if prototype is None:
                    continue

                if required_observations <= 1:
                    entry = HardNegativeEntry(
                        appearance=prototype,
                        source_track_ids=(track_id,),
                        selected_track_ids=(
                            int(selected_track_id),
                        ),
                        source="trusted_locked_distractor",
                        observations=1,
                        positive_similarity=positive_similarity,
                        geometry_strength=geometry,
                    )
                    self._memory.append(entry)
                    events.append(
                        HardNegativeMemoryEvent(
                            action="insert",
                            source=entry.source,
                            source_track_id=track_id,
                            selected_track_id=int(selected_track_id),
                            source_track_ids=entry.source_track_ids,
                            selected_track_ids=entry.selected_track_ids,
                            observations=entry.observations,
                            positive_similarity=entry.positive_similarity,
                            geometry_strength=entry.geometry_strength,
                            memory_size=min(
                                len(self._memory),
                                max_entries,
                            ),
                        )
                    )
                else:
                    entry = HardNegativeEntry(
                        appearance=prototype,
                        source_track_ids=(track_id,),
                        selected_track_ids=(
                            int(selected_track_id),
                        ),
                        source=(
                            "trusted_locked_distractor_pending"
                        ),
                        observations=1,
                        positive_similarity=positive_similarity,
                        geometry_strength=geometry,
                    )
                    pending_new.append(entry)
                    events.append(
                        HardNegativeMemoryEvent(
                            action="stage",
                            source=entry.source,
                            source_track_id=track_id,
                            selected_track_id=int(selected_track_id),
                            source_track_ids=entry.source_track_ids,
                            selected_track_ids=entry.selected_track_ids,
                            observations=entry.observations,
                            positive_similarity=entry.positive_similarity,
                            geometry_strength=entry.geometry_strength,
                            memory_size=len(self._memory),
                        )
                    )

            if len(self._memory) > max_entries:
                evicted_entries = (
                    self._memory[:-max_entries]
                )
                self._memory = (
                    self._memory[-max_entries:]
                )
                memory_size = len(self._memory)

                for raw_entry in evicted_entries:
                    if isinstance(
                        raw_entry,
                        HardNegativeEntry,
                    ):
                        entry = raw_entry
                    else:
                        entry = HardNegativeEntry(
                            appearance=raw_entry,
                            source_track_ids=(),
                            selected_track_ids=(),
                            source=(
                                "legacy_unattributed"
                            ),
                            observations=1,
                            positive_similarity=0.0,
                            geometry_strength=0.0,
                        )

                    events.append(
                        HardNegativeMemoryEvent(
                            action="evict",
                            source=entry.source,
                            selected_track_id=int(selected_track_id),
                            source_track_ids=entry.source_track_ids,
                            selected_track_ids=entry.selected_track_ids,
                            observations=entry.observations,
                            positive_similarity=(
                                entry.positive_similarity
                            ),
                            geometry_strength=(
                                entry.geometry_strength
                            ),
                            memory_size=memory_size,
                        )
                    )

        retained_pending = []
        for index, entry in enumerate(
            pending_snapshot
        ):
            if index in pending_promoted:
                continue
            if index not in pending_touched:
                events.append(
                    HardNegativeMemoryEvent(
                        action="expire_pending",
                        source=entry.source,
                        selected_track_id=int(selected_track_id),
                        source_track_ids=entry.source_track_ids,
                        selected_track_ids=entry.selected_track_ids,
                        observations=entry.observations,
                        positive_similarity=entry.positive_similarity,
                        geometry_strength=entry.geometry_strength,
                        memory_size=len(self._memory),
                    )
                )
                continue
            retained_pending.append(
                pending_updates[index]
            )
        retained_pending.extend(pending_new)

        deduplicated_pending = []
        for entry in retained_pending:
            prototype_similarity = 0.0
            if self._memory:
                prototype_similarity = max(
                    clamp01(
                        cosine_similarity(
                            _appearance_of(memory_entry),
                            entry.appearance,
                        )
                    )
                    for memory_entry in self._memory
                )

            if (
                self._memory
                and prototype_similarity
                >= min_candidate_similarity
            ):
                events.append(
                    HardNegativeMemoryEvent(
                        action="discard_pending",
                        source=entry.source,
                        selected_track_id=int(selected_track_id),
                        source_track_ids=entry.source_track_ids,
                        selected_track_ids=entry.selected_track_ids,
                        observations=entry.observations,
                        positive_similarity=entry.positive_similarity,
                        geometry_strength=entry.geometry_strength,
                        prototype_similarity=(
                            prototype_similarity
                        ),
                        memory_size=len(self._memory),
                    )
                )
                continue

            deduplicated_pending.append(entry)

        if len(deduplicated_pending) > max_entries:
            evicted_pending = (
                deduplicated_pending[:-max_entries]
            )
            deduplicated_pending = (
                deduplicated_pending[-max_entries:]
            )
            for entry in evicted_pending:
                events.append(
                    HardNegativeMemoryEvent(
                        action="evict_pending",
                        source=entry.source,
                        selected_track_id=int(selected_track_id),
                        source_track_ids=entry.source_track_ids,
                        selected_track_ids=entry.selected_track_ids,
                        observations=entry.observations,
                        positive_similarity=entry.positive_similarity,
                        geometry_strength=entry.geometry_strength,
                        memory_size=len(self._memory),
                    )
                )

        self._pending = deduplicated_pending
        return tuple(events)


__all__ = [
    "HardNegativeEntry",
    "HardNegativeMemory",
]
