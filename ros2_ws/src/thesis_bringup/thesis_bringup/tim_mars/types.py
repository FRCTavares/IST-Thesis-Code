"""Shared public data types for TIM-MARS.

This module contains the enums, dataclasses, and aliases shared across the
TIM-MARS implementation: candidate tracks, candidate scores, memory outputs,
control modes, target states, and the TargetMemoryConfig parameter set.

Keeping these definitions separate avoids circular imports between scoring,
appearance, reacquisition, ROS glue, and the selected-target state machine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional, Tuple

from thesis_bringup.tim_mars.crop_quality import (
    AppearanceCropQuality,
)

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
class AppearanceObservationProvenance:
    """Origin of the embedding attached to one current candidate."""

    source_frame_id: Optional[int]
    source_image_timestamp_ns: Optional[int]
    embedded_ns: int
    embedding_age_ms: float
    frame_generation: int
    track_generation: int
    source_bbox: BBox
    source_crop_quality: AppearanceCropQuality


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

    # Tracker-timeline provenance for lifecycle accounting. These values
    # describe the current tracker observation, not the possibly cached
    # appearance image from which the embedding originated.
    tracker_frame_id: Optional[int] = None
    tracker_timestamp_ns: Optional[int] = None

    appearance: Optional[Any] = None

    # State-machine geometry remains clipped to the candidate frame. The
    # original geometry is retained so appearance attachment can measure how
    # much of the requested crop lies outside the actual image.
    unclipped_bbox: Optional[BBox] = None

    # Crop quality describes the current appearance observation. Direct
    # algorithm tests that provide embeddings manually remain compatible by
    # omitting this optional provenance.
    appearance_crop_quality: Optional[
        AppearanceCropQuality
    ] = None
    appearance_memory_update_eligible: bool = True
    appearance_provenance: Optional[
        AppearanceObservationProvenance
    ] = None


@dataclass(frozen=True)
class CandidateScore:
    track_id: int
    # ``total`` is the legacy clipped ranking score kept for compatibility.
    # Geometry validation must use ``geometry_score``; candidate ordering uses
    # the unclipped ``ranking_score``.
    total: float
    iou: float
    distance: float
    scale: float
    confidence: float
    id_bonus: float
    geometry_score: float = 0.0
    ranking_score: float = 0.0
    appearance: float = 0.0
    appearance_available: bool = False
    appearance_evaluated: bool = False
    appearance_similarity_passed: bool = False
    appearance_used: bool = False
    appearance_accepted_for_publication: bool = False
    appearance_raw: float = 0.0

    # P1.4 separated positive-memory diagnostics.
    protected_anchor_similarity: float = 0.0
    trusted_gallery_similarity: float = 0.0
    adaptive_similarity: float = 0.0
    positive_similarity: float = 0.0
    positive_support_source: str = "none"

    appearance_gate_passed: bool = False
    geometry_allows_appearance: bool = False
    hard_negative_similarity: float = 0.0
    hard_negative_margin: float = 1.0
    hard_negative_reject: bool = False
    ambiguous: bool = False

    def __post_init__(self) -> None:
        """Backfill separated scores for legacy keyword constructors."""
        if self.geometry_score == 0.0 and self.total != 0.0:
            object.__setattr__(
                self,
                "geometry_score",
                float(self.total),
            )
        if self.ranking_score == 0.0 and self.total != 0.0:
            object.__setattr__(
                self,
                "ranking_score",
                float(self.total),
            )


@dataclass
class TargetMemoryConfig:
    """TIM configuration.

    Defaults are conservative for 640x640-ish imagery. Tune with bag replay,
    not by guessing from one live session.
    """

    # Image geometry.
    # Candidate bboxes are evaluated in this coordinate frame after ROS-side
    # conversion from tracker messages.
    image_width: float = 640.0
    image_height: float = 640.0

    # Candidate scoring weights.
    # These combine geometry, confidence, and tracker-ID continuity into the
    # base score. The sum does not need to be exactly 1 because acceptance
    # thresholds are empirical gates over the final score.
    w_iou: float = 0.34
    w_distance: float = 0.26
    w_scale: float = 0.18
    w_confidence: float = 0.14
    w_id_bonus: float = 0.08

    # Acceptance and ambiguity gates.
    # Locked targets can be accepted more easily than lost targets. Ambiguity
    # margin controls when the best and second-best candidates are too close.
    accept_score_locked: float = 0.52
    accept_score_lost: float = 0.60
    ambiguity_margin: float = 0.07
    min_candidate_score: float = 0.10

    # Geometry normalization and stale-memory decay.
    # Distance is normalized by image diagonal. Scale uses log-space similarity.
    distance_sigma: float = 0.18  # relative to image diagonal
    scale_sigma: float = 0.55  # log-scale sigma
    stale_quality_decay: float = 0.85

    # State hysteresis, measured in update calls / frames.
    # These values control how long TIM-MARS remains uncertain before declaring
    # the selected target lost and how long reacquisition needs confirmation.
    max_uncertain_frames: int = 6
    min_confirm_frames_after_reacquire: int = 1

    # Experimental short-gap motion reference (Issue #21).
    # Disabled by default. When enabled, a centre-only constant-velocity
    # reference may replace the frozen last trusted bbox after at least one
    # committed miss. Prediction is capped in elapsed tracker time.
    motion_prediction_enabled: bool = False
    motion_prediction_max_horizon_s: float = 0.25

    # Identity continuity and controlled ID-switch recovery.
    # Same-ID continuity receives a small score relief. New tracker IDs are
    # accepted only when recovery is enabled and any configured spatial gate
    # considers the candidate plausible relative to the remembered target.
    allow_id_switch_recovery: bool = True
    same_id_accept_relief: float = 0.08
    id_switch_spatial_gate_enabled: bool = False
    id_switch_min_iou: float = 0.05
    id_switch_min_distance: float = 0.35
    id_switch_min_scale: float = 0.35
    # Disabled at 0.0 for generic geometry-only configurations. When positive,
    # a different tracker ID must reach this similarity to positive appearance
    # memory before it can replace the selected identity.
    id_switch_min_appearance_similarity: float = 0.0

    # Short-gap identity protection.
    # If the trusted tracker ID disappears briefly, TIM-MARS should not
    # immediately replace it with a nearby new ID. If the same ID returns inside
    # the grace window, it is preferred unless it is clearly unusable.
    short_gap_same_id_priority_enabled: bool = True
    short_gap_same_id_grace_frames: int = 8
    short_gap_same_id_min_total: float = 0.30
    short_gap_new_id_suppression_enabled: bool = True
    short_gap_new_id_allow_total: float = 0.70
    short_gap_group_risk_allow_total: float = 0.85

    # Optional appearance scoring.
    # Appearance is secondary evidence. It can help separate plausible
    # candidates, but it should not rescue geometrically implausible candidates.
    appearance_enabled: bool = False
    appearance_weight: float = 0.12
    appearance_min_similarity: float = 0.35
    appearance_update_alpha: float = 0.10
    appearance_ambiguous_only: bool = True

    # Appearance memory update policy.
    # Cooldown can freeze positive-memory updates after risky reacquisition so
    # TIM-MARS does not immediately learn a wrong target.
    appearance_update_cooldown_after_reacquire_frames: int = 0

    # P1.4 protected/adaptive positive-memory separation.
    # Disabled by default until deterministic replay evidence supports
    # promotion over the current canonical behaviour.
    appearance_protected_memory_enabled: bool = False
    appearance_trusted_gallery_max_entries: int = 4

    # A gallery-supported risky reacquisition may optionally require
    # independent agreement with the immutable operator anchor.
    # Zero preserves the previous max-over-gallery behaviour.
    appearance_gallery_min_anchor_similarity: float = 0.0

    appearance_trusted_lock_frames_before_update: int = 2

    # Hard-negative distractor memory.
    # During trusted lock, nearby non-selected tracks can be remembered as
    # negative appearance prototypes. Future candidates that look too close to a
    # hard negative can be suppressed.
    hard_negative_memory_enabled: bool = True
    hard_negative_max_entries: int = 8
    hard_negative_update_alpha: float = 0.20
    hard_negative_min_candidate_similarity: float = 0.70
    hard_negative_confirm_observations: int = 2

    # Candidates almost identical to protected positive memory are more likely
    # duplicate detections or target fragments than reliable distractors.
    # Values above 1.0 preserve the previous behaviour.
    hard_negative_max_positive_similarity: float = 1.01

    hard_negative_reject_similarity: float = 0.80
    hard_negative_reject_margin: float = 0.03
    hard_negative_min_geometry: float = 0.20

    # Committed hard-negative lifecycle policy. Zero disables automatic
    # expiry, preserving the established canonical behaviour until replay
    # evidence supports a finite age. Prototypes retain full rejection
    # strength until explicit atomic expiry; embeddings are never softened.
    hard_negative_max_age_frames: int = 0
    hard_negative_decay_policy: str = "none_until_expiry"

    # Same-ID hijack protection.
    # When enabled, uninterrupted tracker-ID continuity remains trusted unless
    # a nearby, spatially plausible competing person challenges that identity.
    # During such a challenge, the same-ID candidate must carry current
    # positive appearance support and must not match hard-negative memory.
    same_id_hijack_protection_enabled: bool = False

    # Conservative appearance publication filter.
    # When enabled, a candidate needs sufficiently strong and separated
    # appearance evidence before it is allowed to drive controller-facing output.
    appearance_conservative_enabled: bool = True
    appearance_conservative_require_appearance: bool = False
    appearance_conservative_min_similarity: float = 0.65
    appearance_conservative_margin: float = 0.05

    # Rank-aware reacquisition.
    # In UNCERTAIN/LOST states, candidates can be ranked by appearance evidence
    # rather than raw total score alone. Confirmation can require repeated frames.
    rank_aware_reacquisition_enabled: bool = False
    rank_aware_lost_min_total: float = 0.40
    rank_aware_lost_min_geom: float = 0.10
    rank_aware_lost_min_app: float = 0.05
    rank_aware_lost_app_margin: float = 0.03
    rank_aware_confirm_frames: int = 1

    # Candidate-belief confirmation.
    # TIM-MARS may remember a plausible new candidate during UNCERTAIN/LOST but
    # suppress controller-facing publication until repeated confirmation.
    candidate_belief_enabled: bool = False
    candidate_belief_min_score: float = 0.45
    candidate_belief_confirm_frames: int = 2

    # Absence-aware new-ID recovery.
    # After longer target absence, accepting a new tracker ID requires stronger
    # geometry and appearance evidence. Same-ID continuity is not affected.
    absence_recovery_enabled: bool = False
    absence_after_missed_frames: int = 6
    absence_new_id_requires_appearance: bool = True
    absence_min_total: float = 0.45
    absence_min_distance: float = 0.25
    absence_min_scale: float = 0.35
    absence_min_similarity: float = 0.65
    absence_appearance_margin: float = 0.20
    absence_confirm_frames: int = 3


@dataclass(frozen=True)
class PositiveMemoryBootstrapEvent:
    """Auditable evidence for creation of the immutable operator anchor."""

    action: str
    track_id: int
    accepted_bbox: BBox
    acceptance_memory_source: str
    memory_update_eligible: bool
    ambiguous: bool
    hard_negative_reject: bool

    operator_track_id: Optional[int] = None
    current_lineage_track_id: Optional[int] = None
    current_lineage_supported: bool = False

    # Runtime evidence correspondence. Direct algorithm tests may leave these
    # unset; TimMarsRuntime enriches them from the accepted tracker frame and
    # structured appearance-cache entry.
    frame_id: Optional[int] = None
    track_timestamp_ns: Optional[int] = None
    selected_image_timestamp_ns: Optional[int] = None
    image_track_offset_ms: Optional[float] = None

    appearance_source_frame_id: Optional[int] = None
    appearance_source_image_timestamp_ns: Optional[int] = None
    appearance_embedded_ns: Optional[int] = None
    appearance_embedding_age_ms: Optional[float] = None
    appearance_frame_generation: Optional[int] = None
    appearance_track_generation: Optional[int] = None
    appearance_source_bbox: Optional[BBox] = None

    accepted_crop_quality: Optional[
        AppearanceCropQuality
    ] = None
    appearance_source_crop_quality: Optional[
        AppearanceCropQuality
    ] = None


@dataclass(frozen=True)
class HardNegativeMemoryEvent:
    """One auditable hard-negative memory lifecycle mutation."""

    action: str
    source: str
    source_track_id: Optional[int] = None
    selected_track_id: Optional[int] = None
    source_track_ids: tuple[int, ...] = ()
    selected_track_ids: tuple[int, ...] = ()
    observations: int = 0
    positive_similarity: float = 0.0
    geometry_strength: float = 0.0
    prototype_similarity: float = 0.0
    memory_size: int = 0
    snapshot: Optional[
        "HardNegativeMemorySnapshot"
    ] = None


@dataclass(frozen=True)
class HardNegativeMemorySnapshot:
    """Serializable state of one hard-negative prototype."""

    lifecycle_state: str
    source: str
    source_track_ids: tuple[int, ...] = ()
    selected_track_ids: tuple[int, ...] = ()
    observations: int = 0

    first_frame_id: Optional[int] = None
    last_frame_id: Optional[int] = None
    first_timestamp_ns: Optional[int] = None
    last_timestamp_ns: Optional[int] = None
    age_frames: Optional[int] = None
    expires_at_frame_id: Optional[int] = None
    expired: bool = False

    latest_bbox: Optional[BBox] = None
    latest_confidence: float = 0.0
    latest_crop_quality: Optional[
        AppearanceCropQuality
    ] = None

    positive_similarity: float = 0.0
    geometry_strength: float = 0.0
    latest_iou: float = 0.0
    latest_distance: float = 0.0
    latest_scale: float = 0.0
    latest_geometry_score: float = 0.0

    appearance_source_frame_id: Optional[int] = None
    appearance_source_image_timestamp_ns: Optional[int] = None
    appearance_embedded_ns: Optional[int] = None
    appearance_embedding_age_ms: Optional[float] = None
    appearance_frame_generation: Optional[int] = None
    appearance_track_generation: Optional[int] = None
    appearance_source_bbox: Optional[BBox] = None
    appearance_source_crop_quality: Optional[
        AppearanceCropQuality
    ] = None

    max_age_frames: int = 0
    decay_policy: str = "none_until_expiry"


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

    # P1.4 acceptance and positive-memory transaction diagnostics.
    acceptance_memory_source: str = "none"
    positive_memory_updated: bool = False
    positive_memory_update_reason: str = ""
    positive_memory_bootstrap_event: Optional[
        PositiveMemoryBootstrapEvent
    ] = None
    protected_anchor_available: bool = False
    trusted_gallery_size: int = 0
    appearance_lineage_trusted: bool = False
    appearance_trusted_lock_streak: int = 0

    appearance_margin_best_vs_second: float = 0.0
    geometry_strength: float = 0.0
    risk_hard_negative: bool = False
    hard_negative_memory_size: int = 0
    hard_negative_events: tuple[
        HardNegativeMemoryEvent,
        ...,
    ] = ()
    hard_negative_entries: tuple[
        HardNegativeMemorySnapshot,
        ...,
    ] = ()
    hard_negative_pending_entries: tuple[
        HardNegativeMemorySnapshot,
        ...,
    ] = ()
    hard_negative_current_frame_id: Optional[int] = None
    hard_negative_max_age_frames: int = 0
    hard_negative_decay_policy: str = "none_until_expiry"
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
    "AppearanceCropQuality",
    "AppearanceObservationProvenance",
    "CandidateTrack",
    "CandidateScore",
    "TargetMemoryConfig",
    "PositiveMemoryBootstrapEvent",
    "HardNegativeMemoryEvent",
    "HardNegativeMemorySnapshot",
    "TargetMemoryOutput",
]
