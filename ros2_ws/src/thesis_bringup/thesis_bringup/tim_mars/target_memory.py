"""Core selected-target memory state machine for TIM-MARS.

TargetIdentityMemory is the pure algorithmic core of TIM-MARS. It receives
CandidateTrack objects and returns a conservative TargetMemoryOutput describing
whether the selected target should be published, suppressed, marked uncertain,
or reacquired.

The state machine combines tracker identity, bbox geometry, temporal memory,
optional MARS appearance evidence, hard-negative memory, short-gap protection,
absence-aware recovery, and rank-aware reacquisition. It has no ROS dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import (
    List,
    Optional,
    Sequence,
)

from thesis_bringup.tim_mars.appearance_memory import update_feature_memory
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
from thesis_bringup.tim_mars.memory_state import (
    _control_mode_for_state,
    _Memory,
)
from thesis_bringup.tim_mars.positive_appearance_memory import PositiveAppearanceMemory
from thesis_bringup.tim_mars.reacquisition_policy import (
    absence_risk,
    appearance_margin,
    CandidatePersistenceTracker,
    geometry_strength,
    scene_ambiguity_risk,
)
from thesis_bringup.tim_mars.types import (
    BBox,
    CandidateScore,
    CandidateTrack,
    ControlMode,
    HardNegativeMemoryEvent,
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


class _ProposalVerdictStatus(str, Enum):
    ACCEPTED = 'accepted'
    REJECTED = 'rejected'
    PENDING = 'pending'


@dataclass(frozen=True)
class _ConfirmationRequirement:
    policy: str
    required: int
    count: int


@dataclass(frozen=True)
class _CandidateProposal:
    candidate: CandidateTrack
    score: CandidateScore
    all_scores: tuple[CandidateScore, ...]
    candidates: tuple[CandidateTrack, ...]
    proposal_source: str
    previous_tracker_id: Optional[int]
    proposed_tracker_id: int
    same_id: bool
    id_switch: bool
    confirmations: tuple[_ConfirmationRequirement, ...]
    minimum_total: float
    minimum_total_reason: str
    evidence_available: tuple[str, ...]
    memory_update_eligible: bool
    diagnostic_reason: str


@dataclass(frozen=True)
class _ProposalVerdict:
    status: _ProposalVerdictStatus
    reason: str


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
        self._candidate_persistence = CandidatePersistenceTracker()
        self._hard_negative_memory = HardNegativeMemory()
        self._positive_appearance = PositiveAppearanceMemory()
        self._last_acceptance_memory_source = "none"
        self._last_positive_memory_updated = False
        self._last_positive_memory_update_reason = ""
        self._last_hard_negative_events: tuple[
            HardNegativeMemoryEvent,
            ...,
        ] = ()

    @property
    def state(self) -> TargetState:
        return self._m.state

    @property
    def target_track_id(self) -> Optional[int]:
        return self._m.track_id

    @property
    def bbox(self) -> Optional[BBox]:
        return self._m.bbox

    @property
    def _rank_reacq_confirmation(
        self,
    ) -> CandidatePersistenceTracker:
        """Temporary compatibility view of the unified tracker."""
        return self._candidate_persistence

    @property
    def _absence_reacq_confirmation(
        self,
    ) -> CandidatePersistenceTracker:
        """Temporary compatibility view of the unified tracker."""
        return self._candidate_persistence

    @property
    def _candidate_belief_confirmation(
        self,
    ) -> CandidatePersistenceTracker:
        """Temporary compatibility view of the unified tracker."""
        return self._candidate_persistence

    @property
    def appearance_update_cooldown_frames_remaining(self) -> int:
        """Remaining frames before positive appearance updates resume."""
        return int(self._appearance_update_cooldown_frames_remaining)

    def _reset_positive_memory_diagnostics(self) -> None:
        self._last_acceptance_memory_source = "none"
        self._last_positive_memory_updated = False
        self._last_positive_memory_update_reason = ""

    def _reset_hard_negative_diagnostics(self) -> None:
        self._last_hard_negative_events = ()

    def clear(self) -> TargetMemoryOutput:
        self._reset_positive_memory_diagnostics()
        self._reset_hard_negative_diagnostics()
        self._m = _Memory()
        self._appearance_update_cooldown_frames_remaining = 0
        self._candidate_persistence.reset()
        self._hard_negative_memory.clear()
        self._positive_appearance.clear()

        return self._make_output(
            reason="operator_clear",
            visible=False,
            reacquired=False,
        )

    def select(
        self,
        track: CandidateTrack,
    ) -> TargetMemoryOutput:
        """Operator selects a visible track as the active target."""
        self._reset_positive_memory_diagnostics()
        self._reset_hard_negative_diagnostics()

        selected_appearance = (
            track.appearance
            if track.appearance_memory_update_eligible
            else None
        )
        protected_mode = bool(
            self.cfg.appearance_protected_memory_enabled
        )

        self._m = _Memory(
            selected=True,
            state=TargetState.LOCKED,
            track_id=track.track_id,
            bbox=track.bbox,
            quality=clamp01(track.score),
            frames_since_seen=0,
            appearance=(
                None
                if protected_mode
                else update_feature_memory(
                    None,
                    selected_appearance,
                    alpha=1.0,
                )
            ),
        )

        self._positive_appearance.clear()

        if protected_mode:
            initialised = (
                self._positive_appearance.select_operator(
                    track_id=track.track_id,
                    appearance=selected_appearance,
                )
            )
            self._last_acceptance_memory_source = (
                "operator_selection"
            )
            self._last_positive_memory_updated = bool(
                initialised
            )
            if initialised:
                self._last_positive_memory_update_reason = (
                    "operator_anchor_initialised"
                )

        self._appearance_update_cooldown_frames_remaining = 0
        self._candidate_persistence.reset()
        self._hard_negative_memory.clear()

        return self._make_output(
            reason="operator_select",
            visible=True,
            reacquired=False,
        )

    def update(
        self,
        candidates: Sequence[CandidateTrack],
    ) -> TargetMemoryOutput:
        """Update target memory from current tracker candidates."""
        self._reset_positive_memory_diagnostics()
        self._reset_hard_negative_diagnostics()

        if not self._m.selected or self._m.bbox is None:
            return self._make_output(
                reason='no_operator_selected_target',
                visible=False,
                reacquired=False,
            )

        prepared = self._prepare_update_candidates(candidates)
        if prepared is None:
            self._reset_confirmation_trackers_except(set())
            return self._miss(reason='no_candidates')

        candidates = prepared.candidates
        scores_sorted = prepared.scores_sorted
        best = prepared.best
        best_candidate = prepared.best_candidate
        same_id = prepared.same_id
        same_id_score = prepared.same_id_score
        same_id_candidate = prepared.same_id_candidate

        id_switch = best.track_id != self._m.track_id

        short_gap_proposal, short_gap_output = (
            self._handle_short_gap_identity_protection(
                candidates=candidates,
                scores_sorted=scores_sorted,
                best=best,
                same_id_score=same_id_score,
                same_id_candidate=same_id_candidate,
                id_switch=id_switch,
                ambiguous=prepared.ambiguous,
            )
        )
        if short_gap_output is not None:
            self._reset_confirmation_trackers_except(set())
            return short_gap_output
        if short_gap_proposal is not None:
            return self._finalize_candidate_proposal(
                short_gap_proposal
            )

        rank_proposal, rank_output = (
            self._handle_rank_aware_reacquisition(
                candidates=candidates,
                scores_sorted=scores_sorted,
                best=best,
            )
        )
        if rank_output is not None:
            self._reset_confirmation_trackers_except(set())
            return rank_output
        if rank_proposal is not None:
            return self._finalize_candidate_proposal(
                rank_proposal
            )

        threshold = (
            self.cfg.accept_score_lost
            if self._m.state == TargetState.LOST
            else self.cfg.accept_score_locked
        )
        if same_id:
            threshold = max(
                0.0,
                threshold - self.cfg.same_id_accept_relief,
            )

        proposal = self._make_candidate_proposal(
            candidate=best_candidate,
            score=best,
            all_scores=scores_sorted,
            candidates=candidates,
            proposal_source='normal_selection',
            diagnostic_reason='normal_candidate',
            minimum_total=threshold,
            minimum_total_reason=(
                'best_below_threshold:'
                f'{best.geometry_score:.3f}<{threshold:.3f}'
            ),
        )
        return self._finalize_candidate_proposal(proposal)

    def _make_candidate_proposal(
        self,
        *,
        candidate: CandidateTrack,
        score: CandidateScore,
        all_scores: Sequence[CandidateScore],
        candidates: Sequence[CandidateTrack],
        proposal_source: str,
        diagnostic_reason: str,
        minimum_total: float = 0.0,
        minimum_total_reason: str = '',
        confirmation_requirements: Sequence[
            tuple[str, int]
        ] = (),
    ) -> _CandidateProposal:
        previous_tracker_id = self._m.track_id
        same_id = bool(
            previous_tracker_id is not None
            and int(candidate.track_id)
            == int(previous_tracker_id)
        )
        id_switch = bool(
            previous_tracker_id is not None
            and int(candidate.track_id)
            != int(previous_tracker_id)
        )

        confirmation_options = list(
            tuple(confirmation_requirements)
            + self._candidate_belief_confirmation_requirements(
                best=score,
                id_switch=id_switch,
            )
        )

        if self._absence_confirmation_applies(
            id_switch=id_switch,
        ):
            confirmation_options.append(
                (
                    'absence_recovery',
                    max(
                        1,
                        int(self.cfg.absence_confirm_frames),
                    ),
                )
            )

        recovery_proposal = bool(
            id_switch
            or self._m.state
            in {
                TargetState.UNCERTAIN,
                TargetState.LOST,
                TargetState.REACQUIRED,
            }
        )
        if recovery_proposal:
            confirmation_options.append(
                (
                    'recovery_persistence',
                    1
                    + max(
                        0,
                        int(
                            self.cfg
                            .min_confirm_frames_after_reacquire
                        ),
                    ),
                )
            )

        if confirmation_options:
            policy, required = max(
                (
                    (
                        str(policy_name),
                        max(1, int(required_count)),
                    )
                    for policy_name, required_count
                    in confirmation_options
                ),
                key=lambda item: item[1],
            )
            confirmations = (
                _ConfirmationRequirement(
                    policy=policy,
                    required=required,
                    count=self._preview_confirmation_count(
                        int(candidate.track_id),
                    ),
                ),
            )
        else:
            confirmations = ()

        evidence = ['geometry']
        if candidate.appearance is not None:
            evidence.append('appearance')
        if candidate.appearance_crop_quality is not None:
            evidence.append('crop_quality')
        if score.hard_negative_similarity > 0.0:
            evidence.append('hard_negative')
        if score.protected_anchor_similarity > 0.0:
            evidence.append('protected_anchor')
        if score.adaptive_similarity > 0.0:
            evidence.append('adaptive_appearance')

        return _CandidateProposal(
            candidate=candidate,
            score=score,
            all_scores=tuple(all_scores),
            candidates=tuple(candidates),
            proposal_source=str(proposal_source),
            previous_tracker_id=previous_tracker_id,
            proposed_tracker_id=int(candidate.track_id),
            same_id=same_id,
            id_switch=id_switch,
            confirmations=confirmations,
            minimum_total=max(0.0, float(minimum_total)),
            minimum_total_reason=str(minimum_total_reason),
            evidence_available=tuple(evidence),
            memory_update_eligible=bool(
                candidate.appearance_memory_update_eligible
            ),
            diagnostic_reason=str(diagnostic_reason),
        )

    def _preview_confirmation_count(
        self,
        track_id: int,
    ) -> int:
        return self._candidate_persistence.preview(
            int(track_id)
        )

    def _reset_confirmation_trackers_except(
        self,
        active: set[str],
    ) -> None:
        if not active:
            self._candidate_persistence.reset()

    def _proposal_pending_reason(
        self,
        proposal: _CandidateProposal,
        requirement: _ConfirmationRequirement,
    ) -> str:
        if requirement.policy == 'candidate_belief':
            return (
                'candidate_belief_confirmation_pending:'
                f' id={proposal.proposed_tracker_id}'
                f' confirm={requirement.count}/'
                f'{requirement.required}'
                f' score={proposal.score.total:.3f}'
            )

        if requirement.policy == 'absence_recovery':
            app_margin = self._appearance_margin(
                proposal.score,
                list(proposal.all_scores),
            )
            return (
                'absence_recovery_pending:'
                f' id={proposal.proposed_tracker_id}'
                f' confirm={requirement.count}/'
                f'{requirement.required}'
                f' app={proposal.score.appearance_raw:.3f}'
                f' margin={app_margin:.3f}'
            )

        if (
            requirement.policy
            == 'rank_aware_reacquisition'
        ):
            return (
                'rank_aware_reacquisition_pending:'
                f' id={proposal.proposed_tracker_id}'
                f' confirm={requirement.count}/'
                f'{requirement.required}'
            )

        if requirement.policy == 'recovery_persistence':
            return (
                'recovery_persistence_pending:'
                f' id={proposal.proposed_tracker_id}'
                f' confirm={requirement.count}/'
                f'{requirement.required}'
            )

        return (
            f'{proposal.proposal_source}_pending:'
            f' id={proposal.proposed_tracker_id}'
            f' confirm={requirement.count}/'
            f'{requirement.required}'
        )

    def _commit_confirmation_state(
        self,
        proposal: _CandidateProposal,
        verdict: _ProposalVerdict,
    ) -> None:
        if verdict.status == _ProposalVerdictStatus.REJECTED:
            self._candidate_persistence.reset()
            return

        if not proposal.confirmations:
            self._candidate_persistence.reset()
            return

        if len(proposal.confirmations) != 1:
            raise RuntimeError(
                'Unified candidate persistence requires exactly '
                'one confirmation requirement.'
            )

        requirement = proposal.confirmations[0]
        observed = self._candidate_persistence.observe(
            proposal.proposed_tracker_id,
            required_observations=requirement.required,
            source=requirement.policy,
            bbox=proposal.candidate.bbox,
            score=proposal.score.total,
            identity_evidence_confirmed=bool(
                proposal.candidate.appearance is not None
                and proposal.score.appearance_evaluated
                and (
                    proposal.score
                    .appearance_similarity_passed
                )
            ),
        )

        if observed != requirement.count:
            raise RuntimeError(
                'Confirmation preview diverged from commit: '
                f'{observed}!={requirement.count}'
            )

    @staticmethod
    def _proposal_reject_reason(
        proposal: _CandidateProposal,
        reason: str,
    ) -> str:
        """Preserve source-specific diagnostics without bypassing the gate."""
        if (
            proposal.proposal_source
            == 'rank_aware_reacquisition'
            and reason.startswith(
                (
                    'id_switch_recovery_reject:',
                    'id_switch_spatial_reject:',
                    'hard_negative_reject:',
                )
            )
        ):
            return 'rank_aware_' + reason

        return reason

    def _evaluate_candidate_proposal(
        self,
        proposal: _CandidateProposal,
    ) -> _ProposalVerdict:
        absence_reject = (
            self._absence_aware_reacquisition_reject_reason(
                proposal
            )
        )
        if absence_reject is not None:
            return _ProposalVerdict(
                _ProposalVerdictStatus.REJECTED,
                absence_reject,
            )

        if (
            proposal.score.geometry_score
            < proposal.minimum_total
        ):
            reason = (
                proposal.minimum_total_reason
                or (
                    f'{proposal.proposal_source}_'
                    'below_threshold:'
                    f'{proposal.score.geometry_score:.3f}'
                    f'<{proposal.minimum_total:.3f}'
                )
            )
            return _ProposalVerdict(
                _ProposalVerdictStatus.REJECTED,
                reason,
            )

        same_id_reject = (
            self._same_id_reacquisition_appearance_reject_reason(
                candidate=proposal.candidate,
            )
        )
        if same_id_reject is not None:
            return _ProposalVerdict(
                _ProposalVerdictStatus.REJECTED,
                same_id_reject,
            )

        same_id_hijack_reject = (
            self._same_id_hijack_reject_reason(proposal)
        )
        if same_id_hijack_reject is not None:
            return _ProposalVerdict(
                _ProposalVerdictStatus.REJECTED,
                same_id_hijack_reject,
            )

        id_switch_appearance_reject = (
            self._id_switch_appearance_reject_reason(
                candidate=proposal.candidate,
                score=proposal.score,
                id_switch=proposal.id_switch,
            )
        )
        if id_switch_appearance_reject is not None:
            return _ProposalVerdict(
                _ProposalVerdictStatus.REJECTED,
                self._proposal_reject_reason(
                    proposal,
                    id_switch_appearance_reject,
                ),
            )

        if proposal.score.ambiguous:
            return _ProposalVerdict(
                _ProposalVerdictStatus.REJECTED,
                'ambiguous_best_candidate',
            )

        if (
            proposal.id_switch
            and not self.cfg.allow_id_switch_recovery
        ):
            return _ProposalVerdict(
                _ProposalVerdictStatus.REJECTED,
                'id_switch_recovery_disabled',
            )

        if (
            proposal.id_switch
            and self.cfg.id_switch_spatial_gate_enabled
        ):
            spatial_ok = (
                proposal.score.iou
                >= self.cfg.id_switch_min_iou
                or (
                    proposal.score.distance
                    >= self.cfg.id_switch_min_distance
                    and proposal.score.scale
                    >= self.cfg.id_switch_min_scale
                )
            )
            if not spatial_ok:
                reason = (
                    'id_switch_spatial_reject:'
                    f' iou={proposal.score.iou:.3f}'
                    f' distance={proposal.score.distance:.3f}'
                    f' scale={proposal.score.scale:.3f}'
                )
                return _ProposalVerdict(
                    _ProposalVerdictStatus.REJECTED,
                    self._proposal_reject_reason(
                        proposal,
                        reason,
                    ),
                )

        hard_negative_reject = (
            self._hard_negative_memory.should_reject(
                proposal.score,
                self.cfg,
            )
        )
        trusted_same_id_continuity = bool(
            self.cfg.same_id_hijack_protection_enabled
            and proposal.same_id
            and self._m.state == TargetState.LOCKED
        )
        if (
            hard_negative_reject
            and not trusted_same_id_continuity
        ):
            reason = (
                'hard_negative_reject:'
                f' neg={proposal.score.hard_negative_similarity:.3f}'
                f' margin={proposal.score.hard_negative_margin:.3f}'
            )
            return _ProposalVerdict(
                _ProposalVerdictStatus.REJECTED,
                self._proposal_reject_reason(
                    proposal,
                    reason,
                ),
            )

        previous_state = self._m.state
        reacquired = bool(
            proposal.id_switch
            or previous_state
            in {
                TargetState.UNCERTAIN,
                TargetState.LOST,
            }
        )

        gallery_reject = (
            self._protected_gallery_reacquisition_reject_reason(
                candidate=proposal.candidate,
                score=proposal.score,
                reacquired=reacquired,
            )
        )
        if gallery_reject is not None:
            return _ProposalVerdict(
                _ProposalVerdictStatus.REJECTED,
                gallery_reject,
            )

        conservative_reject = (
            self._appearance_conservative_reject_reason(
                best_score=proposal.score,
                all_scores=list(proposal.all_scores),
            )
        )
        if conservative_reject is not None:
            return _ProposalVerdict(
                _ProposalVerdictStatus.REJECTED,
                conservative_reject,
            )

        for requirement in proposal.confirmations:
            if requirement.count < requirement.required:
                return _ProposalVerdict(
                    _ProposalVerdictStatus.PENDING,
                    self._proposal_pending_reason(
                        proposal,
                        requirement,
                    ),
                )

        return _ProposalVerdict(
            _ProposalVerdictStatus.ACCEPTED,
            proposal.diagnostic_reason,
        )

    def _finalize_candidate_proposal(
        self,
        proposal: _CandidateProposal,
    ) -> TargetMemoryOutput:
        verdict = self._evaluate_candidate_proposal(proposal)
        self._commit_confirmation_state(
            proposal,
            verdict,
        )

        if verdict.status == _ProposalVerdictStatus.REJECTED:
            return self._miss(
                reason=verdict.reason,
                best_score=proposal.score,
                all_scores=list(proposal.all_scores),
            )

        if verdict.status == _ProposalVerdictStatus.PENDING:
            trusted_continuity_broken = bool(
                self._m.state != TargetState.LOCKED
                or proposal.id_switch
            )
            if trusted_continuity_broken:
                self._last_hard_negative_events = (
                    self._hard_negative_memory.discard_pending(
                        selected_track_id=self._m.track_id,
                    )
                )

            return self._make_output(
                reason=verdict.reason,
                visible=False,
                reacquired=True,
                best_score=proposal.score,
                all_scores=list(proposal.all_scores),
                state_override=TargetState.REACQUIRED,
                control_mode_override=ControlMode.CONFIRM,
            )

        return self._accept(
            proposal.candidate,
            best_score=proposal.score,
            all_scores=list(proposal.all_scores),
            candidates=proposal.candidates,
        )

    def _same_id_reacquisition_appearance_reject_reason(
        self,
        *,
        candidate: CandidateTrack,
    ) -> Optional[str]:
        """Require identity evidence when restoring an untrusted lineage.

        Same-ID geometry may maintain uninterrupted LOCKED continuity. It may
        also complete a REACQUIRED confirmation because entry to REACQUIRED
        has already passed the applicable appearance-evidence gates. A same-ID
        return from UNCERTAIN or LOST remains untrusted and requires an actual
        candidate embedding while appearance mode is active.
        """
        if not self.cfg.appearance_enabled:
            return None

        if self._m.state in {
            TargetState.LOCKED,
            TargetState.REACQUIRED,
        }:
            return None

        if self._m.track_id is None:
            return None

        if int(candidate.track_id) != int(self._m.track_id):
            return None

        if candidate.appearance is not None:
            return None

        return (
            'same_id_reacquisition_reject:'
            'no_candidate_appearance'
        )

    def _same_id_hijack_reject_reason(
        self,
        proposal: _CandidateProposal,
    ) -> Optional[str]:
        """Challenge same-ID continuity only during a plausible person handover.

        Tracker IDs are normally strong temporal evidence. A hard-negative
        prototype alone must not suppress an uninterrupted, geometrically
        stable target because pose changes can resemble a nearby distractor.
        Conversely, the same tracker ID is no longer sufficient when another
        person is both spatially plausible relative to target memory and close
        enough to contaminate the selected crop. In that narrow case, current
        positive appearance must independently validate the same-ID candidate.
        """
        if (
            not self.cfg.same_id_hijack_protection_enabled
            or not self.cfg.appearance_enabled
            or not proposal.same_id
            or self._m.state != TargetState.LOCKED
        ):
            return None

        challenger = self._same_id_group_challenger(
            proposal
        )
        if challenger is None:
            return None

        threshold = self._id_switch_appearance_threshold()
        identity_supported = bool(
            threshold > 0.0
            and proposal.score.appearance_evaluated
            and proposal.score.appearance_raw >= threshold
            and not proposal.score.hard_negative_reject
        )
        if identity_supported:
            return None

        if proposal.score.hard_negative_reject:
            evidence = (
                'hard_negative'
                f' neg={proposal.score.hard_negative_similarity:.3f}'
                f' margin={proposal.score.hard_negative_margin:.3f}'
            )
        elif not proposal.score.appearance_evaluated:
            evidence = 'no_current_appearance'
        else:
            evidence = (
                'appearance'
                f' {proposal.score.appearance_raw:.3f}'
                f'<{threshold:.3f}'
            )

        return (
            'same_id_hijack_reject:'
            f' challenger={challenger.track_id}'
            f' {evidence}'
        )

    def _same_id_group_challenger(
        self,
        proposal: _CandidateProposal,
    ) -> Optional[CandidateScore]:
        """Return a nearby new-ID candidate plausible relative to target memory."""
        scores_by_id = {
            int(score.track_id): score
            for score in proposal.all_scores
        }
        width = float(
            getattr(self.cfg, 'image_width', 640.0)
        )
        height = float(
            getattr(self.cfg, 'image_height', 640.0)
        )

        for candidate in proposal.candidates:
            if (
                int(candidate.track_id)
                == int(proposal.candidate.track_id)
            ):
                continue

            score = scores_by_id.get(
                int(candidate.track_id)
            )
            if score is None:
                continue

            group_close = bool(
                bbox_iou(
                    proposal.candidate.bbox,
                    candidate.bbox,
                ) >= 0.10
                or centre_distance_norm(
                    proposal.candidate.bbox,
                    candidate.bbox,
                    width,
                    height,
                ) <= 0.12
            )
            if not group_close:
                continue

            spatially_plausible = bool(
                score.geometry_score
                >= self.cfg.min_candidate_score
                and (
                    score.iou
                    >= self.cfg.id_switch_min_iou
                    or (
                        score.distance
                        >= self.cfg.id_switch_min_distance
                        and score.scale
                        >= self.cfg.id_switch_min_scale
                    )
                )
            )
            if spatially_plausible:
                return score

        return None

    def _id_switch_appearance_reject_reason(
        self,
        *,
        candidate: CandidateTrack,
        score: CandidateScore,
        id_switch: bool,
    ) -> Optional[str]:
        """Return why appearance evidence cannot authorize a tracker-ID change."""
        if (
            not id_switch
            or not self.cfg.allow_id_switch_recovery
            or not self.cfg.appearance_enabled
        ):
            return None

        if candidate.appearance is None:
            same_pending_candidate = bool(
                self._candidate_persistence.candidate_id
                == int(candidate.track_id)
            )
            if (
                same_pending_candidate
                and self._candidate_persistence
                .identity_evidence_confirmed
            ):
                return None

            return (
                'id_switch_recovery_reject:'
                'no_candidate_appearance'
            )

        threshold = self._id_switch_appearance_threshold()

        if threshold <= 0.0:
            return None

        if not score.appearance_evaluated:
            return (
                'id_switch_recovery_reject:'
                'appearance_not_evaluated'
            )

        if float(score.appearance_raw) < threshold:
            return (
                'id_switch_recovery_reject:'
                'appearance'
                f' {score.appearance_raw:.3f}'
                f'<{threshold:.3f}'
            )

        return None

    def _id_switch_appearance_threshold(self) -> float:
        """Return the independent identity threshold for a tracker-ID change."""
        threshold = max(
            0.0,
            float(
                self.cfg
                .id_switch_min_appearance_similarity
            ),
        )
        if self.cfg.appearance_conservative_enabled:
            threshold = max(
                threshold,
                float(
                    self.cfg
                    .appearance_conservative_min_similarity
                ),
            )

        return threshold

    def _appearance_validates_id_switch(
        self,
        score: CandidateScore,
    ) -> bool:
        """Return whether appearance independently authorizes an ID switch."""
        threshold = self._id_switch_appearance_threshold()
        return bool(
            threshold > 0.0
            and score.appearance_evaluated
            and float(score.appearance_raw) >= threshold
        )

    def _protected_gallery_reacquisition_reject_reason(
        self,
        *,
        candidate: CandidateTrack,
        score: CandidateScore,
        reacquired: bool,
    ) -> Optional[str]:
        """Validate gallery-only support for a risky reacquisition.

        A single trusted-gallery exemplar must not independently authorize a
        new or recovered lineage when the current crop is unsuitable for
        identity memory, the candidate is ambiguous, or the immutable operator
        anchor does not provide the configured minimum agreement.
        """
        if (
            not reacquired
            or not self.cfg.appearance_protected_memory_enabled
            or score.positive_support_source != 'trusted_gallery'
        ):
            return None

        if not candidate.appearance_memory_update_eligible:
            return (
                'protected_gallery_reacquisition_reject:'
                'untrusted_crop'
            )

        if score.ambiguous:
            return (
                'protected_gallery_reacquisition_reject:'
                'ambiguous_candidate'
            )

        anchor_threshold = max(
            0.0,
            float(
                self.cfg
                .appearance_gallery_min_anchor_similarity
            ),
        )

        if (
            anchor_threshold > 0.0
            and float(
                score.protected_anchor_similarity
            ) < anchor_threshold
        ):
            return (
                'protected_gallery_reacquisition_reject:'
                'anchor'
                f' {score.protected_anchor_similarity:.3f}'
                f'<{anchor_threshold:.3f}'
            )

        return None

    def _candidate_belief_confirmation_requirements(
        self,
        *,
        best: CandidateScore,
        id_switch: bool,
    ) -> tuple[tuple[str, int], ...]:
        if (
            self.cfg.candidate_belief_enabled
            and id_switch
            and self._m.state
            in {
                TargetState.UNCERTAIN,
                TargetState.LOST,
            }
            and best.geometry_score
            >= self.cfg.candidate_belief_min_score
        ):
            return (
                (
                    'candidate_belief',
                    max(
                        1,
                        int(
                            self.cfg
                            .candidate_belief_confirm_frames
                        ),
                    ),
                ),
            )

        return ()

    def _handle_rank_aware_reacquisition(
        self,
        *,
        candidates: Sequence[CandidateTrack],
        scores_sorted: List[CandidateScore],
        best: CandidateScore,
    ) -> tuple[
        Optional[_CandidateProposal],
        Optional[TargetMemoryOutput],
    ]:
        rank_aware_best = (
            self._rank_aware_reacquisition_candidate(
                scores_sorted,
                candidates,
            )
        )

        if rank_aware_best is None:
            return None, None

        rank_candidate = next(
            candidate
            for candidate in candidates
            if candidate.track_id
            == rank_aware_best.track_id
        )

        required = max(
            1,
            int(self.cfg.rank_aware_confirm_frames),
        )
        proposal = self._make_candidate_proposal(
            candidate=rank_candidate,
            score=rank_aware_best,
            all_scores=scores_sorted,
            candidates=candidates,
            proposal_source='rank_aware_reacquisition',
            diagnostic_reason=(
                'rank_aware_reacquisition_candidate'
            ),
            minimum_total=(
                self.cfg.rank_aware_lost_min_total
            ),
            minimum_total_reason=(
                'rank_aware_reacquisition_reject:total'
            ),
            confirmation_requirements=(
                (
                    'rank_aware_reacquisition',
                    required,
                ),
            ),
        )
        return proposal, None

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
    ) -> tuple[
        Optional[_CandidateProposal],
        Optional[TargetMemoryOutput],
    ]:
        short_gap_active = (
            self._m.track_id is not None
            and self._m.frames_since_seen
            <= max(
                0,
                int(
                    self.cfg.short_gap_same_id_grace_frames
                ),
            )
            and self._m.state
            in {
                TargetState.LOCKED,
                TargetState.UNCERTAIN,
                TargetState.REACQUIRED,
            }
        )

        if (
            self.cfg.short_gap_same_id_priority_enabled
            and short_gap_active
            and self._m.state
            in {
                TargetState.UNCERTAIN,
                TargetState.REACQUIRED,
            }
            and same_id_score is not None
            and same_id_candidate is not None
            and same_id_score.geometry_score
            >= self.cfg.short_gap_same_id_min_total
        ):
            proposal = self._make_candidate_proposal(
                candidate=same_id_candidate,
                score=same_id_score,
                all_scores=scores_sorted,
                candidates=candidates,
                proposal_source='short_gap_same_id',
                diagnostic_reason=(
                    'short_gap_same_id_candidate'
                ),
                minimum_total=(
                    self.cfg.short_gap_same_id_min_total
                ),
                minimum_total_reason=(
                    'short_gap_same_id_below_threshold'
                ),
            )
            return proposal, None

        short_gap_base_threshold = (
            self.cfg.accept_score_lost
            if self._m.state == TargetState.LOST
            else self.cfg.accept_score_locked
        )

        best_candidate = next(
            (
                candidate
                for candidate in candidates
                if int(candidate.track_id)
                == int(best.track_id)
            ),
            None,
        )
        best_group_crop_risk = bool(
            best_candidate is not None
            and self._candidate_group_crop_risk(
                best_candidate,
                candidates,
            )
        )
        best_identity_supported = (
            self._appearance_validates_id_switch(best)
        )

        short_gap_new_id_should_suppress = (
            self._m.state
            in {
                TargetState.UNCERTAIN,
                TargetState.REACQUIRED,
            }
            or (
                self._m.state == TargetState.LOCKED
                and not best_identity_supported
                and (
                    best.geometry_score
                    < self.cfg.short_gap_new_id_allow_total
                    or (
                        best_group_crop_risk
                        and best.geometry_score
                        < self.cfg
                        .short_gap_group_risk_allow_total
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
            and best.geometry_score
            >= short_gap_base_threshold
        ):
            return None, self._miss(
                reason=(
                    'short_gap_new_id_suppressed:'
                    f' id={best.track_id}'
                    f' gap={self._m.frames_since_seen}'
                    f' score={best.geometry_score:.3f}'
                ),
                best_score=best,
                all_scores=scores_sorted,
            )

        return None, None

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
        base_sorted = sorted(
            base_scores,
            key=lambda score: score.geometry_score,
            reverse=True,
        )
        base_best = base_sorted[0]
        base_second = base_sorted[1] if len(base_sorted) > 1 else None
        base_same_id = self._m.track_id is not None and base_best.track_id == self._m.track_id
        base_ambiguous = self._is_ambiguous(base_best, base_second, same_id=base_same_id)

        use_appearance = self._should_use_appearance(base_ambiguous=base_ambiguous)

        scores = [
            self._score_candidate(self._m.bbox, c, use_appearance=use_appearance)
            for c in candidates
        ]
        scores_sorted = sorted(
            scores,
            key=lambda score: score.ranking_score,
            reverse=True,
        )
        best = scores_sorted[0]
        second = scores_sorted[1] if len(scores_sorted) > 1 else None

        best_candidate = next(c for c in candidates if c.track_id == best.track_id)
        same_id = self._m.track_id is not None and best.track_id == self._m.track_id
        ambiguous = self._is_ambiguous(best, second, same_id=same_id)

        best = replace(best, ambiguous=ambiguous)
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

        Rank-aware reacquisition intentionally uses the same gated
        appearance_raw exported in diagnostics so live behaviour matches
        the offline simulator. Geometry bypass is a separate future
        experiment, not the default TIM-MARS path.
        """
        return float(score.appearance_raw)

    def _appearance_margin(
        self,
        selected: CandidateScore,
        scores_sorted: List[CandidateScore],
    ) -> float:
        return appearance_margin(selected, scores_sorted)

    def _geometry_strength(self, score: Optional[CandidateScore]) -> float:
        return geometry_strength(score)

    def _scene_ambiguity_risk(
        self,
        best: Optional[CandidateScore],
        scores_sorted: List[CandidateScore],
    ) -> bool:
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
        self._candidate_persistence.reset()

    def _absence_confirmation_applies(
        self,
        *,
        id_switch: bool,
    ) -> bool:
        return bool(
            self.cfg.absence_recovery_enabled
            and id_switch
            and self._m.state
            in {
                TargetState.UNCERTAIN,
                TargetState.LOST,
            }
            and self._m.frames_since_seen
            >= max(
                1,
                int(
                    self.cfg.absence_after_missed_frames
                ),
            )
        )

    def _absence_aware_reacquisition_reject_reason(
        self,
        proposal: _CandidateProposal,
    ) -> Optional[str]:
        """Reject unsafe proposals in the absence-risk window."""
        if not self._absence_confirmation_applies(
            id_switch=proposal.id_switch,
        ):
            return None

        best = proposal.score

        if best.geometry_score < self.cfg.absence_min_total:
            return (
                'absence_recovery_reject:total '
                f'{best.geometry_score:.3f}'
                f'<{self.cfg.absence_min_total:.3f}'
            )

        if best.distance < self.cfg.absence_min_distance:
            return (
                'absence_recovery_reject:distance '
                f'{best.distance:.3f}'
                f'<{self.cfg.absence_min_distance:.3f}'
            )

        if best.scale < self.cfg.absence_min_scale:
            return (
                'absence_recovery_reject:scale '
                f'{best.scale:.3f}'
                f'<{self.cfg.absence_min_scale:.3f}'
            )

        if not self.cfg.absence_new_id_requires_appearance:
            return None

        if (
            not best.geometry_allows_appearance
            or best.appearance_raw <= 0.0
        ):
            return 'absence_recovery_reject:no_appearance'

        if (
            best.appearance_raw
            < self.cfg.absence_min_similarity
        ):
            return (
                'absence_recovery_reject:appearance'
                f' {best.appearance_raw:.3f}'
                f'<{self.cfg.absence_min_similarity:.3f}'
            )

        app_margin = self._appearance_margin(
            best,
            list(proposal.all_scores),
        )
        if (
            app_margin
            < self.cfg.absence_appearance_margin
        ):
            return (
                'absence_recovery_reject:appearance_margin'
                f' {app_margin:.3f}'
                f'<{self.cfg.absence_appearance_margin:.3f}'
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
                float(getattr(self.cfg, 'image_width', 640.0)),
                float(getattr(self.cfg, 'image_height', 640.0)),
            )

            if overlap >= 0.10:
                return True

            if distance <= 0.12:
                return True

        return False

    def _rank_aware_enriched_candidates(
        self,
        *,
        scores_sorted: List[CandidateScore],
        candidates: Sequence[CandidateTrack],
    ) -> list[tuple[CandidateScore, float]]:
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
                and self._m.frames_since_seen <= max(
                    0,
                    int(self.cfg.short_gap_same_id_grace_frames),
                )
            )

            if (
                group_crop_gate_active
                and int(score.track_id) != int(self._m.track_id)
                and self._candidate_group_crop_risk(candidate, candidates)
            ):
                continue

            if (
                score.geometry_score
                >= self.cfg.rank_aware_lost_min_total
                and score.distance >= self.cfg.rank_aware_lost_min_geom
                and app_raw >= self.cfg.rank_aware_lost_min_app
            ):
                enriched.append((score, app_raw))

        return enriched

    def _rank_aware_reacquisition_candidate(
        self,
        scores_sorted: List[CandidateScore],
        candidates: Sequence[CandidateTrack],
    ) -> Optional[CandidateScore]:
        if not self.cfg.rank_aware_reacquisition_enabled:
            return None

        if self._m.state not in {
            TargetState.UNCERTAIN,
            TargetState.LOST,
        }:
            return None

        enriched = self._rank_aware_enriched_candidates(
            scores_sorted=scores_sorted,
            candidates=candidates,
        )

        if not enriched:
            return None

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
            if int(score.track_id)
            != int(best.track_id)
        ]
        best_other_app = max(
            other_apps,
            default=0.0,
        )

        if (
            float(best_app) - best_other_app
            < self.cfg.rank_aware_lost_app_margin
        ):
            return None

        return self._rank_aware_diagnostic_score(
            best,
            best_app,
        )

    def _rank_aware_diagnostic_score(
        self,
        score: CandidateScore,
        appearance: float,
    ) -> CandidateScore:
        """Return a score copy exposing rank-aware appearance evidence."""
        return replace(
            score,
            appearance=appearance,
            appearance_used=True,
            appearance_raw=appearance,
            appearance_evaluated=True,
            appearance_similarity_passed=True,
            positive_similarity=appearance,
            appearance_gate_passed=True,
        )

    def _should_use_appearance(
        self,
        *,
        base_ambiguous: bool,
    ) -> bool:
        positive_appearance = self._m.appearance

        if self.cfg.appearance_protected_memory_enabled:
            positive_appearance = (
                self._positive_appearance
                .protected_reference()
            )
            if (
                positive_appearance is None
                and self._positive_appearance
                .adaptive_prototype is not None
            ):
                positive_appearance = (
                    self._positive_appearance
                    .adaptive_prototype
                )

        return should_use_appearance(
            cfg=self.cfg,
            positive_appearance=positive_appearance,
            state_is_lostish=self._m.state in {
                TargetState.UNCERTAIN,
                TargetState.LOST,
                TargetState.REACQUIRED,
            },
            base_ambiguous=base_ambiguous,
        )

    def _score_candidate(
        self,
        reference_bbox: BBox,
        candidate: CandidateTrack,
        *,
        use_appearance: bool,
    ) -> CandidateScore:
        protected_mode = bool(
            self.cfg.appearance_protected_memory_enabled
        )

        positive_appearance = self._m.appearance

        if (
            not protected_mode
            and self.cfg.appearance_enabled
            and positive_appearance is None
            and self._m.track_id is not None
            and int(candidate.track_id)
            == int(self._m.track_id)
            and candidate.appearance is not None
            and candidate.appearance_memory_update_eligible
        ):
            # Use the current same-ID observation as an ephemeral
            # scoring reference. Candidate preparation remains
            # side-effect free; accepted memory bootstrap happens
            # only during the final commit.
            positive_appearance = candidate.appearance

        base = score_candidate(
            reference_bbox,
            candidate,
            self._m.track_id,
            self.cfg,
        )

        protected_only = bool(
            protected_mode
            and (
                self._m.track_id is None
                or int(candidate.track_id)
                != int(self._m.track_id)
                or self._m.state
                in {
                    TargetState.UNCERTAIN,
                    TargetState.LOST,
                    TargetState.REACQUIRED,
                }
            )
        )

        return score_with_appearance(
            base=base,
            candidate=candidate,
            positive_appearance=positive_appearance,
            use_appearance=use_appearance,
            hard_negative_memory=(
                self._hard_negative_memory
            ),
            cfg=self.cfg,
            positive_memory=(
                self._positive_appearance
                if protected_mode
                else None
            ),
            protected_only=protected_only,
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
        return (
            best.ranking_score - second.ranking_score
        ) < self.cfg.ambiguity_margin

    def _accept(
        self,
        candidate: CandidateTrack,
        *,
        best_score: CandidateScore,
        all_scores: List[CandidateScore],
        candidates: Sequence[CandidateTrack],
        memory_update_frozen: bool = False,
        memory_update_freeze_reason: str = '',
    ) -> TargetMemoryOutput:
        previous_state = self._m.state
        previous_id = self._m.track_id

        protected_mode = bool(
            self.cfg.appearance_protected_memory_enabled
        )
        previous_positive_appearance = (
            self._positive_appearance
            .protected_reference()
            if protected_mode
            else self._m.appearance
        )

        id_changed = (
            previous_id is not None
            and int(candidate.track_id)
            != int(previous_id)
        )
        was_lostish = previous_state in {
            TargetState.UNCERTAIN,
            TargetState.LOST,
        }
        reacquired = bool(id_changed or was_lostish)

        self._candidate_persistence.reset()

        if reacquired:
            self._appearance_update_cooldown_frames_remaining = max(
                self._appearance_update_cooldown_frames_remaining,
                max(
                    0,
                    int(
                        self.cfg
                        .appearance_update_cooldown_after_reacquire_frames
                    ),
                ),
            )

        # Recovery persistence has already been confirmed before _accept().
        # Trusted selected memory is committed once, atomically, into LOCKED.
        new_state = TargetState.LOCKED

        best_score = replace(
            best_score,
            appearance_accepted_for_publication=bool(
                best_score.appearance_evaluated
                and best_score.appearance_similarity_passed
            ),
        )
        all_scores = [
            (
                best_score
                if int(score.track_id)
                == int(best_score.track_id)
                else score
            )
            for score in all_scores
        ]

        if protected_mode and reacquired:
            support_threshold = max(
                float(self.cfg.appearance_min_similarity),
                float(
                    self.cfg
                    .id_switch_min_appearance_similarity
                ),
            )
            independently_supported = bool(
                best_score.positive_support_source
                in {
                    'protected_anchor',
                    'trusted_gallery',
                }
                and best_score.positive_similarity
                >= support_threshold
            )
            self._last_acceptance_memory_source = (
                best_score.positive_support_source
                if independently_supported
                else 'none'
            )
        elif protected_mode:
            self._last_acceptance_memory_source = (
                'tracker_continuity'
            )
        else:
            self._last_acceptance_memory_source = (
                'legacy_positive_memory'
                if best_score.appearance_raw > 0.0
                else 'tracker_continuity'
            )

        self._apply_accept_memory_update(
            candidate=candidate,
            best_score=best_score,
            previous_state=previous_state,
            previous_track_id=previous_id,
            new_state=new_state,
            memory_update_frozen=memory_update_frozen,
        )

        self._commit_hard_negative_transaction(
            candidates=candidates,
            scores_sorted=all_scores,
            accepted_candidate=candidate,
            previous_state=previous_state,
            previous_track_id=previous_id,
            previous_positive_appearance=(
                previous_positive_appearance
            ),
            new_state=new_state,
        )

        return self._make_output(
            reason=(
                'accepted_candidate'
                if not reacquired
                else 'reacquired_candidate'
            ),
            visible=(new_state == TargetState.LOCKED),
            reacquired=reacquired,
            best_score=best_score,
            all_scores=all_scores,
            memory_update_frozen=memory_update_frozen,
            memory_update_freeze_reason=(
                memory_update_freeze_reason
            ),
        )

    def _commit_hard_negative_transaction(
        self,
        *,
        candidates: Sequence[CandidateTrack],
        scores_sorted: List[CandidateScore],
        accepted_candidate: CandidateTrack,
        previous_state: TargetState,
        previous_track_id: Optional[int],
        previous_positive_appearance,
        new_state: TargetState,
    ) -> None:
        """Commit negative memory only after trusted current-frame acceptance.

        Candidate preparation and proposal validation must remain side-effect
        free. A changed selected lineage is reconciled immediately, but new
        negatives are learned only from uninterrupted LOCKED continuity.
        """
        id_changed = (
            previous_track_id is not None
            and int(accepted_candidate.track_id) != int(previous_track_id)
        )
        events = []

        if self.cfg.appearance_protected_memory_enabled:
            if (
                new_state == TargetState.LOCKED
                and self._positive_appearance.lineage_trusted
                and accepted_candidate
                .appearance_memory_update_eligible
            ):
                events.extend(
                    self._hard_negative_memory.reconcile_selected(
                        accepted_candidate.appearance,
                        self.cfg,
                        selected_track_id=(
                            accepted_candidate.track_id
                        ),
                    )
                )
        elif (
            id_changed
            and accepted_candidate.appearance_memory_update_eligible
        ):
            events.extend(
                self._hard_negative_memory.reconcile_selected(
                    accepted_candidate.appearance,
                    self.cfg,
                    selected_track_id=(
                        accepted_candidate.track_id
                    ),
                )
            )

        trusted_continuity = (
            previous_state == TargetState.LOCKED
            and new_state == TargetState.LOCKED
            and previous_track_id is not None
            and int(accepted_candidate.track_id) == int(previous_track_id)
            and accepted_candidate.appearance_memory_update_eligible
            and (
                not self.cfg.appearance_protected_memory_enabled
                or self._positive_appearance.lineage_trusted
            )
        )

        if not trusted_continuity:
            events.extend(
                self._hard_negative_memory.discard_pending(
                    selected_track_id=accepted_candidate.track_id,
                )
            )
            self._last_hard_negative_events = tuple(events)
            return

        events.extend(
            self._hard_negative_memory.update(
                candidates=candidates,
                scores_sorted=scores_sorted,
                selected_track_id=accepted_candidate.track_id,
                positive_appearance=previous_positive_appearance,
                state=TargetState.LOCKED,
                cfg=self.cfg,
            )
        )
        self._last_hard_negative_events = tuple(events)

    def _apply_accept_memory_update(
        self,
        *,
        candidate: CandidateTrack,
        best_score: CandidateScore,
        previous_state: TargetState,
        previous_track_id: Optional[int],
        new_state: TargetState,
        memory_update_frozen: bool,
    ) -> None:
        protected_mode = bool(
            self.cfg.appearance_protected_memory_enabled
        )

        id_changed = (
            previous_track_id is not None
            and int(candidate.track_id)
            != int(previous_track_id)
        )
        was_lostish = previous_state in {
            TargetState.UNCERTAIN,
            TargetState.LOST,
        }
        reacquired = bool(id_changed or was_lostish)

        if protected_mode and reacquired:
            support_threshold = max(
                float(self.cfg.appearance_min_similarity),
                float(
                    self.cfg
                    .id_switch_min_appearance_similarity
                ),
            )
            independently_supported = bool(
                best_score.positive_support_source
                in {
                    'protected_anchor',
                    'trusted_gallery',
                }
                and best_score.positive_similarity
                >= support_threshold
            )
            self._positive_appearance.begin_reacquired_lineage(
                track_id=candidate.track_id,
                independently_supported=(
                    independently_supported
                ),
            )

        self._m.selected = True
        self._m.state = new_state
        self._m.track_id = candidate.track_id
        self._m.bbox = candidate.bbox
        self._m.quality = clamp01(
            0.65 * best_score.total
            + 0.35 * candidate.score
        )
        self._m.frames_since_seen = 0

        if not protected_mode:
            can_update_appearance = (
                new_state == TargetState.LOCKED
                and self._appearance_update_cooldown_frames_remaining
                <= 0
                and not memory_update_frozen
                and candidate.appearance_memory_update_eligible
            )

            if can_update_appearance:
                self._m.appearance = update_feature_memory(
                    self._m.appearance,
                    candidate.appearance,
                    alpha=self.cfg.appearance_update_alpha,
                )
            elif (
                self._appearance_update_cooldown_frames_remaining
                > 0
            ):
                self._appearance_update_cooldown_frames_remaining -= 1
            return

        observation_eligible = bool(
            new_state == TargetState.LOCKED
            and not memory_update_frozen
            and candidate.appearance_memory_update_eligible
            and candidate.appearance is not None
            and not best_score.ambiguous
            and not best_score.hard_negative_reject
        )

        if not observation_eligible:
            return

        if (
            self._appearance_update_cooldown_frames_remaining
            > 0
        ):
            self._appearance_update_cooldown_frames_remaining -= 1
            return

        bootstrapped = (
            self._positive_appearance
            .bootstrap_operator_anchor(
                track_id=candidate.track_id,
                appearance=candidate.appearance,
            )
        )
        if bootstrapped:
            self._last_positive_memory_updated = True
            self._last_positive_memory_update_reason = (
                'protected_anchor_bootstrap'
            )
            return

        if not self._positive_appearance.lineage_trusted:
            self._positive_appearance.observe_locked(
                track_id=candidate.track_id,
                required_frames=(
                    self.cfg
                    .appearance_trusted_lock_frames_before_update
                ),
            )

        if not self._positive_appearance.lineage_trusted:
            return

        updated = self._positive_appearance.update_trusted(
            appearance=candidate.appearance,
            alpha=self.cfg.appearance_update_alpha,
            gallery_max_entries=(
                self.cfg
                .appearance_trusted_gallery_max_entries
            ),
        )

        if updated:
            self._last_positive_memory_updated = True
            self._last_positive_memory_update_reason = (
                'trusted_locked_adaptive_update'
            )

    def _appearance_conservative_reject_reason(
        self,
        *,
        best_score: CandidateScore,
        all_scores: List[CandidateScore],
    ) -> Optional[str]:
        if not self.cfg.appearance_conservative_enabled:
            return None

        if not best_score.appearance_used:
            if (
                self.cfg
                .appearance_conservative_require_appearance
            ):
                return (
                    'appearance_conservative_reject:'
                    'no_appearance_used'
                )
            return None

        appearance_scores = sorted(
            [
                score.appearance_raw
                for score in all_scores
                if (
                    score.appearance_used
                    and score.geometry_allows_appearance
                )
            ],
            reverse=True,
        )
        selected_app = best_score.appearance_raw
        second_app = (
            appearance_scores[1]
            if len(appearance_scores) > 1
            else 0.0
        )
        app_margin = selected_app - second_app

        if (
            selected_app
            < self.cfg
            .appearance_conservative_min_similarity
            or app_margin
            < self.cfg.appearance_conservative_margin
        ):
            return (
                'appearance_conservative_reject:'
                f' selected_app={selected_app:.3f}'
                f' second_app={second_app:.3f}'
                f' margin={app_margin:.3f}'
            )

        return None

    def _miss(
        self,
        *,
        reason: str,
        best_score: Optional[CandidateScore] = None,
        all_scores: Optional[List[CandidateScore]] = None,
        memory_update_frozen: bool = False,
        memory_update_freeze_reason: str = '',
    ) -> TargetMemoryOutput:
        self._m.frames_since_seen += 1
        self._m.quality *= self.cfg.stale_quality_decay
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
        state_override: Optional[TargetState] = None,
        control_mode_override: Optional[ControlMode] = None,
        memory_update_frozen: bool = False,
        memory_update_freeze_reason: str = '',
    ) -> TargetMemoryOutput:
        score_list = all_scores or []

        appearance_margin_best_vs_second = (
            self._appearance_margin(best_score, score_list)
            if best_score is not None
            else 0.0
        )
        geometry_strength = self._geometry_strength(best_score)
        risk_hard_negative = (
            bool(best_score.hard_negative_reject)
            if best_score is not None
            else False
        )
        risk_absence = self._absence_risk()
        risk_scene_ambiguity = self._scene_ambiguity_risk(best_score, score_list)
        candidate_track_id = int(best_score.track_id) if best_score is not None else None
        candidate_score = float(best_score.total) if best_score is not None else 0.0
        publication_suppressed_reason = '' if visible else reason
        output_state = state_override or self._m.state

        return TargetMemoryOutput(
            state=output_state,
            control_mode=(
                control_mode_override
                or _control_mode_for_state(output_state)
            ),
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
            acceptance_memory_source=(
                self._last_acceptance_memory_source
            ),
            positive_memory_updated=(
                self._last_positive_memory_updated
            ),
            positive_memory_update_reason=(
                self._last_positive_memory_update_reason
            ),
            protected_anchor_available=bool(
                self._positive_appearance
                .protected_anchor is not None
            ),
            trusted_gallery_size=len(
                self._positive_appearance.trusted_gallery
            ),
            appearance_lineage_trusted=bool(
                self._positive_appearance.lineage_trusted
            ),
            appearance_trusted_lock_streak=int(
                self._positive_appearance
                .trusted_lock_streak
            ),
            appearance_margin_best_vs_second=appearance_margin_best_vs_second,
            geometry_strength=geometry_strength,
            risk_hard_negative=risk_hard_negative,
            hard_negative_memory_size=len(
                self._hard_negative_memory
            ),
            hard_negative_events=(
                self._last_hard_negative_events
            ),
            risk_absence=risk_absence,
            risk_scene_ambiguity=risk_scene_ambiguity,
            candidate_track_id=candidate_track_id,
            candidate_score=candidate_score,
            publication_suppressed_reason=publication_suppressed_reason,
        )


__all__ = [
    'BBox',
    'CandidateScore',
    'CandidateTrack',
    'ControlMode',
    'TargetIdentityMemory',
    'TargetMemoryConfig',
    'TargetMemoryOutput',
    'TargetState',
    'bbox_area',
    'bbox_centre',
    'bbox_iou',
    'centre_distance_norm',
    'distance_similarity',
    'scale_similarity',
    'score_candidate',
]
