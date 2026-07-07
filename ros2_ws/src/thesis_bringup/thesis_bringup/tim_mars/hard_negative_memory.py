"""Hard-negative appearance memory for TIM-MARS.

Hard negatives are bounded appearance prototypes of nearby non-selected tracks
observed while TIM-MARS is confidently locked on the selected target. They help
suppress recovery to distractors that look similar to the positive target.

This module owns only the hard-negative prototype store, update policy, and
rejection score helper. The final reject decision is made in target_memory.py.
"""

from __future__ import annotations

from typing import Any, List, Sequence

from thesis_bringup.tim_mars.appearance_memory import cosine_similarity, update_feature_memory
from thesis_bringup.tim_mars.geometry_scoring import clamp01
from thesis_bringup.tim_mars.types import CandidateScore, CandidateTrack, TargetMemoryConfig, TargetState


class HardNegativeMemory:
    """Small bounded memory of distractor appearance prototypes."""

    def __init__(self) -> None:
        self._memory: List[Any] = []

    def __len__(self) -> int:
        """Return number of stored hard-negative prototypes.

        This keeps debug/tests compatible with the previous list-backed memory.
        """
        return len(self._memory)

    def clear(self) -> None:
        self._memory = []

    def similarity(self, appearance: Any, cfg: TargetMemoryConfig) -> float:
        if not cfg.hard_negative_memory_enabled:
            return 0.0
        if appearance is None or not self._memory:
            return 0.0
        return max(
            clamp01(cosine_similarity(memory, appearance))
            for memory in self._memory
        )

    def should_reject(self, best: CandidateScore, cfg: TargetMemoryConfig) -> bool:
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
        if selected_track_id is None or positive_appearance is None:
            return

        max_entries = max(1, int(cfg.hard_negative_max_entries))
        by_id = {int(c.track_id): c for c in candidates}

        for score in scores_sorted:
            track_id = int(score.track_id)
            if track_id == int(selected_track_id):
                continue

            if not score.geometry_allows_appearance:
                continue

            if max(score.distance, score.iou) < cfg.hard_negative_min_geometry:
                continue

            candidate = by_id.get(track_id)
            if candidate is None or candidate.appearance is None:
                continue

            if score.appearance_raw < cfg.hard_negative_min_candidate_similarity:
                continue

            updated = False
            for i, memory in enumerate(self._memory):
                sim = clamp01(cosine_similarity(memory, candidate.appearance))
                if sim >= cfg.hard_negative_min_candidate_similarity:
                    self._memory[i] = update_feature_memory(
                        memory,
                        candidate.appearance,
                        alpha=cfg.hard_negative_update_alpha,
                    )
                    updated = True
                    break

            if not updated:
                self._memory.append(candidate.appearance)

            if len(self._memory) > max_entries:
                self._memory = self._memory[-max_entries:]


__all__ = ["HardNegativeMemory"]
