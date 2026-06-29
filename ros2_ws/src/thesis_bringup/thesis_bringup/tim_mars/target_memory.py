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

from thesis_bringup.tim_mars.appearance_memory import cosine_similarity, update_feature_memory

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
        self._appearance_update_cooldown_frames_remaining = 0
        self._rank_reacq_candidate_id: Optional[int] = None
        self._rank_reacq_confirm_count = 0
        self._absence_reacq_candidate_id: Optional[int] = None
        self._absence_reacq_confirm_count = 0
        self._hard_negative_memory: List[Any] = []

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
        self._appearance_update_cooldown_frames_remaining = 0
        self._rank_reacq_candidate_id = None
        self._rank_reacq_confirm_count = 0
        self._absence_reacq_candidate_id = None
        self._absence_reacq_confirm_count = 0
        self._hard_negative_memory = []
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
        self._appearance_update_cooldown_frames_remaining = 0
        self._rank_reacq_candidate_id = None
        self._rank_reacq_confirm_count = 0
        self._absence_reacq_candidate_id = None
        self._absence_reacq_confirm_count = 0
        self._hard_negative_memory = []
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

        self._update_hard_negative_memory(candidates, scores_sorted)

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
            appearance_raw=best.appearance_raw,
            appearance_gate_passed=best.appearance_gate_passed,
            geometry_allows_appearance=best.geometry_allows_appearance,
            hard_negative_similarity=best.hard_negative_similarity,
            hard_negative_margin=best.hard_negative_margin,
            hard_negative_reject=best.hard_negative_reject,
            ambiguous=ambiguous,
        )
        scores_sorted[0] = best


        absence_reject_reason = self._absence_aware_reacquisition_reject_reason(
            best,
            scores_sorted,
            same_id=same_id,
        )
        if absence_reject_reason is not None:
            return self._miss(
                reason=absence_reject_reason,
                best_score=best,
                all_scores=scores_sorted,
            )

        rank_aware_best, rank_aware_pending = self._rank_aware_reacquisition_candidate(
            scores_sorted,
            candidates,
        )
        if rank_aware_best is not None:
            rank_candidate = next(c for c in candidates if c.track_id == rank_aware_best.track_id)
            rank_id_switch = rank_aware_best.track_id != self._m.track_id

            if rank_id_switch and self.cfg.id_switch_spatial_gate_enabled:
                spatial_ok = (
                    rank_aware_best.iou >= self.cfg.id_switch_min_iou
                    or (
                        rank_aware_best.distance >= self.cfg.id_switch_min_distance
                        and rank_aware_best.scale >= self.cfg.id_switch_min_scale
                    )
                )
                if not spatial_ok:
                    return self._miss(
                        reason=(
                            "rank_aware_id_switch_spatial_reject:"
                            f" iou={rank_aware_best.iou:.3f}"
                            f" distance={rank_aware_best.distance:.3f}"
                            f" scale={rank_aware_best.scale:.3f}"
                        ),
                        best_score=rank_aware_best,
                        all_scores=scores_sorted,
                    )

            return self._accept(
                rank_candidate,
                best_score=rank_aware_best,
                all_scores=scores_sorted,
            )

        if rank_aware_pending:
            return self._miss(
                reason="rank_aware_reacquisition_pending",
                best_score=best,
                all_scores=scores_sorted,
            )

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

        id_switch = best.track_id != self._m.track_id

        if id_switch and not self.cfg.allow_id_switch_recovery:
            return self._miss(
                reason="id_switch_recovery_disabled",
                best_score=best,
                all_scores=scores_sorted,
            )

        if id_switch and self.cfg.id_switch_spatial_gate_enabled:
            spatial_ok = (
                best.iou >= self.cfg.id_switch_min_iou
                or (
                    best.distance >= self.cfg.id_switch_min_distance
                    and best.scale >= self.cfg.id_switch_min_scale
                )
            )
            if not spatial_ok:
                return self._miss(
                    reason=(
                        "id_switch_spatial_reject:"
                        f" iou={best.iou:.3f}"
                        f" distance={best.distance:.3f}"
                        f" scale={best.scale:.3f}"
                    ),
                    best_score=best,
                    all_scores=scores_sorted,
                )


        if self._hard_negative_should_reject(best):

            return self._miss(
                reason=(
                    "hard_negative_reject:"
                    f" neg={best.hard_negative_similarity:.3f}"
                    f" margin={best.hard_negative_margin:.3f}"
                ),
                best_score=best,
                all_scores=scores_sorted,
            )


        return self._accept(
            best_candidate,
            best_score=best,
            all_scores=scores_sorted,
        )

    def _rank_aware_app_raw(self, candidate: CandidateTrack, score: CandidateScore) -> float:
        """Appearance evidence for rank-aware reacquisition.

        TIM-V2K intentionally uses the same gated appearance_raw exported in
        diagnostics so live behaviour matches the offline simulator. Geometry
        bypass is a separate future experiment, not the V2K default.
        """
        return float(score.appearance_raw)

    def _appearance_margin(self, selected: CandidateScore, scores_sorted: List[CandidateScore]) -> float:
        other_apps = [
            float(s.appearance_raw)
            for s in scores_sorted
            if int(s.track_id) != int(selected.track_id) and s.geometry_allows_appearance
        ]
        return float(selected.appearance_raw) - max(other_apps, default=0.0)

    def _geometry_strength(self, score: Optional[CandidateScore]) -> float:
        if score is None:
            return 0.0
        return max(float(score.iou), float(score.distance), float(score.scale))

    def _scene_ambiguity_risk(self, best: Optional[CandidateScore], scores_sorted: List[CandidateScore]) -> bool:
        if best is None:
            return False
        if bool(best.ambiguous):
            return True
        if not best.geometry_allows_appearance:
            return False
        app_margin = self._appearance_margin(best, scores_sorted)
        return (
            best.appearance_raw >= self.cfg.appearance_conservative_min_similarity
            and app_margin < self.cfg.appearance_conservative_margin
        )

    def _absence_risk(self) -> bool:
        if not self.cfg.absence_recovery_enabled:
            return False
        return (
            self._m.state in {TargetState.UNCERTAIN, TargetState.LOST}
            and self._m.frames_since_seen >= max(1, int(self.cfg.absence_after_missed_frames))
        )



    def _reset_absence_reacquisition_confirmation(self) -> None:
        self._absence_reacq_candidate_id = None
        self._absence_reacq_confirm_count = 0







    def _absence_aware_reacquisition_reject_reason(
        self,
        best: CandidateScore,
        scores_sorted: List[CandidateScore],
        *,
        same_id: bool,
    ) -> Optional[str]:
        """Reject risky new-ID recovery after likely target absence."""

        if not self.cfg.absence_recovery_enabled:
            return None

        if self._m.state not in {TargetState.UNCERTAIN, TargetState.LOST}:
            self._reset_absence_reacquisition_confirmation()
            return None

        if same_id:
            self._reset_absence_reacquisition_confirmation()
            return None

        if self._m.frames_since_seen < max(1, int(self.cfg.absence_after_missed_frames)):
            self._reset_absence_reacquisition_confirmation()
            return None

        if best.total < self.cfg.absence_min_total:
            self._reset_absence_reacquisition_confirmation()
            return f"absence_recovery_reject:total {best.total:.3f}<{self.cfg.absence_min_total:.3f}"

        if best.distance < self.cfg.absence_min_distance:
            self._reset_absence_reacquisition_confirmation()
            return f"absence_recovery_reject:distance {best.distance:.3f}<{self.cfg.absence_min_distance:.3f}"

        if best.scale < self.cfg.absence_min_scale:
            self._reset_absence_reacquisition_confirmation()
            return f"absence_recovery_reject:scale {best.scale:.3f}<{self.cfg.absence_min_scale:.3f}"

        app_margin = self._appearance_margin(best, scores_sorted)

        if self.cfg.absence_new_id_requires_appearance:
            if not best.geometry_allows_appearance or best.appearance_raw <= 0.0:
                self._reset_absence_reacquisition_confirmation()
                return "absence_recovery_reject:no_appearance"

            if best.appearance_raw < self.cfg.absence_min_similarity:
                self._reset_absence_reacquisition_confirmation()
                return (
                    "absence_recovery_reject:appearance"
                    f" {best.appearance_raw:.3f}<{self.cfg.absence_min_similarity:.3f}"
                )

            if app_margin < self.cfg.absence_appearance_margin:
                self._reset_absence_reacquisition_confirmation()
                return (
                    "absence_recovery_reject:appearance_margin"
                    f" {app_margin:.3f}<{self.cfg.absence_appearance_margin:.3f}"
                )

        if self._absence_reacq_candidate_id == best.track_id:
            self._absence_reacq_confirm_count += 1
        else:
            self._absence_reacq_candidate_id = best.track_id
            self._absence_reacq_confirm_count = 1

        required = max(1, int(self.cfg.absence_confirm_frames))
        if self._absence_reacq_confirm_count < required:
            return (
                "absence_recovery_pending:"
                f" id={best.track_id}"
                f" confirm={self._absence_reacq_confirm_count}/{required}"
                f" app={best.appearance_raw:.3f}"
                f" margin={app_margin:.3f}"
            )

        return None


    def _rank_aware_reacquisition_candidate(
        self,
        scores_sorted: List[CandidateScore],
        candidates: Sequence[CandidateTrack],
    ) -> tuple[Optional[CandidateScore], bool]:
        if not self.cfg.rank_aware_reacquisition_enabled:
            return None, False

        if self._m.state not in {TargetState.UNCERTAIN, TargetState.LOST}:
            self._rank_reacq_candidate_id = None
            self._rank_reacq_confirm_count = 0
            return None, False

        by_id = {int(c.track_id): c for c in candidates}
        enriched: list[tuple[CandidateScore, float]] = []

        for score in scores_sorted:
            candidate = by_id.get(int(score.track_id))
            if candidate is None:
                continue

            app_raw = self._rank_aware_app_raw(candidate, score)

            if (
                score.total >= self.cfg.rank_aware_lost_min_total
                and score.distance >= self.cfg.rank_aware_lost_min_geom
                and app_raw >= self.cfg.rank_aware_lost_min_app
            ):
                enriched.append((score, app_raw))

        if not enriched:
            self._rank_reacq_candidate_id = None
            self._rank_reacq_confirm_count = 0
            return None, False

        best, best_app = max(
            enriched,
            key=lambda item: (
                float(item[1]),
                float(item[0].distance),
                float(item[0].scale),
                float(item[0].total),
            ),
        )

        other_apps = [
            app
            for score, app in enriched
            if int(score.track_id) != int(best.track_id)
        ]
        best_other_app = max(other_apps, default=0.0)

        if (float(best_app) - best_other_app) < self.cfg.rank_aware_lost_app_margin:
            self._rank_reacq_candidate_id = None
            self._rank_reacq_confirm_count = 0
            return None, False

        if (
            self.cfg.absence_recovery_enabled
            and self._m.track_id is not None
            and int(best.track_id) != int(self._m.track_id)
            and self._m.frames_since_seen >= max(1, int(self.cfg.absence_after_missed_frames))
        ):
            app_margin = float(best_app) - float(best_other_app)
            if (
                best.total < self.cfg.absence_min_total
                or best.distance < self.cfg.absence_min_distance
                or best.scale < self.cfg.absence_min_scale
                or best_app < self.cfg.absence_min_similarity
                or app_margin < self.cfg.absence_appearance_margin
            ):
                self._rank_reacq_candidate_id = None
                self._rank_reacq_confirm_count = 0
                return None, False

        if self._rank_reacq_candidate_id == best.track_id:
            self._rank_reacq_confirm_count += 1
        else:
            self._rank_reacq_candidate_id = best.track_id
            self._rank_reacq_confirm_count = 1

        pending = self._rank_reacq_confirm_count < max(1, int(self.cfg.rank_aware_confirm_frames))
        if pending:
            return None, True

        # Return a copy with rank-aware appearance evidence exposed in diagnostics.
        best = CandidateScore(
            track_id=best.track_id,
            total=best.total,
            iou=best.iou,
            distance=best.distance,
            scale=best.scale,
            confidence=best.confidence,
            id_bonus=best.id_bonus,
            appearance=best_app,
            appearance_used=True,
            appearance_raw=best_app,
            appearance_gate_passed=True,
            geometry_allows_appearance=best.geometry_allows_appearance,
            hard_negative_similarity=best.hard_negative_similarity,
            hard_negative_margin=best.hard_negative_margin,
            hard_negative_reject=best.hard_negative_reject,
            ambiguous=best.ambiguous,
        )
        return best, False

    def _hard_negative_similarity(self, appearance: Any) -> float:
        if not self.cfg.hard_negative_memory_enabled:
            return 0.0

        if appearance is None or not self._hard_negative_memory:
            return 0.0

        return max(
            clamp01(cosine_similarity(memory, appearance))
            for memory in self._hard_negative_memory
        )

    def _hard_negative_should_reject(self, best: CandidateScore) -> bool:
        if not self.cfg.hard_negative_memory_enabled:
            return False

        if not best.geometry_allows_appearance:
            return False

        return bool(best.hard_negative_reject)

    def _update_hard_negative_memory(
        self,
        candidates: Sequence[CandidateTrack],
        scores_sorted: List[CandidateScore],
    ) -> None:
        if not self.cfg.hard_negative_memory_enabled:
            return

        if not self.cfg.appearance_enabled:
            return

        if self._m.track_id is None or self._m.appearance is None:
            return

        if self._m.state != TargetState.LOCKED:
            return

        by_id = {int(c.track_id): c for c in candidates}
        trusted_id = int(self._m.track_id)
        max_entries = max(1, int(self.cfg.hard_negative_max_entries))

        for score in scores_sorted:
            track_id = int(score.track_id)

            if track_id == trusted_id:
                continue

            if not score.geometry_allows_appearance:
                continue

            if max(score.distance, score.iou) < self.cfg.hard_negative_min_geometry:
                continue

            candidate = by_id.get(track_id)
            if candidate is None or candidate.appearance is None:
                continue

            if score.appearance_raw < self.cfg.hard_negative_min_candidate_similarity:
                continue

            updated = False
            for i, memory in enumerate(self._hard_negative_memory):
                sim = clamp01(cosine_similarity(memory, candidate.appearance))
                if sim >= self.cfg.hard_negative_min_candidate_similarity:
                    self._hard_negative_memory[i] = update_feature_memory(
                        memory,
                        candidate.appearance,
                        alpha=self.cfg.hard_negative_update_alpha,
                    )
                    updated = True
                    break

            if not updated:
                self._hard_negative_memory.append(candidate.appearance)

            if len(self._hard_negative_memory) > max_entries:
                self._hard_negative_memory = self._hard_negative_memory[-max_entries:]



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

    def _bootstrap_positive_appearance_if_needed(self, candidate: CandidateTrack) -> None:
        """Initialise positive appearance memory after selection if it was missing.

        TIM can select a target before the image callback has produced a MARS
        embedding for that track. Without this delayed bootstrap, appearance_raw
        stays permanently zero and appearance-based gates remain blind.
        """

        if not self.cfg.appearance_enabled:
            return

        if self._m.appearance is not None:
            return

        if self._m.track_id is None or int(candidate.track_id) != int(self._m.track_id):
            return

        if candidate.appearance is None:
            return

        self._m.appearance = update_feature_memory(
            None,
            candidate.appearance,
            alpha=1.0,
        )

    def _score_candidate(
        self,
        reference_bbox: BBox,
        candidate: CandidateTrack,
        *,
        use_appearance: bool,
    ) -> CandidateScore:
        self._bootstrap_positive_appearance_if_needed(candidate)

        base = score_candidate(reference_bbox, candidate, self._m.track_id, self.cfg)

        appearance_score = 0.0
        appearance_raw = 0.0
        appearance_used = False
        appearance_gate_passed = False
        hard_negative_similarity = 0.0
        hard_negative_margin = 1.0
        hard_negative_reject = False
        total = base.total

        geometry_allows_appearance = (
            base.iou > 0.0
            or (base.distance >= 0.25 and base.scale >= 0.35)
        )

        if candidate.appearance is not None and geometry_allows_appearance:
            if self._m.appearance is not None:
                appearance_raw = clamp01(cosine_similarity(self._m.appearance, candidate.appearance))

                if use_appearance and appearance_raw >= self.cfg.appearance_min_similarity:
                    appearance_score = appearance_raw
                    appearance_gate_passed = True
                    total = clamp01(total + self.cfg.appearance_weight * appearance_score)
                    appearance_used = True

            hard_negative_similarity = self._hard_negative_similarity(candidate.appearance)
            hard_negative_margin = float(appearance_raw) - float(hard_negative_similarity)
            hard_negative_reject = (
                self.cfg.hard_negative_memory_enabled
                and hard_negative_similarity >= self.cfg.hard_negative_reject_similarity
                and hard_negative_margin < self.cfg.hard_negative_reject_margin
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
            geometry_allows_appearance=geometry_allows_appearance,
            hard_negative_similarity=hard_negative_similarity,
            hard_negative_margin=hard_negative_margin,
            hard_negative_reject=hard_negative_reject,
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
        memory_update_frozen: bool = False,
        memory_update_freeze_reason: str = "",
    ) -> TargetMemoryOutput:
        previous_state = self._m.state
        previous_id = self._m.track_id
        id_changed = previous_id is not None and candidate.track_id != previous_id
        was_lostish = previous_state in {TargetState.UNCERTAIN, TargetState.LOST}

        reacquired = bool(id_changed or was_lostish)

        self._rank_reacq_candidate_id = None
        self._rank_reacq_confirm_count = 0
        self._reset_absence_reacquisition_confirmation()

        if reacquired:
            self._appearance_update_cooldown_frames_remaining = max(
                self._appearance_update_cooldown_frames_remaining,
                max(0, int(self.cfg.appearance_update_cooldown_after_reacquire_frames)),
            )

        if previous_state == TargetState.REACQUIRED:
            self._m.confirmed_after_reacquire += 1
        elif reacquired:
            self._m.confirmed_after_reacquire = 0

        if self.cfg.appearance_conservative_enabled:
            if not best_score.appearance_used:
                if self.cfg.appearance_conservative_require_appearance:
                    return self._miss(
                        reason="appearance_conservative_reject:no_appearance_used",
                        best_score=best_score,
                        all_scores=all_scores,
                    )
            else:
                appearance_scores = sorted(
                    [
                        s.appearance_raw
                        for s in all_scores
                        if s.appearance_used and s.geometry_allows_appearance
                    ],
                    reverse=True,
                )
                selected_app = best_score.appearance_raw
                second_app = appearance_scores[1] if len(appearance_scores) > 1 else 0.0
                app_margin = selected_app - second_app

                if (
                    selected_app < self.cfg.appearance_conservative_min_similarity
                    or app_margin < self.cfg.appearance_conservative_margin
                ):
                    return self._miss(
                        reason=(
                            "appearance_conservative_reject:"
                            f" selected_app={selected_app:.3f}"
                            f" second_app={second_app:.3f}"
                            f" margin={app_margin:.3f}"
                        ),
                        best_score=best_score,
                        all_scores=all_scores,
                    )

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
        # Optional cooldown prevents learning a newly reacquired wrong target.
        can_update_appearance = (
            new_state == TargetState.LOCKED
            and self._appearance_update_cooldown_frames_remaining <= 0
            and not memory_update_frozen
        )

        if can_update_appearance:
            self._m.appearance = update_feature_memory(
                self._m.appearance,
                candidate.appearance,
                alpha=self.cfg.appearance_update_alpha,
            )
        elif self._appearance_update_cooldown_frames_remaining > 0:
            self._appearance_update_cooldown_frames_remaining -= 1

        return self._make_output(
            reason="accepted_candidate" if not reacquired else "reacquired_candidate",
            visible=(new_state == TargetState.LOCKED),
            reacquired=reacquired,
            best_score=best_score,
            all_scores=all_scores,
            memory_update_frozen=memory_update_frozen,
            memory_update_freeze_reason=memory_update_freeze_reason,
        )

    def _miss(
        self,
        *,
        reason: str,
        best_score: Optional[CandidateScore] = None,
        all_scores: Optional[List[CandidateScore]] = None,
        memory_update_frozen: bool = False,
        memory_update_freeze_reason: str = "",
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
            memory_update_frozen=memory_update_frozen,
            memory_update_freeze_reason=memory_update_freeze_reason,
        )

    def _make_output(
        self,
        *,
        reason: str,
        visible: bool,
        reacquired: bool,
        best_score: Optional[CandidateScore] = None,
        all_scores: Optional[List[CandidateScore]] = None,
        control_mode_override: Optional[ControlMode] = None,
        memory_update_frozen: bool = False,
        memory_update_freeze_reason: str = "",
    ) -> TargetMemoryOutput:
        score_list = all_scores or []

        appearance_margin_best_vs_second = (
            self._appearance_margin(best_score, score_list)
            if best_score is not None
            else 0.0
        )
        geometry_strength = self._geometry_strength(best_score)
        risk_hard_negative = bool(best_score.hard_negative_reject) if best_score is not None else False
        risk_absence = self._absence_risk()
        risk_scene_ambiguity = self._scene_ambiguity_risk(best_score, score_list)

        return TargetMemoryOutput(
            state=self._m.state,
            control_mode=control_mode_override or _control_mode_for_state(self._m.state),
            target_track_id=self._m.track_id,
            bbox=self._m.bbox,
            quality=clamp01(self._m.quality),
            visible=visible,
            reacquired=reacquired,
            frames_since_seen=self._m.frames_since_seen,
            reason=reason,
            best_score=best_score,
            all_scores=score_list,
            memory_update_frozen=memory_update_frozen,
            memory_update_freeze_reason=memory_update_freeze_reason,
            appearance_margin_best_vs_second=appearance_margin_best_vs_second,
            geometry_strength=geometry_strength,
            risk_hard_negative=risk_hard_negative,
            risk_absence=risk_absence,
            risk_scene_ambiguity=risk_scene_ambiguity,
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
