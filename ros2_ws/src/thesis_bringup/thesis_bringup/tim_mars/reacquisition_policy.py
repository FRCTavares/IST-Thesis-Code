"""Reacquisition and ambiguity policy helpers for TIM-MARS.

This module starts with stateless helpers only. Stateful confirmation counters
remain in target_memory.py until behavior is fully locked down by tests.
"""

from __future__ import annotations

from typing import List, Optional

from thesis_bringup.tim_mars.types import CandidateScore, TargetMemoryConfig, TargetState


def appearance_margin(selected: CandidateScore, scores_sorted: List[CandidateScore]) -> float:
    """Return selected appearance margin over other plausible candidates."""

    other_apps = [
        float(s.appearance_raw)
        for s in scores_sorted
        if int(s.track_id) != int(selected.track_id) and s.geometry_allows_appearance
    ]
    return float(selected.appearance_raw) - max(other_apps, default=0.0)


def geometry_strength(score: Optional[CandidateScore]) -> float:
    """Return strongest geometric cue in a candidate score."""

    if score is None:
        return 0.0
    return max(float(score.iou), float(score.distance), float(score.scale))


def scene_ambiguity_risk(
    *,
    best: Optional[CandidateScore],
    scores_sorted: List[CandidateScore],
    cfg: TargetMemoryConfig,
) -> bool:
    """Return whether the scene is risky due to close competing evidence."""

    if best is None:
        return False
    if bool(best.ambiguous):
        return True
    if not best.geometry_allows_appearance:
        return False

    app_margin = appearance_margin(best, scores_sorted)
    return (
        best.appearance_raw >= cfg.appearance_conservative_min_similarity
        and app_margin < cfg.appearance_conservative_margin
    )


def absence_risk(
    *,
    state: TargetState,
    frames_since_seen: int,
    cfg: TargetMemoryConfig,
) -> bool:
    """Return whether TIM is in the configured absence-risk window."""

    if not cfg.absence_recovery_enabled:
        return False
    return (
        state in {TargetState.UNCERTAIN, TargetState.LOST}
        and frames_since_seen >= max(1, int(cfg.absence_after_missed_frames))
    )


__all__ = [
    "absence_risk",
    "appearance_margin",
    "geometry_strength",
    "scene_ambiguity_risk",
]
