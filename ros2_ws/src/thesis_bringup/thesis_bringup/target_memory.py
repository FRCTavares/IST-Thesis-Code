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
    appearance_raw: float = 0.0
    appearance_gate_passed: bool = False
    geometry_allows_appearance: bool = False
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

    # Freeze appearance memory updates after risky reacquisition / ID switch.
    # Default 0 preserves previous behaviour.
    appearance_update_cooldown_after_reacquire_frames: int = 0

    # TIM-V1 experimental safety gate.
    # When enabled, a strong appearance challenger can force UNCERTAIN
    # instead of allowing geometry to keep a wrong LOCKED target.
    appearance_challenge_enabled: bool = False
    appearance_challenge_min_similarity: float = 0.50
    appearance_challenge_margin: float = 0.20
    appearance_challenge_min_total: float = 0.45

    # TIM-MARS conservative output filter.
    # When enabled, a candidate must have strong and separated appearance evidence.
    appearance_conservative_enabled: bool = False
    appearance_conservative_min_similarity: float = 0.65
    appearance_conservative_margin: float = 0.25

    # TIM-V2K experimental rank-aware LOST/UNCERTAIN reacquisition.
    # Disabled by default to preserve TIM-V1 behaviour.
    rank_aware_reacquisition_enabled: bool = False
    rank_aware_lost_min_total: float = 0.40
    rank_aware_lost_min_geom: float = 0.10
    rank_aware_lost_min_app: float = 0.05
    rank_aware_lost_app_margin: float = 0.03
    rank_aware_confirm_frames: int = 1
    rank_aware_missing_ttl_frames: int = 8


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
        self._appearance_update_cooldown_frames_remaining = 0
        self._rank_reacq_candidate_id: Optional[int] = None
        self._rank_reacq_confirm_count = 0

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
            appearance_raw=best.appearance_raw,
            appearance_gate_passed=best.appearance_gate_passed,
            geometry_allows_appearance=best.geometry_allows_appearance,
            ambiguous=ambiguous,
        )
        scores_sorted[0] = best

        rank_aware_best, rank_aware_pending = self._rank_aware_reacquisition_candidate(
            scores_sorted,
            candidates,
        )
        if rank_aware_best is not None:
            rank_candidate = next(c for c in candidates if c.track_id == rank_aware_best.track_id)
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

        if best.track_id != self._m.track_id and not self.cfg.allow_id_switch_recovery:
            return self._miss(
                reason="id_switch_recovery_disabled",
                best_score=best,
                all_scores=scores_sorted,
            )

        if self._appearance_challenge_should_hold(best, scores_sorted, same_id=same_id):
            return self._miss(
                reason="appearance_challenge_uncertain",
                best_score=best,
                all_scores=scores_sorted,
            )

        return self._accept(best_candidate, best_score=best, all_scores=scores_sorted)

    def _rank_aware_app_raw(self, candidate: CandidateTrack, score: CandidateScore) -> float:
        """Appearance evidence for rank-aware reacquisition.

        TIM-V2K intentionally uses the same gated appearance_raw exported in
        diagnostics so live behaviour matches the offline simulator. Geometry
        bypass is a separate future experiment, not the V2K default.
        """
        return float(score.appearance_raw)

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
            ambiguous=best.ambiguous,
        )
        return best, False

    def _appearance_challenge_should_hold(
        self,
        best: CandidateScore,
        scores_sorted: List[CandidateScore],
        *,
        same_id: bool,
    ) -> bool:
        if not self.cfg.appearance_challenge_enabled:
            return False

        if self._m.state not in {TargetState.LOCKED, TargetState.REACQUIRED}:
            return False

        if not same_id:
            return False

        if self._m.track_id is None:
            return False

        challengers = [s for s in scores_sorted if int(s.track_id) != int(self._m.track_id)]

        if not challengers:
            return False

        challenger = max(challengers, key=lambda s: float(s.appearance_raw))

        if not challenger.geometry_allows_appearance:
            return False

        if challenger.total < self.cfg.appearance_challenge_min_total:
            return False

        if challenger.appearance_raw < self.cfg.appearance_challenge_min_similarity:
            return False

        if (challenger.appearance_raw - best.appearance_raw) < self.cfg.appearance_challenge_margin:
            return False

        return True

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
        appearance_raw = 0.0
        appearance_used = False
        appearance_gate_passed = False
        total = base.total

        # Appearance is only a tie-breaker inside a geometrically plausible region.
        # It must not rescue candidates that are far from the predicted target memory.
        geometry_allows_appearance = (
            base.iou > 0.0
            or (base.distance >= 0.25 and base.scale >= 0.35)
        )

        if candidate.appearance is not None and geometry_allows_appearance and self._m.appearance is not None:
            appearance_raw = clamp01(cosine_similarity(self._m.appearance, candidate.appearance))
            if use_appearance and appearance_raw >= self.cfg.appearance_min_similarity:
                appearance_score = appearance_raw
                appearance_gate_passed = True
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
            appearance_raw=appearance_raw,
            appearance_gate_passed=appearance_gate_passed,
            geometry_allows_appearance=geometry_allows_appearance,
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

        self._rank_reacq_candidate_id = None
        self._rank_reacq_confirm_count = 0

        if reacquired:
            self._appearance_update_cooldown_frames_remaining = max(
                self._appearance_update_cooldown_frames_remaining,
                max(0, int(self.cfg.appearance_update_cooldown_after_reacquire_frames)),
            )

        if previous_state == TargetState.REACQUIRED:
            self._m.confirmed_after_reacquire += 1
        elif reacquired:
            self._m.confirmed_after_reacquire = 0

        if self.cfg.appearance_conservative_enabled and best_score.appearance_used:
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
