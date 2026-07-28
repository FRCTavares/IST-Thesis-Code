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
    HardNegativeMemorySnapshot,
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

    first_frame_id: int | None = None
    last_frame_id: int | None = None
    first_timestamp_ns: int | None = None
    last_timestamp_ns: int | None = None

    latest_bbox: tuple[
        float,
        float,
        float,
        float,
    ] | None = None
    latest_confidence: float = 0.0
    latest_crop_quality: Any | None = None

    latest_iou: float = 0.0
    latest_distance: float = 0.0
    latest_scale: float = 0.0
    latest_geometry_score: float = 0.0

    appearance_source_frame_id: int | None = None
    appearance_source_image_timestamp_ns: int | None = None
    appearance_embedded_ns: int | None = None
    appearance_embedding_age_ms: float | None = None
    appearance_frame_generation: int | None = None
    appearance_track_generation: int | None = None
    appearance_source_bbox: tuple[
        float,
        float,
        float,
        float,
    ] | None = None
    appearance_source_crop_quality: Any | None = None


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


def _entry_with_candidate_provenance(
    *,
    appearance: Any,
    candidate: CandidateTrack,
    score: CandidateScore,
    source_track_ids: tuple[int, ...],
    selected_track_ids: tuple[int, ...],
    source: str,
    observations: int,
    positive_similarity: float,
    geometry_strength: float,
    previous: HardNegativeEntry | None = None,
) -> HardNegativeEntry:
    """Build an entry while retaining earliest and latest evidence."""
    provenance = candidate.appearance_provenance

    first_frame_id = (
        previous.first_frame_id
        if (
            previous is not None
            and previous.first_frame_id is not None
        )
        else candidate.tracker_frame_id
    )
    first_timestamp_ns = (
        previous.first_timestamp_ns
        if (
            previous is not None
            and previous.first_timestamp_ns is not None
        )
        else candidate.tracker_timestamp_ns
    )

    last_frame_id = (
        candidate.tracker_frame_id
        if candidate.tracker_frame_id is not None
        else (
            previous.last_frame_id
            if previous is not None
            else None
        )
    )
    last_timestamp_ns = (
        candidate.tracker_timestamp_ns
        if candidate.tracker_timestamp_ns is not None
        else (
            previous.last_timestamp_ns
            if previous is not None
            else None
        )
    )

    latest_crop_quality = (
        candidate.appearance_crop_quality
        if candidate.appearance_crop_quality is not None
        else (
            previous.latest_crop_quality
            if previous is not None
            else None
        )
    )

    def previous_value(name: str):
        if previous is None:
            return None
        return getattr(previous, name)

    return HardNegativeEntry(
        appearance=appearance,
        source_track_ids=source_track_ids,
        selected_track_ids=selected_track_ids,
        source=source,
        observations=int(observations),
        positive_similarity=float(positive_similarity),
        geometry_strength=float(geometry_strength),
        first_frame_id=first_frame_id,
        last_frame_id=last_frame_id,
        first_timestamp_ns=first_timestamp_ns,
        last_timestamp_ns=last_timestamp_ns,
        latest_bbox=candidate.bbox,
        latest_confidence=float(candidate.score),
        latest_crop_quality=latest_crop_quality,
        latest_iou=float(score.iou),
        latest_distance=float(score.distance),
        latest_scale=float(score.scale),
        latest_geometry_score=float(
            score.geometry_score
        ),
        appearance_source_frame_id=(
            provenance.source_frame_id
            if provenance is not None
            else previous_value(
                "appearance_source_frame_id"
            )
        ),
        appearance_source_image_timestamp_ns=(
            provenance.source_image_timestamp_ns
            if provenance is not None
            else previous_value(
                "appearance_source_image_timestamp_ns"
            )
        ),
        appearance_embedded_ns=(
            provenance.embedded_ns
            if provenance is not None
            else previous_value(
                "appearance_embedded_ns"
            )
        ),
        appearance_embedding_age_ms=(
            provenance.embedding_age_ms
            if provenance is not None
            else previous_value(
                "appearance_embedding_age_ms"
            )
        ),
        appearance_frame_generation=(
            provenance.frame_generation
            if provenance is not None
            else previous_value(
                "appearance_frame_generation"
            )
        ),
        appearance_track_generation=(
            provenance.track_generation
            if provenance is not None
            else previous_value(
                "appearance_track_generation"
            )
        ),
        appearance_source_bbox=(
            provenance.source_bbox
            if provenance is not None
            else previous_value(
                "appearance_source_bbox"
            )
        ),
        appearance_source_crop_quality=(
            provenance.source_crop_quality
            if provenance is not None
            else previous_value(
                "appearance_source_crop_quality"
            )
        ),
    )


def _snapshot_for_entry(
    entry: HardNegativeEntry,
    *,
    lifecycle_state: str,
    current_frame_id: int | None,
    max_age_frames: int,
    decay_policy: str,
) -> HardNegativeMemorySnapshot:
    """Return diagnostics without exposing the appearance vector."""
    age_frames = None
    if (
        current_frame_id is not None
        and entry.last_frame_id is not None
    ):
        age_frames = max(
            0,
            int(current_frame_id)
            - int(entry.last_frame_id),
        )

    expires_at_frame_id = None
    if (
        int(max_age_frames) > 0
        and entry.last_frame_id is not None
    ):
        # An entry with age equal to max_age_frames remains valid.
        expires_at_frame_id = (
            int(entry.last_frame_id)
            + int(max_age_frames)
            + 1
        )

    expired = bool(
        int(max_age_frames) > 0
        and age_frames is not None
        and int(age_frames) > int(max_age_frames)
    )

    return HardNegativeMemorySnapshot(
        lifecycle_state=str(lifecycle_state),
        source=str(entry.source),
        source_track_ids=entry.source_track_ids,
        selected_track_ids=entry.selected_track_ids,
        observations=int(entry.observations),
        first_frame_id=entry.first_frame_id,
        last_frame_id=entry.last_frame_id,
        first_timestamp_ns=entry.first_timestamp_ns,
        last_timestamp_ns=entry.last_timestamp_ns,
        age_frames=age_frames,
        expires_at_frame_id=expires_at_frame_id,
        expired=expired,
        latest_bbox=entry.latest_bbox,
        latest_confidence=float(
            entry.latest_confidence
        ),
        latest_crop_quality=entry.latest_crop_quality,
        positive_similarity=float(
            entry.positive_similarity
        ),
        geometry_strength=float(
            entry.geometry_strength
        ),
        latest_iou=float(entry.latest_iou),
        latest_distance=float(entry.latest_distance),
        latest_scale=float(entry.latest_scale),
        latest_geometry_score=float(
            entry.latest_geometry_score
        ),
        appearance_source_frame_id=(
            entry.appearance_source_frame_id
        ),
        appearance_source_image_timestamp_ns=(
            entry
            .appearance_source_image_timestamp_ns
        ),
        appearance_embedded_ns=(
            entry.appearance_embedded_ns
        ),
        appearance_embedding_age_ms=(
            entry.appearance_embedding_age_ms
        ),
        appearance_frame_generation=(
            entry.appearance_frame_generation
        ),
        appearance_track_generation=(
            entry.appearance_track_generation
        ),
        appearance_source_bbox=(
            entry.appearance_source_bbox
        ),
        appearance_source_crop_quality=(
            entry.appearance_source_crop_quality
        ),
        max_age_frames=max(
            0,
            int(max_age_frames),
        ),
        decay_policy=str(decay_policy),
    )


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

    def snapshots(
        self,
        *,
        current_frame_id: int | None,
        max_age_frames: int,
        decay_policy: str,
        pending: bool = False,
    ) -> tuple[HardNegativeMemorySnapshot, ...]:
        """Return committed or pending prototype diagnostics."""
        entries = (
            self.pending_entries
            if pending
            else self.entries
        )
        lifecycle_state = (
            "pending"
            if pending
            else "committed"
        )

        return tuple(
            _snapshot_for_entry(
                entry,
                lifecycle_state=lifecycle_state,
                current_frame_id=current_frame_id,
                max_age_frames=max_age_frames,
                decay_policy=decay_policy,
            )
            for entry in entries
        )

    def expire_committed(
        self,
        *,
        current_frame_id: int | None,
        max_age_frames: int,
        decay_policy: str,
        selected_track_id: int | None = None,
    ) -> tuple[HardNegativeMemoryEvent, ...]:
        """Atomically remove over-age committed prototypes.

        Expiry is intentionally separate from scoring and candidate
        preparation. The caller may invoke it only after trusted current-frame
        identity acceptance. Embeddings retain full rejection strength until
        removal; no vector or similarity decay is applied.
        """
        policy = str(decay_policy)
        if policy != "none_until_expiry":
            raise ValueError(
                "Unsupported hard-negative decay policy: "
                f"{policy}"
            )

        maximum_age = max(0, int(max_age_frames))
        if maximum_age == 0 or current_frame_id is None:
            return ()

        current_frame = int(current_frame_id)
        retained = []
        expired = []

        for raw_entry in self._memory:
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

            # Legacy entries and direct tests without timeline provenance
            # cannot be expired safely by frame age.
            if entry.last_frame_id is None:
                retained.append(raw_entry)
                continue

            age_frames = max(
                0,
                current_frame - int(entry.last_frame_id),
            )
            if age_frames <= maximum_age:
                retained.append(raw_entry)
                continue

            snapshot = _snapshot_for_entry(
                entry,
                lifecycle_state="expired",
                current_frame_id=current_frame,
                max_age_frames=maximum_age,
                decay_policy=policy,
            )
            expired.append((entry, snapshot))

        if not expired:
            return ()

        self._memory = retained
        memory_size = len(self._memory)

        return tuple(
            HardNegativeMemoryEvent(
                action="expire",
                source=entry.source,
                selected_track_id=selected_track_id,
                source_track_ids=entry.source_track_ids,
                selected_track_ids=entry.selected_track_ids,
                observations=entry.observations,
                positive_similarity=(
                    entry.positive_similarity
                ),
                geometry_strength=entry.geometry_strength,
                memory_size=memory_size,
                snapshot=snapshot,
            )
            for entry, snapshot in expired
        )

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

                entry = _entry_with_candidate_provenance(
                    appearance=updated_appearance,
                    candidate=candidate,
                    score=score,
                    source_track_ids=source_track_ids,
                    selected_track_ids=selected_track_ids,
                    source="trusted_locked_distractor",
                    observations=observations,
                    positive_similarity=positive_similarity,
                    geometry_strength=geometry,
                    previous=(
                        raw_entry
                        if isinstance(
                            raw_entry,
                            HardNegativeEntry,
                        )
                        else None
                    ),
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
                    entry = _entry_with_candidate_provenance(
                        appearance=updated_appearance,
                        candidate=candidate,
                        score=score,
                        source_track_ids=source_track_ids,
                        selected_track_ids=selected_track_ids,
                        source="trusted_locked_distractor",
                        observations=observations,
                        positive_similarity=positive_similarity,
                        geometry_strength=geometry,
                        previous=pending_entry,
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
                    entry = _entry_with_candidate_provenance(
                        appearance=updated_appearance,
                        candidate=candidate,
                        score=score,
                        source_track_ids=source_track_ids,
                        selected_track_ids=selected_track_ids,
                        source=(
                            "trusted_locked_distractor_pending"
                        ),
                        observations=observations,
                        positive_similarity=positive_similarity,
                        geometry_strength=geometry,
                        previous=pending_entry,
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
                    entry = _entry_with_candidate_provenance(
                        appearance=prototype,
                        candidate=candidate,
                        score=score,
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
                    entry = _entry_with_candidate_provenance(
                        appearance=prototype,
                        candidate=candidate,
                        score=score,
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
