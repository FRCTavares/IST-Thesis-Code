"""Appearance scoring policy for TIM-MARS.

This module keeps MARS appearance score decisions separate from the target
memory state machine. It does not own target memory state; it only enriches a
geometric CandidateScore with positive-appearance and hard-negative evidence.
"""

from __future__ import annotations

from typing import Any

from thesis_bringup.tim_mars.appearance_memory import cosine_similarity
from thesis_bringup.tim_mars.geometry_scoring import clamp01
from thesis_bringup.tim_mars.hard_negative_memory import HardNegativeMemory
from thesis_bringup.tim_mars.types import CandidateScore, CandidateTrack, TargetMemoryConfig


def geometry_allows_appearance(score: CandidateScore) -> bool:
    """Return whether geometry is plausible enough to consult appearance."""

    return bool(
        score.iou > 0.0
        or (score.distance >= 0.25 and score.scale >= 0.35)
    )


def should_use_appearance(
    *,
    cfg: TargetMemoryConfig,
    positive_appearance: Any,
    state_is_lostish: bool,
    base_ambiguous: bool,
) -> bool:
    """Return whether positive appearance should affect candidate scoring."""

    if not cfg.appearance_enabled:
        return False
    if positive_appearance is None:
        return False
    if state_is_lostish:
        return True
    if not cfg.appearance_ambiguous_only:
        return True
    return bool(base_ambiguous)


def score_with_appearance(
    *,
    base: CandidateScore,
    candidate: CandidateTrack,
    positive_appearance: Any,
    use_appearance: bool,
    hard_negative_memory: HardNegativeMemory,
    cfg: TargetMemoryConfig,
) -> CandidateScore:
    """Return a copy of base score enriched with appearance diagnostics."""

    appearance_score = 0.0
    appearance_raw = 0.0
    appearance_used = False
    appearance_gate_passed = False
    hard_negative_similarity = 0.0
    hard_negative_margin = 1.0
    hard_negative_reject = False
    total = base.total

    allows_appearance = geometry_allows_appearance(base)

    if candidate.appearance is not None and allows_appearance:
        if positive_appearance is not None:
            appearance_raw = clamp01(cosine_similarity(positive_appearance, candidate.appearance))

            if use_appearance and appearance_raw >= cfg.appearance_min_similarity:
                appearance_score = appearance_raw
                appearance_gate_passed = True
                total = clamp01(total + cfg.appearance_weight * appearance_score)
                appearance_used = True

        hard_negative_similarity = hard_negative_memory.similarity(candidate.appearance, cfg)
        hard_negative_margin = float(appearance_raw) - float(hard_negative_similarity)
        hard_negative_reject = (
            cfg.hard_negative_memory_enabled
            and hard_negative_similarity >= cfg.hard_negative_reject_similarity
            and hard_negative_margin < cfg.hard_negative_reject_margin
        )

    return CandidateScore(
        track_id=base.track_id,
        total=total,
        iou=base.iou,
        distance=base.distance,
        scale=base.scale,
        confidence=base.confidence,
        id_bonus=base.id_bonus,
        appearance=appearance_score,
        appearance_used=appearance_used,
        appearance_raw=appearance_raw,
        appearance_gate_passed=appearance_gate_passed,
        geometry_allows_appearance=allows_appearance,
        hard_negative_similarity=hard_negative_similarity,
        hard_negative_margin=hard_negative_margin,
        hard_negative_reject=hard_negative_reject,
        ambiguous=base.ambiguous,
    )


__all__ = [
    "geometry_allows_appearance",
    "score_with_appearance",
    "should_use_appearance",
]
