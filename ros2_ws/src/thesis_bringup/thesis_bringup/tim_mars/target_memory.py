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

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

from thesis_bringup.tim_mars.appearance_memory import cosine_similarity, update_feature_memory
from thesis_bringup.tim_mars.appearance_policy import (
    score_with_appearance,
    should_use_appearance,
)
from thesis_bringup.tim_mars.geometry_scoring import (
    bbox_area,
    bbox_centre,
    bbox_iou,
    centre_distance_norm,
    clamp01,
    distance_similarity,
    scale_similarity,
    score_candidate,
)
from thesis_bringup.tim_mars.hard_negative_memory import HardNegativeMemory
from thesis_bringup.tim_mars.memory_state import _Memory, _control_mode_for_state
from thesis_bringup.tim_mars.reacquisition_policy import (
    AbsenceRecoveryConfirmation,
    CandidateBeliefConfirmation,
    RankAwareReacquisitionConfirmation,
    absence_risk,
    appearance_margin,
    geometry_strength,
    scene_ambiguity_risk,
)
from thesis_bringup.tim_mars.types import (
    BBox,
    CandidateScore,
    CandidateTrack,
    ControlMode,
    TargetMemoryConfig,
    TargetMemoryOutput,
    TargetState,
)



@dataclass
class _PreparedUpdate:
    candidates: List[CandidateTrack]
    scores_sorted: List[CandidateScore]
    best: CandidateScore
    second: Optional[CandidateScore]
    best_candidate: CandidateTrack
    same_id: bool
    same_id_score: Optional[CandidateScore]
    same_id_candidate: Optional[CandidateTrack]
    ambiguous: bool


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
        self._rank_reacq_confirmation = RankAwareReacquisitionConfirmation()
        self._absence_reacq_confirmation = AbsenceRecoveryConfirmation()
        self._candidate_belief_confirmation = CandidateBeliefConfirmation()
        self._hard_negative_memory = HardNegativeMemory()

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
        self._rank_reacq_confirmation.reset()
        self._absence_reacq_confirmation.reset()
        self._candidate_belief_confirmation.reset()
        self._hard_negative_memory.clear()
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
        self._rank_reacq_confirmation.reset()
        self._absence_reacq_confirmation.reset()
        self._candidate_belief_confirmation.reset()
        self._hard_negative_memory.clear()
        return self._make_output(reason="operator_select", visible=True, reacquired=False)

    def update(self, candidates: Sequence[CandidateTrack]) -> TargetMemoryOutput:
        """Update target memory from current tracker candidates."""

        if not self._m.selected or self._m.bbox is None:
            return self._make_output(reason="no_operator_selected_target", visible=False, reacquired=False)

        prepared = self._prepare_update_candidates(candidates)
        if prepared is None:
            return self._miss(reason="no_candidates")

        candidates = prepared.candidates
        scores_sorted = prepared.scores_sorted
        best = prepared.best
        second = prepared.second
        best_candidate = prepared.best_candidate
        same_id = prepared.same_id
        ambiguous = prepared.ambiguous
        same_id_score = prepared.same_id_score
        same_id_candidate = prepared.same_id_candidate

        id_switch = best.track_id != self._m.track_id

        short_gap_output = self._handle_short_gap_identity_protection(
            candidates=candidates,
            scores_sorted=scores_sorted,
            best=best,
            same_id_score=same_id_score,
            same_id_candidate=same_id_candidate,
            id_switch=id_switch,
            ambiguous=ambiguous,
        )
        if short_gap_output is not None:
            return short_gap_output

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

        rank_aware_output = self._handle_rank_aware_reacquisition(
            candidates=candidates,
            scores_sorted=scores_sorted,
            best=best,
        )
        if rank_aware_output is not None:
            return rank_aware_output

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
            self._candidate_belief_confirmation.reset()
            return self._miss(
                reason="ambiguous_best_candidate",
                best_score=best,
                all_scores=scores_sorted,
            )

        id_switch = best.track_id != self._m.track_id

        if (
            self.cfg.candidate_belief_enabled
            and id_switch
            and self._m.state in {TargetState.UNCERTAIN, TargetState.LOST}
            and best.total >= self.cfg.candidate_belief_min_score
        ):
            confirm_count = self._candidate_belief_confirmation.observe(int(best.track_id))
            required = max(1, int(self.cfg.candidate_belief_confirm_frames))
            if confirm_count < required:
                return self._miss(
                    reason=(
                        "candidate_belief_confirmation_pending:"
                        f" id={best.track_id}"
                        f" confirm={confirm_count}/{required}"
                        f" score={best.total:.3f}"
                    ),
                    best_score=best,
                    all_scores=scores_sorted,
                )
        else:
            self._candidate_belief_confirmation.reset()

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


        if self._hard_negative_memory.should_reject(best, self.cfg):

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

    def _handle_rank_aware_reacquisition(
        self,
        *,
        candidates: Sequence[CandidateTrack],
        scores_sorted: List[CandidateScore],
        best: CandidateScore,
    ) -> Optional[TargetMemoryOutput]:
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

        return None

    def _handle_short_gap_identity_protection(
        self,
        *,
        candidates: Sequence[CandidateTrack],
        scores_sorted: List[CandidateScore],
        best: CandidateScore,
        same_id_score: Optional[CandidateScore],
        same_id_candidate: Optional[CandidateTrack],
        id_switch: bool,
        ambiguous: bool,
    ) -> Optional[TargetMemoryOutput]:
        short_gap_active = (
            self._m.track_id is not None
            and self._m.frames_since_seen <= max(0, int(self.cfg.short_gap_same_id_grace_frames))
            and self._m.state in {TargetState.LOCKED, TargetState.UNCERTAIN, TargetState.REACQUIRED}
        )

        if (
            self.cfg.short_gap_same_id_priority_enabled
            and short_gap_active
            and self._m.state in {TargetState.UNCERTAIN, TargetState.REACQUIRED}
            and same_id_score is not None
            and same_id_candidate is not None
            and same_id_score.total >= self.cfg.short_gap_same_id_min_total
        ):
            return self._accept(
                same_id_candidate,
                best_score=same_id_score,
                all_scores=scores_sorted,
            )

        short_gap_base_threshold = (
            self.cfg.accept_score_lost
            if self._m.state == TargetState.LOST
            else self.cfg.accept_score_locked
        )

        best_candidate = next(
            (c for c in candidates if int(c.track_id) == int(best.track_id)),
            None,
        )
        best_group_crop_risk = (
            best_candidate is not None
            and self._candidate_group_crop_risk(best_candidate, candidates)
        )

        short_gap_new_id_should_suppress = (
            self._m.state in {TargetState.UNCERTAIN, TargetState.REACQUIRED}
            or (
                self._m.state == TargetState.LOCKED
                and (
                    best.total < self.cfg.short_gap_new_id_allow_total
                    or (
                        best_group_crop_risk
                        and best.total < self.cfg.short_gap_group_risk_allow_total
                    )
                )
            )
        )

        if (
            self.cfg.short_gap_new_id_suppression_enabled
            and self.cfg.allow_id_switch_recovery
            and short_gap_active
            and short_gap_new_id_should_suppress
            and id_switch
            and same_id_score is None
            and not ambiguous
            and best.total >= short_gap_base_threshold
        ):
            return self._miss(
                reason=(
                    "short_gap_new_id_suppressed:"
                    f" id={best.track_id}"
                    f" gap={self._m.frames_since_seen}"
                    f" score={best.total:.3f}"
                ),
                best_score=best,
                all_scores=scores_sorted,
            )

        return None

    def _prepare_update_candidates(
        self,
        candidates: Sequence[CandidateTrack],
    ) -> Optional[_PreparedUpdate]:
        candidates = [c for c in candidates if c.score >= self.cfg.min_candidate_score]
        if not candidates:
            return None

        base_scores = [
            score_candidate(self._m.bbox, c, self._m.track_id, self.cfg)
            for c in candidates
        ]
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

        self._hard_negative_memory.update(
            candidates=candidates,
            scores_sorted=scores_sorted,
            selected_track_id=self._m.track_id,
            positive_appearance=self._m.appearance,
            state=self._m.state,
            cfg=self.cfg,
        )

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

        same_id_score = None
        same_id_candidate = None
        if self._m.track_id is not None:
            for score in scores_sorted:
                if int(score.track_id) != int(self._m.track_id):
                    continue
                same_id_score = score
                same_id_candidate = next(
                    c for c in candidates if int(c.track_id) == int(self._m.track_id)
                )
                break

        return _PreparedUpdate(
            candidates=candidates,
            scores_sorted=scores_sorted,
            best=best,
            second=second,
            best_candidate=best_candidate,
            same_id=same_id,
            same_id_score=same_id_score,
            same_id_candidate=same_id_candidate,
            ambiguous=ambiguous,
        )

    def _rank_aware_app_raw(self, candidate: CandidateTrack, score: CandidateScore) -> float:
        """Appearance evidence for rank-aware reacquisition.

        TIM-V2K intentionally uses the same gated appearance_raw exported in
        diagnostics so live behaviour matches the offline simulator. Geometry
        bypass is a separate future experiment, not the V2K default.
        """
        return float(score.appearance_raw)

    def _appearance_margin(self, selected: CandidateScore, scores_sorted: List[CandidateScore]) -> float:
        return appearance_margin(selected, scores_sorted)

    def _geometry_strength(self, score: Optional[CandidateScore]) -> float:
        return geometry_strength(score)

    def _scene_ambiguity_risk(self, best: Optional[CandidateScore], scores_sorted: List[CandidateScore]) -> bool:
        return scene_ambiguity_risk(
            best=best,
            scores_sorted=scores_sorted,
            cfg=self.cfg,
        )

    def _absence_risk(self) -> bool:
        return absence_risk(
            state=self._m.state,
            frames_since_seen=self._m.frames_since_seen,
            cfg=self.cfg,
        )


    def _reset_absence_reacquisition_confirmation(self) -> None:
        self._absence_reacq_confirmation.reset()


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

        confirm_count = self._absence_reacq_confirmation.observe(int(best.track_id))

        required = max(1, int(self.cfg.absence_confirm_frames))
        if confirm_count < required:
            return (
                "absence_recovery_pending:"
                f" id={best.track_id}"
                f" confirm={confirm_count}/{required}"
                f" app={best.appearance_raw:.3f}"
                f" margin={app_margin:.3f}"
            )

        return None


    def _candidate_group_crop_risk(
        self,
        candidate: CandidateTrack,
        candidates: Sequence[CandidateTrack],
    ) -> bool:
        """Return True when a candidate crop is likely contaminated by nearby people.

        This does not remove the candidate from geometric scoring. It only
        prevents appearance-driven new-ID reacquisition during short-gap
        ambiguity when the crop may contain another person.
        """

        for other in candidates:
            if int(other.track_id) == int(candidate.track_id):
                continue

            overlap = bbox_iou(candidate.bbox, other.bbox)
            distance = centre_distance_norm(
                candidate.bbox,
                other.bbox,
                float(getattr(self.cfg, "image_width", 640.0)),
                float(getattr(self.cfg, "image_height", 640.0)),
            )

            if overlap >= 0.10:
                return True

            if distance <= 0.12:
                return True

        return False


    def _rank_aware_reacquisition_candidate(
        self,
        scores_sorted: List[CandidateScore],
        candidates: Sequence[CandidateTrack],
    ) -> tuple[Optional[CandidateScore], bool]:
        if not self.cfg.rank_aware_reacquisition_enabled:
            return None, False

        if self._m.state not in {TargetState.UNCERTAIN, TargetState.LOST}:
            self._rank_reacq_confirmation.reset()
            return None, False

        by_id = {int(c.track_id): c for c in candidates}
        enriched: list[tuple[CandidateScore, float]] = []

        for score in scores_sorted:
            candidate = by_id.get(int(score.track_id))
            if candidate is None:
                continue

            app_raw = self._rank_aware_app_raw(candidate, score)

            group_crop_gate_active = (
                self._m.track_id is not None
                and self._m.state == TargetState.UNCERTAIN
                and self._m.frames_since_seen <= max(0, int(self.cfg.short_gap_same_id_grace_frames))
            )

            if (
                group_crop_gate_active
                and int(score.track_id) != int(self._m.track_id)
                and self._candidate_group_crop_risk(candidate, candidates)
            ):
                continue

            if (
                score.total >= self.cfg.rank_aware_lost_min_total
                and score.distance >= self.cfg.rank_aware_lost_min_geom
                and app_raw >= self.cfg.rank_aware_lost_min_app
            ):
                enriched.append((score, app_raw))

        if not enriched:
            self._rank_reacq_confirmation.reset()
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
            self._rank_reacq_confirmation.reset()
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
                self._rank_reacq_confirmation.reset()
                return None, False

        confirm_count = self._rank_reacq_confirmation.observe(int(best.track_id))
        pending = confirm_count < max(1, int(self.cfg.rank_aware_confirm_frames))
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

    def _should_use_appearance(self, *, base_ambiguous: bool) -> bool:
        return should_use_appearance(
            cfg=self.cfg,
            positive_appearance=self._m.appearance,
            state_is_lostish=self._m.state in {TargetState.UNCERTAIN, TargetState.LOST, TargetState.REACQUIRED},
            base_ambiguous=base_ambiguous,
        )

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
        return score_with_appearance(
            base=base,
            candidate=candidate,
            positive_appearance=self._m.appearance,
            use_appearance=use_appearance,
            hard_negative_memory=self._hard_negative_memory,
            cfg=self.cfg,
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

        self._rank_reacq_confirmation.reset()
        self._reset_absence_reacquisition_confirmation()
        self._candidate_belief_confirmation.reset()

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
        candidate_track_id = int(best_score.track_id) if best_score is not None else None
        candidate_score = float(best_score.total) if best_score is not None else 0.0
        publication_suppressed_reason = "" if visible else reason

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
            candidate_track_id=candidate_track_id,
            candidate_score=candidate_score,
            publication_suppressed_reason=publication_suppressed_reason,
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
