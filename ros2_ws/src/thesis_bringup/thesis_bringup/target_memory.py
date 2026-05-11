"""Selected-target memory for RGB-only micro-UAV following.

TIM converts noisy tracker outputs into one selected, control-valid target state.

TIM-V0 is the geometry-only baseline:
- IoU, distance, scale, confidence, and tracker-ID continuity
- no detector feedback
- no ROS dependency
- deterministic update rules

TIM-V1A adds an optional lightweight appearance cue:
- disabled by default
- used only as a gated tie-breaker
- cannot rescue geometrically implausible candidates
- appearance memory freezes during uncertain/lost/reacquired states
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import exp, log, sqrt
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from thesis_bringup.appearance_memory import cosine_similarity, update_feature_memory

BBox = Tuple[float, float, float, float]  # x1, y1, x2, y2, in pixels


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

    # TIM-V1A optional appearance cue.
    # Disabled by default so TIM-V0 behaviour remains unchanged.
    appearance_enabled: bool = False
    appearance_weight: float = 0.12
    appearance_min_similarity: float = 0.35
    appearance_update_alpha: float = 0.10
    appearance_ambiguous_only: bool = True


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

    @property
    def control_valid(self) -> bool:
        return self.control_mode in {ControlMode.NORMAL, ControlMode.CONFIRM, ControlMode.YAW_ONLY}

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


@dataclass
class _Memory:
    selected: bool = False
    state: TargetState = TargetState.NO_TARGET
    track_id: Optional[int] = None
    bbox: Optional[BBox] = None
    quality: float = 0.0
    frames_since_seen: int = 0
    confirmed_after_reacquire: int = 0
    appearance: Optional[Any] = None


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def bbox_area(bbox: BBox) -> float:
    x1, y1, x2, y2 = bbox
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def bbox_iou(a: BBox, b: BBox) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b

    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter <= 0.0:
        return 0.0

    union = bbox_area(a) + bbox_area(b) - inter
    if union <= 0.0:
        return 0.0
    return clamp01(inter / union)


def bbox_centre(bbox: BBox) -> Tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return 0.5 * (x1 + x2), 0.5 * (y1 + y2)


def centre_distance_norm(a: BBox, b: BBox, image_width: float, image_height: float) -> float:
    ax, ay = bbox_centre(a)
    bx, by = bbox_centre(b)
    diag = sqrt(image_width * image_width + image_height * image_height)
    if diag <= 0:
        raise ValueError("image diagonal must be positive")
    return sqrt((ax - bx) ** 2 + (ay - by) ** 2) / diag


def distance_similarity(distance_norm: float, sigma: float) -> float:
    if sigma <= 0:
        raise ValueError("distance sigma must be positive")
    return clamp01(exp(-0.5 * (distance_norm / sigma) ** 2))


def scale_similarity(a: BBox, b: BBox, sigma: float) -> float:
    """Return 1 for equal area, decaying with log-area ratio."""

    area_a = bbox_area(a)
    area_b = bbox_area(b)
    if area_a <= 1e-6 or area_b <= 1e-6:
        return 0.0
    if sigma <= 0:
        raise ValueError("scale sigma must be positive")
    ratio = area_b / area_a
    return clamp01(exp(-0.5 * (log(ratio) / sigma) ** 2))


def score_candidate(
    reference_bbox: BBox,
    candidate: CandidateTrack,
    current_track_id: Optional[int],
    cfg: TargetMemoryConfig,
) -> CandidateScore:
    """Score one candidate against the selected-target memory."""

    iou_score = bbox_iou(reference_bbox, candidate.bbox)
    dist = centre_distance_norm(reference_bbox, candidate.bbox, cfg.image_width, cfg.image_height)
    dist_score = distance_similarity(dist, cfg.distance_sigma)
    scale_score = scale_similarity(reference_bbox, candidate.bbox, cfg.scale_sigma)
    conf_score = clamp01(candidate.score)
    id_bonus = 1.0 if current_track_id is not None and candidate.track_id == current_track_id else 0.0

    total = (
        cfg.w_iou * iou_score
        + cfg.w_distance * dist_score
        + cfg.w_scale * scale_score
        + cfg.w_confidence * conf_score
        + cfg.w_id_bonus * id_bonus
    )

    return CandidateScore(
        track_id=candidate.track_id,
        total=clamp01(total),
        iou=iou_score,
        distance=dist_score,
        scale=scale_score,
        confidence=conf_score,
        id_bonus=id_bonus,
    )


def _control_mode_for_state(state: TargetState) -> ControlMode:
    if state == TargetState.NO_TARGET:
        return ControlMode.NO_CONTROL
    if state == TargetState.LOCKED:
        return ControlMode.NORMAL
    if state == TargetState.UNCERTAIN:
        return ControlMode.YAW_ONLY
    if state == TargetState.REACQUIRED:
        return ControlMode.CONFIRM
    return ControlMode.HOVER


class TargetIdentityMemory:
    """Selected-target memory state machine.

    Usage:
        tim = TargetIdentityMemory()
        tim.select(CandidateTrack(...))
        out = tim.update(current_tracks)
    """

    def __init__(self, cfg: Optional[TargetMemoryConfig] = None) -> None:
        self.cfg = cfg or TargetMemoryConfig()
        self._m = _Memory()

    @property
    def state(self) -> TargetState:
        return self._m.state

    @property
    def target_track_id(self) -> Optional[int]:
        return self._m.track_id

    @property
    def bbox(self) -> Optional[BBox]:
        return self._m.bbox

    def clear(self) -> TargetMemoryOutput:
        self._m = _Memory()
        return self._make_output(reason="operator_clear", visible=False, reacquired=False)

    def select(self, track: CandidateTrack) -> TargetMemoryOutput:
        """Operator selects a visible track as the active target."""

        self._m = _Memory(
            selected=True,
            state=TargetState.LOCKED,
            track_id=track.track_id,
            bbox=track.bbox,
            quality=clamp01(track.score),
            frames_since_seen=0,
            confirmed_after_reacquire=0,
            appearance=update_feature_memory(None, track.appearance, alpha=1.0),
        )
        return self._make_output(reason="operator_select", visible=True, reacquired=False)

    def update(self, candidates: Sequence[CandidateTrack]) -> TargetMemoryOutput:
        """Update target memory from current tracker candidates."""

        if not self._m.selected or self._m.bbox is None:
            return self._make_output(reason="no_operator_selected_target", visible=False, reacquired=False)

        candidates = [c for c in candidates if c.score >= self.cfg.min_candidate_score]
        if not candidates:
            return self._miss(reason="no_candidates")

        base_scores = [score_candidate(self._m.bbox, c, self._m.track_id, self.cfg) for c in candidates]
        base_sorted = sorted(base_scores, key=lambda s: s.total, reverse=True)
        base_best = base_sorted[0]
        base_second = base_sorted[1] if len(base_sorted) > 1 else None
        base_same_id = self._m.track_id is not None and base_best.track_id == self._m.track_id
        base_ambiguous = self._is_ambiguous(base_best, base_second, same_id=base_same_id)

        use_appearance = self._should_use_appearance(base_ambiguous=base_ambiguous)

        scores = [
            self._score_candidate(self._m.bbox, c, use_appearance=use_appearance)
            for c in candidates
        ]
        scores_sorted = sorted(scores, key=lambda s: s.total, reverse=True)
        best = scores_sorted[0]
        second = scores_sorted[1] if len(scores_sorted) > 1 else None

        best_candidate = next(c for c in candidates if c.track_id == best.track_id)
        same_id = self._m.track_id is not None and best.track_id == self._m.track_id
        ambiguous = self._is_ambiguous(best, second, same_id=same_id)

        best = CandidateScore(
            track_id=best.track_id,
            total=best.total,
            iou=best.iou,
            distance=best.distance,
            scale=best.scale,
            confidence=best.confidence,
            id_bonus=best.id_bonus,
            appearance=best.appearance,
            appearance_used=best.appearance_used,
            ambiguous=ambiguous,
        )
        scores_sorted[0] = best

        threshold = self.cfg.accept_score_lost if self._m.state == TargetState.LOST else self.cfg.accept_score_locked
        if same_id:
            threshold = max(0.0, threshold - self.cfg.same_id_accept_relief)

        if best.total < threshold:
            return self._miss(
                reason=f"best_below_threshold:{best.total:.3f}<{threshold:.3f}",
                best_score=best,
                all_scores=scores_sorted,
            )

        if ambiguous:
            return self._miss(
                reason="ambiguous_best_candidate",
                best_score=best,
                all_scores=scores_sorted,
            )

        if best.track_id != self._m.track_id and not self.cfg.allow_id_switch_recovery:
            return self._miss(
                reason="id_switch_recovery_disabled",
                best_score=best,
                all_scores=scores_sorted,
            )

        return self._accept(best_candidate, best_score=best, all_scores=scores_sorted)

    def _should_use_appearance(self, *, base_ambiguous: bool) -> bool:
        if not self.cfg.appearance_enabled:
            return False
        if self._m.appearance is None:
            return False
        if self._m.state in {TargetState.UNCERTAIN, TargetState.LOST, TargetState.REACQUIRED}:
            return True
        if not self.cfg.appearance_ambiguous_only:
            return True
        return bool(base_ambiguous)

    def _score_candidate(
        self,
        reference_bbox: BBox,
        candidate: CandidateTrack,
        *,
        use_appearance: bool,
    ) -> CandidateScore:
        base = score_candidate(reference_bbox, candidate, self._m.track_id, self.cfg)

        appearance_score = 0.0
        appearance_used = False
        total = base.total

        # Appearance is only a tie-breaker inside a geometrically plausible region.
        # It must not rescue candidates that are far from the predicted target memory.
        geometry_allows_appearance = (
            base.iou > 0.0
            or (base.distance >= 0.25 and base.scale >= 0.35)
        )

        if use_appearance and candidate.appearance is not None and geometry_allows_appearance:
            appearance_score = clamp01(cosine_similarity(self._m.appearance, candidate.appearance))
            if appearance_score >= self.cfg.appearance_min_similarity:
                total = clamp01(total + self.cfg.appearance_weight * appearance_score)
                appearance_used = True

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
            ambiguous=base.ambiguous,
        )

    def _is_ambiguous(
        self,
        best: CandidateScore,
        second: Optional[CandidateScore],
        *,
        same_id: bool,
    ) -> bool:
        if second is None:
            return False
        if same_id:
            return False
        return (best.total - second.total) < self.cfg.ambiguity_margin

    def _accept(
        self,
        candidate: CandidateTrack,
        *,
        best_score: CandidateScore,
        all_scores: List[CandidateScore],
    ) -> TargetMemoryOutput:
        previous_state = self._m.state
        previous_id = self._m.track_id
        id_changed = previous_id is not None and candidate.track_id != previous_id
        was_lostish = previous_state in {TargetState.UNCERTAIN, TargetState.LOST}

        reacquired = bool(id_changed or was_lostish)

        if previous_state == TargetState.REACQUIRED:
            self._m.confirmed_after_reacquire += 1
        elif reacquired:
            self._m.confirmed_after_reacquire = 0

        if reacquired and self._m.confirmed_after_reacquire < self.cfg.min_confirm_frames_after_reacquire:
            new_state = TargetState.REACQUIRED
        else:
            new_state = TargetState.LOCKED

        self._m.selected = True
        self._m.state = new_state
        self._m.track_id = candidate.track_id
        self._m.bbox = candidate.bbox
        self._m.quality = clamp01(0.65 * best_score.total + 0.35 * candidate.score)
        self._m.frames_since_seen = 0

        # TIM-V1A memory update policy:
        # update only after a confirmed LOCKED state.
        # freeze during UNCERTAIN, LOST, and REACQUIRED.
        if new_state == TargetState.LOCKED:
            self._m.appearance = update_feature_memory(
                self._m.appearance,
                candidate.appearance,
                alpha=self.cfg.appearance_update_alpha,
            )

        return self._make_output(
            reason="accepted_candidate" if not reacquired else "reacquired_candidate",
            visible=True,
            reacquired=reacquired,
            best_score=best_score,
            all_scores=all_scores,
        )

    def _miss(
        self,
        *,
        reason: str,
        best_score: Optional[CandidateScore] = None,
        all_scores: Optional[List[CandidateScore]] = None,
    ) -> TargetMemoryOutput:
        self._m.frames_since_seen += 1
        self._m.quality *= self.cfg.stale_quality_decay
        self._m.confirmed_after_reacquire = 0

        if self._m.frames_since_seen <= self.cfg.max_uncertain_frames:
            self._m.state = TargetState.UNCERTAIN
        else:
            self._m.state = TargetState.LOST

        return self._make_output(
            reason=reason,
            visible=False,
            reacquired=False,
            best_score=best_score,
            all_scores=all_scores or [],
        )

    def _make_output(
        self,
        *,
        reason: str,
        visible: bool,
        reacquired: bool,
        best_score: Optional[CandidateScore] = None,
        all_scores: Optional[List[CandidateScore]] = None,
    ) -> TargetMemoryOutput:
        return TargetMemoryOutput(
            state=self._m.state,
            control_mode=_control_mode_for_state(self._m.state),
            target_track_id=self._m.track_id,
            bbox=self._m.bbox,
            quality=clamp01(self._m.quality),
            visible=visible,
            reacquired=reacquired,
            frames_since_seen=self._m.frames_since_seen,
            reason=reason,
            best_score=best_score,
            all_scores=all_scores or [],
        )


__all__ = [
    "BBox",
    "CandidateScore",
    "CandidateTrack",
    "ControlMode",
    "TargetIdentityMemory",
    "TargetMemoryConfig",
    "TargetMemoryOutput",
    "TargetState",
    "bbox_area",
    "bbox_centre",
    "bbox_iou",
    "centre_distance_norm",
    "distance_similarity",
    "scale_similarity",
    "score_candidate",
]
