"""Reacquisition and ambiguity helper policies for TIM-MARS.

This module contains small confirmation counters and stateless helper functions
used when the selected target is uncertain, lost, or being reacquired.

The helpers support candidate-belief confirmation, absence-aware recovery,
appearance-margin checks, geometry-strength checks, and scene-ambiguity risk.
The main state transition logic remains in target_memory.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from thesis_bringup.tim_mars.types import (
    BBox,
    CandidateScore,
    TargetMemoryConfig,
    TargetState,
)


@dataclass
class CandidatePersistenceTracker:
    """Track one probationary candidate outside trusted selected memory."""

    candidate_id: Optional[int] = None
    observation_count: int = 0
    required_observations: int = 0
    source: str = ""
    bbox: Optional[BBox] = None
    score: float = 0.0
    identity_evidence_confirmed: bool = False

    # AB-19 development-only: the appearance source-image observation
    # (source_image_timestamp_ns / source_frame_id) that last advanced the
    # persistence count. When distinct-source persistence is required, a
    # repeated source-image observation does not advance the count.
    last_advancing_source: Optional[tuple] = None

    @property
    def pending(self) -> bool:
        return self.candidate_id is not None

    @property
    def confirmed(self) -> bool:
        return bool(
            self.pending
            and self.observation_count
            >= max(1, self.required_observations)
        )

    def reset(self) -> None:
        self.candidate_id = None
        self.observation_count = 0
        self.required_observations = 0
        self.source = ""
        self.bbox = None
        self.score = 0.0
        self.identity_evidence_confirmed = False
        self.last_advancing_source = None

    def _repeated_source(
        self,
        track_id: int,
        *,
        source_observation: Optional[tuple],
        require_distinct_source: bool,
    ) -> bool:
        return bool(
            require_distinct_source
            and self.candidate_id == int(track_id)
            and source_observation is not None
            and source_observation == self.last_advancing_source
        )

    def preview(
        self,
        track_id: int,
        *,
        source_observation: Optional[tuple] = None,
        require_distinct_source: bool = False,
    ) -> int:
        """Return the next observation count without mutating state."""
        if self.candidate_id == int(track_id):
            if self._repeated_source(
                track_id,
                source_observation=source_observation,
                require_distinct_source=require_distinct_source,
            ):
                # AB-19: a repeated source image is not fresh evidence.
                return self.observation_count
            return self.observation_count + 1
        return 1

    @property
    def confirm_count(self) -> int:
        """Compatibility name while old call sites are migrated."""
        return self.observation_count

    @confirm_count.setter
    def confirm_count(self, value: int) -> None:
        self.observation_count = int(value)

    def observe(
        self,
        track_id: int,
        *,
        required_observations: int = 1,
        source: str = "",
        bbox: Optional[BBox] = None,
        score: float = 0.0,
        identity_evidence_confirmed: bool = False,
        source_observation: Optional[tuple] = None,
        require_distinct_source: bool = False,
    ) -> int:
        """Commit one gate-approved observation."""
        same_candidate = bool(
            self.candidate_id == int(track_id)
        )
        repeated_source = self._repeated_source(
            track_id,
            source_observation=source_observation,
            require_distinct_source=require_distinct_source,
        )
        retained_identity_evidence = bool(
            identity_evidence_confirmed
            or (
                same_candidate
                and self.identity_evidence_confirmed
            )
        )
        next_count = self.preview(
            track_id,
            source_observation=source_observation,
            require_distinct_source=require_distinct_source,
        )

        self.candidate_id = int(track_id)
        self.observation_count = next_count
        self.required_observations = max(
            1,
            int(required_observations),
        )
        self.source = str(source)
        self.bbox = bbox
        self.score = float(score)
        self.identity_evidence_confirmed = (
            retained_identity_evidence
        )
        if not repeated_source:
            self.last_advancing_source = source_observation

        return next_count


# Compatibility aliases preserve the current imports while target_memory.py
# is migrated from three policy-specific instances to one persistence tracker.
CandidateBeliefConfirmation = CandidatePersistenceTracker
AbsenceRecoveryConfirmation = CandidatePersistenceTracker
RankAwareReacquisitionConfirmation = CandidatePersistenceTracker


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
    "CandidatePersistenceTracker",
    "AbsenceRecoveryConfirmation",
    "CandidateBeliefConfirmation",
    "RankAwareReacquisitionConfirmation",
    "absence_risk",
    "appearance_margin",
    "geometry_strength",
    "scene_ambiguity_risk",
]
