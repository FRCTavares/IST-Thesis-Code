"""Pure CPU candidate-request policy for TIM-MARS appearance encoding.

This module decides which current tracker candidates should request an
appearance embedding. It is deliberately ROS-free and side-effect-free.

The policy may inspect public selected-target state and stateless geometry
scores. It must not mutate TargetIdentityMemory, candidate objects, appearance
cache state, or backend state.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from thesis_bringup.tim_mars.appearance_policy import (
    geometry_allows_appearance,
)
from thesis_bringup.tim_mars.geometry_scoring import (
    bbox_area,
    score_candidate,
)
from thesis_bringup.tim_mars.types import (
    BBox,
    CandidateScore,
    CandidateTrack,
    TargetMemoryConfig,
    TargetState,
)


class AppearanceRequestPolicy(str, Enum):
    """Available pre-embedding candidate-selection policies."""

    ALL_CANDIDATES = "all_candidates"
    GEOMETRY_WINNER = "geometry_winner"


@dataclass(frozen=True)
class AppearanceRequestCandidateRank:
    """One geometry-only candidate rank produced without state mutation."""

    input_index: int
    track_id: int
    score: CandidateScore
    meets_minimum_score: bool
    geometry_plausible: bool


@dataclass(frozen=True)
class AppearanceRequestDecision:
    """Auditable result of one pure candidate-request decision."""

    policy: AppearanceRequestPolicy
    target_state: TargetState
    requested_indices: tuple[int, ...]
    requested_track_ids: tuple[int, ...]
    reason: str
    ranked_candidates: tuple[
        AppearanceRequestCandidateRank,
        ...,
    ] = ()


def _coerce_policy(
    policy: AppearanceRequestPolicy | str,
) -> AppearanceRequestPolicy:
    if isinstance(policy, AppearanceRequestPolicy):
        return policy

    try:
        return AppearanceRequestPolicy(str(policy))
    except ValueError as exc:
        supported = ", ".join(
            item.value
            for item in AppearanceRequestPolicy
        )
        raise ValueError(
            "unsupported appearance request policy "
            f"{policy!r}; expected one of: {supported}"
        ) from exc


def _validate_unique_track_ids(
    candidates: Sequence[CandidateTrack],
) -> None:
    seen: set[int] = set()
    duplicates: set[int] = set()

    for candidate in candidates:
        track_id = int(candidate.track_id)

        if track_id in seen:
            duplicates.add(track_id)

        seen.add(track_id)

    if duplicates:
        rendered = ", ".join(
            str(track_id)
            for track_id in sorted(duplicates)
        )
        raise ValueError(
            "appearance request policy requires unique "
            f"track IDs; duplicates: {rendered}"
        )


def _single_request(
    *,
    policy: AppearanceRequestPolicy,
    target_state: TargetState,
    index: int,
    candidate: CandidateTrack,
    reason: str,
    ranked_candidates: tuple[
        AppearanceRequestCandidateRank,
        ...,
    ] = (),
) -> AppearanceRequestDecision:
    return AppearanceRequestDecision(
        policy=policy,
        target_state=target_state,
        requested_indices=(int(index),),
        requested_track_ids=(int(candidate.track_id),),
        reason=str(reason),
        ranked_candidates=ranked_candidates,
    )


def _empty_request(
    *,
    policy: AppearanceRequestPolicy,
    target_state: TargetState,
    reason: str,
    ranked_candidates: tuple[
        AppearanceRequestCandidateRank,
        ...,
    ] = (),
) -> AppearanceRequestDecision:
    return AppearanceRequestDecision(
        policy=policy,
        target_state=target_state,
        requested_indices=(),
        requested_track_ids=(),
        reason=str(reason),
        ranked_candidates=ranked_candidates,
    )


def select_appearance_request_candidates(
    *,
    policy: AppearanceRequestPolicy | str,
    candidates: Sequence[CandidateTrack],
    target_state: TargetState,
    reference_bbox: BBox | None,
    current_track_id: int | None,
    target_config: TargetMemoryConfig,
    pending_select_id: int | None = None,
    auto_select_largest: bool = False,
) -> AppearanceRequestDecision:
    """Choose candidate indices that may request an embedding.

    ``all_candidates`` preserves the existing pre-crop policy by forwarding
    every tracker candidate. Crop-quality filtering remains the attachment
    layer's responsibility.

    ``geometry_winner`` performs a stateless CPU geometry pass and requests at
    most one candidate:

    1. a visible pending operator selection has priority;
    2. before target initialisation, optional auto-selection uses bbox area;
    3. otherwise the highest geometry-only ranking score wins;
    4. candidates below the minimum score or outside the existing appearance
       geometry gate are not requested.

    Candidate ordering, objects, target memory, and configuration are never
    mutated.
    """
    resolved_policy = _coerce_policy(policy)
    candidate_tuple = tuple(candidates)
    resolved_state = TargetState(target_state)

    if not candidate_tuple:
        return _empty_request(
            policy=resolved_policy,
            target_state=resolved_state,
            reason="no_candidates",
        )

    if resolved_policy == AppearanceRequestPolicy.ALL_CANDIDATES:
        return AppearanceRequestDecision(
            policy=resolved_policy,
            target_state=resolved_state,
            requested_indices=tuple(
                range(len(candidate_tuple))
            ),
            requested_track_ids=tuple(
                int(candidate.track_id)
                for candidate in candidate_tuple
            ),
            reason="all_candidates",
        )

    # The unchanged all-candidate baseline forwards the tracker output
    # exactly as supplied. Experimental selective policies require unique
    # tracker IDs because their decision is keyed by identity.
    _validate_unique_track_ids(candidate_tuple)

    resolved_pending_id = (
        int(pending_select_id)
        if (
            pending_select_id is not None
            and int(pending_select_id) > 0
        )
        else None
    )

    if resolved_pending_id is not None:
        for index, candidate in enumerate(candidate_tuple):
            if int(candidate.track_id) == resolved_pending_id:
                return _single_request(
                    policy=resolved_policy,
                    target_state=resolved_state,
                    index=index,
                    candidate=candidate,
                    reason="pending_operator_selection",
                )

        return _empty_request(
            policy=resolved_policy,
            target_state=resolved_state,
            reason="pending_operator_selection_not_visible",
        )

    has_selected_reference = bool(
        resolved_state != TargetState.NO_TARGET
        and reference_bbox is not None
        and current_track_id is not None
    )

    if not has_selected_reference:
        if not auto_select_largest:
            return _empty_request(
                policy=resolved_policy,
                target_state=resolved_state,
                reason="no_selected_target",
            )

        winner_index, winner = max(
            enumerate(candidate_tuple),
            key=lambda item: (
                bbox_area(item[1].bbox),
                float(item[1].score),
                -int(item[0]),
            ),
        )

        return _single_request(
            policy=resolved_policy,
            target_state=resolved_state,
            index=winner_index,
            candidate=winner,
            reason="auto_select_largest",
        )

    assert reference_bbox is not None
    assert current_track_id is not None

    ranks: list[AppearanceRequestCandidateRank] = []

    for index, candidate in enumerate(candidate_tuple):
        score = score_candidate(
            reference_bbox,
            candidate,
            int(current_track_id),
            target_config,
        )
        meets_minimum = bool(
            float(score.geometry_score)
            >= float(target_config.min_candidate_score)
        )
        plausible = bool(
            meets_minimum
            and geometry_allows_appearance(score)
        )

        ranks.append(
            AppearanceRequestCandidateRank(
                input_index=int(index),
                track_id=int(candidate.track_id),
                score=score,
                meets_minimum_score=meets_minimum,
                geometry_plausible=plausible,
            )
        )

    ranked = tuple(
        sorted(
            ranks,
            key=lambda item: (
                -float(item.score.ranking_score),
                int(item.input_index),
            ),
        )
    )

    plausible = tuple(
        item
        for item in ranked
        if item.geometry_plausible
    )

    if not plausible:
        return _empty_request(
            policy=resolved_policy,
            target_state=resolved_state,
            reason="no_geometry_plausible_candidate",
            ranked_candidates=ranked,
        )

    winner_rank = plausible[0]
    winner = candidate_tuple[winner_rank.input_index]

    return _single_request(
        policy=resolved_policy,
        target_state=resolved_state,
        index=winner_rank.input_index,
        candidate=winner,
        reason="geometry_winner",
        ranked_candidates=ranked,
    )


__all__ = [
    "AppearanceRequestCandidateRank",
    "AppearanceRequestDecision",
    "AppearanceRequestPolicy",
    "select_appearance_request_candidates",
]
