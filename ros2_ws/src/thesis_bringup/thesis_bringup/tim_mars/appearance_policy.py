"""Appearance scoring policy for TIM-MARS.

This module decides how optional appearance evidence modifies a geometric
CandidateScore. It applies positive target-memory similarity, hard-negative
similarity, and appearance gating rules.

It does not own target memory state or ROS messages. The selected-target state
machine calls these helpers from target_memory.py.
"""

from __future__ import annotations

from typing import Any

from thesis_bringup.tim_mars.appearance_memory import cosine_similarity
from thesis_bringup.tim_mars.geometry_scoring import clamp01
from thesis_bringup.tim_mars.hard_negative_memory import HardNegativeMemory
from thesis_bringup.tim_mars.positive_appearance_memory import (
    PositiveAppearanceMemory,
)
from thesis_bringup.tim_mars.types import (
    CandidateScore,
    CandidateTrack,
    TargetMemoryConfig,
)


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
    positive_memory: PositiveAppearanceMemory | None = None,
    protected_only: bool = False,
) -> CandidateScore:
    """Return a base score enriched with appearance evidence."""
    appearance_score = 0.0
    appearance_raw = 0.0
    appearance_used = False
    appearance_gate_passed = False

    protected_anchor_similarity = 0.0
    trusted_gallery_similarity = 0.0
    adaptive_similarity = 0.0
    positive_similarity = 0.0
    positive_support_source = "none"

    hard_negative_similarity = 0.0
    hard_negative_margin = 1.0
    hard_negative_reject = False
    total = base.total

    allows_appearance = geometry_allows_appearance(base)

    if candidate.appearance is not None and allows_appearance:
        if positive_memory is not None:
            (
                positive_similarity,
                positive_support_source,
                protected_anchor_similarity,
                trusted_gallery_similarity,
                adaptive_similarity,
            ) = positive_memory.effective_similarity(
                appearance=candidate.appearance,
                protected_only=protected_only,
            )
            appearance_raw = positive_similarity
        elif positive_appearance is not None:
            appearance_raw = clamp01(
                cosine_similarity(
                    positive_appearance,
                    candidate.appearance,
                )
            )
            positive_similarity = appearance_raw
            positive_support_source = (
                "legacy_positive_memory"
                if appearance_raw > 0.0
                else "none"
            )

        if (
            use_appearance
            and appearance_raw
            >= cfg.appearance_min_similarity
        ):
            appearance_score = appearance_raw
            appearance_gate_passed = True
            total = clamp01(
                total
                + cfg.appearance_weight
                * appearance_score
            )
            appearance_used = True

        hard_negative_similarity = (
            hard_negative_memory.similarity(
                candidate.appearance,
                cfg,
            )
        )
        hard_negative_margin = (
            float(appearance_raw)
            - float(hard_negative_similarity)
        )
        hard_negative_reject = (
            cfg.hard_negative_memory_enabled
            and hard_negative_similarity
            >= cfg.hard_negative_reject_similarity
            and hard_negative_margin
            < cfg.hard_negative_reject_margin
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
        protected_anchor_similarity=(
            protected_anchor_similarity
        ),
        trusted_gallery_similarity=(
            trusted_gallery_similarity
        ),
        adaptive_similarity=adaptive_similarity,
        positive_similarity=positive_similarity,
        positive_support_source=(
            positive_support_source
        ),
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
