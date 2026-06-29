"""Shared TIM-MARS data types.

This module contains only type aliases, enums, and dataclasses shared across the
TIM-MARS implementation. Keeping these definitions outside target_memory.py
allows scoring, appearance, and reacquisition policies to be split without
creating circular imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional, Tuple

BBox = Tuple[float, float, float, float]


class TargetState(str, Enum):
    """Finite states exposed by the selected-target memory."""

    NO_TARGET = "NO_TARGET"
    LOCKED = "LOCKED"
    UNCERTAIN = "UNCERTAIN"
    LOST = "LOST"
    REACQUIRED = "REACQUIRED"


class ControlMode(str, Enum):
    """Control policy suggestion derived from target-memory state."""

    NO_CONTROL = "NO_CONTROL"
    NORMAL = "NORMAL"
    YAW_ONLY = "YAW_ONLY"
    HOVER = "HOVER"
    CONFIRM = "CONFIRM"


@dataclass(frozen=True)
class CandidateTrack:
    """Minimal tracker output consumed by TIM.

    This deliberately avoids ROS message types so the same code can be tested
    offline and then used inside a ROS node wrapper.
    """

    track_id: int
    bbox: BBox
    score: float = 1.0
    age: int = 0
    last_seen: int = 0
    appearance: Optional[Any] = None


@dataclass(frozen=True)
class CandidateScore:
    track_id: int
    total: float
    iou: float
    distance: float
    scale: float
    confidence: float
    id_bonus: float
    appearance: float = 0.0
    appearance_used: bool = False
    appearance_raw: float = 0.0
    appearance_gate_passed: bool = False
    geometry_allows_appearance: bool = False
    hard_negative_similarity: float = 0.0
    hard_negative_margin: float = 1.0
    hard_negative_reject: bool = False
    ambiguous: bool = False


@dataclass
class TargetMemoryConfig:
    """TIM configuration.

    Defaults are conservative for 640x640-ish imagery. Tune with bag replay,
    not by guessing from one live session.
    """

    image_width: float = 640.0
    image_height: float = 640.0

    # Candidate scoring weights. Sum need not be exactly 1 because thresholds
    # are empirical gates over the final score.
    w_iou: float = 0.34
    w_distance: float = 0.26
    w_scale: float = 0.18
    w_confidence: float = 0.14
    w_id_bonus: float = 0.08

    # Association gates.
    accept_score_locked: float = 0.52
    accept_score_lost: float = 0.60
    ambiguity_margin: float = 0.07
    min_candidate_score: float = 0.10

    # Normalisation and decay.
    distance_sigma: float = 0.18  # relative to image diagonal
    scale_sigma: float = 0.55  # log-scale sigma
    stale_quality_decay: float = 0.85

    # State hysteresis, measured in update calls / frames.
    max_uncertain_frames: int = 6
    max_lost_frames: int = 30
    min_confirm_frames_after_reacquire: int = 1

    # Safety.
    allow_id_switch_recovery: bool = True
    same_id_accept_relief: float = 0.08

    # Controlled ID-switch recovery.
    # When enabled, TIM may accept a new tracker ID only if the candidate is
    # spatially plausible relative to the last trusted target memory.
    id_switch_spatial_gate_enabled: bool = False
    id_switch_min_iou: float = 0.05
    id_switch_min_distance: float = 0.35
    id_switch_min_scale: float = 0.35

    # TIM-V1A optional appearance cue.
    # Disabled by default so TIM-V0 behaviour remains unchanged.
    appearance_enabled: bool = False
    appearance_weight: float = 0.12
    appearance_min_similarity: float = 0.35
    appearance_update_alpha: float = 0.10
    appearance_ambiguous_only: bool = True

    # Freeze appearance memory updates after risky reacquisition / ID switch.
    # Default 0 preserves previous behaviour.
    appearance_update_cooldown_after_reacquire_frames: int = 0

    # TIM-V3C hard-negative memory.
    # During trusted lock, non-selected nearby candidates are remembered as
    # negative appearance prototypes. A future candidate that matches the
    # positive memory but is also too close to a hard negative is suppressed.
    hard_negative_memory_enabled: bool = True
    hard_negative_max_entries: int = 8
    hard_negative_update_alpha: float = 0.20
    hard_negative_min_candidate_similarity: float = 0.70
    hard_negative_reject_similarity: float = 0.80
    hard_negative_reject_margin: float = 0.03
    hard_negative_min_geometry: float = 0.20

    # TIM-MARS conservative output filter.
    # When enabled, a candidate must have strong and separated appearance evidence.
    appearance_conservative_enabled: bool = True
    appearance_conservative_require_appearance: bool = False
    appearance_conservative_min_similarity: float = 0.65
    appearance_conservative_margin: float = 0.05

    # TIM-V2K experimental rank-aware LOST/UNCERTAIN reacquisition.
    # Disabled by default to preserve TIM-V1 behaviour.
    rank_aware_reacquisition_enabled: bool = False
    rank_aware_lost_min_total: float = 0.40
    rank_aware_lost_min_geom: float = 0.10
    rank_aware_lost_min_app: float = 0.05
    rank_aware_lost_app_margin: float = 0.03
    rank_aware_confirm_frames: int = 1
    rank_aware_missing_ttl_frames: int = 8

    # TIM-V3A absence-aware new-ID recovery gate.
    # This protects the controller-facing target from jumping to a distractor
    # after the selected person has likely left the scene or remained hidden
    # for several frames. Same-ID continuity is not affected.
    absence_recovery_enabled: bool = False
    absence_after_missed_frames: int = 6
    absence_new_id_requires_appearance: bool = True
    absence_min_total: float = 0.45
    absence_min_distance: float = 0.25
    absence_min_scale: float = 0.35
    absence_min_similarity: float = 0.65
    absence_appearance_margin: float = 0.20
    absence_confirm_frames: int = 3


@dataclass
class TargetMemoryOutput:
    """Output published by TIM or converted into a ROS /target message."""

    state: TargetState
    control_mode: ControlMode
    target_track_id: Optional[int]
    bbox: Optional[BBox]
    quality: float
    visible: bool
    reacquired: bool
    frames_since_seen: int
    reason: str
    best_score: Optional[CandidateScore] = None
    all_scores: List[CandidateScore] = field(default_factory=list)
    memory_update_frozen: bool = False
    memory_update_freeze_reason: str = ""
    appearance_margin_best_vs_second: float = 0.0
    geometry_strength: float = 0.0
    risk_hard_negative: bool = False
    risk_absence: bool = False
    risk_scene_ambiguity: bool = False

    # Candidate belief diagnostics. These expose the best current candidate
    # separately from the controller-facing published target.
    candidate_track_id: Optional[int] = None
    candidate_score: float = 0.0
    publication_suppressed_reason: str = ""

    @property
    def control_valid(self) -> bool:
        # Only LOCKED/NORMAL is controller-valid.
        # UNCERTAIN, LOST, REACQUIRED, and NO_TARGET deliberately suppress output.
        return self.control_mode == ControlMode.NORMAL

    def cx_norm(self, image_width: float) -> Optional[float]:
        """Normalised target centre x in [0, 1]."""
        if self.bbox is None or image_width <= 0:
            return None
        x1, _, x2, _ = self.bbox
        return 0.5 * (x1 + x2) / image_width

    def cy_norm(self, image_height: float) -> Optional[float]:
        """Normalised target centre y in [0, 1]."""
        if self.bbox is None or image_height <= 0:
            return None
        _, y1, _, y2 = self.bbox
        return 0.5 * (y1 + y2) / image_height

__all__ = [
    "BBox",
    "TargetState",
    "ControlMode",
    "CandidateTrack",
    "CandidateScore",
    "TargetMemoryConfig",
    "TargetMemoryOutput",
]
