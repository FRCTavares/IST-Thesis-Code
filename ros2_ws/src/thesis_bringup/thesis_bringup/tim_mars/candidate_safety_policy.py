"""Candidate acceptance safety policies for TIM-MARS.

These functions evaluate candidate evidence without mutating target-memory
state. Keeping them separate makes the state-machine orchestration easier to
read while preserving the conservative identity-safety rules.
"""

from __future__ import annotations

from typing import Optional, Sequence

from thesis_bringup.tim_mars.reacquisition_policy import (
    appearance_margin,
)
from thesis_bringup.tim_mars.types import (
    CandidateScore,
    CandidateTrack,
    TargetMemoryConfig,
    TargetState,
)


def protected_gallery_reacquisition_reject_reason(
    *,
    cfg: TargetMemoryConfig,
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
        or not cfg.appearance_protected_memory_enabled
        or score.positive_support_source != "trusted_gallery"
    ):
        return None

    if not candidate.appearance_memory_update_eligible:
        return (
            "protected_gallery_reacquisition_reject:"
            "untrusted_crop"
        )

    if score.ambiguous:
        return (
            "protected_gallery_reacquisition_reject:"
            "ambiguous_candidate"
        )

    anchor_threshold = max(
        0.0,
        float(cfg.appearance_gallery_min_anchor_similarity),
    )

    if (
        anchor_threshold > 0.0
        and float(
            score.protected_anchor_similarity
        ) < anchor_threshold
    ):
        return (
            "protected_gallery_reacquisition_reject:"
            "anchor"
            f" {score.protected_anchor_similarity:.3f}"
            f"<{anchor_threshold:.3f}"
        )

    return None


def appearance_conservative_reject_reason(
    *,
    cfg: TargetMemoryConfig,
    best_score: CandidateScore,
    all_scores: Sequence[CandidateScore],
) -> Optional[str]:
    """Apply the conservative appearance acceptance policy."""
    if not cfg.appearance_conservative_enabled:
        return None

    if not best_score.appearance_used:
        if cfg.appearance_conservative_require_appearance:
            return (
                "appearance_conservative_reject:"
                "no_appearance_used"
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
        < cfg.appearance_conservative_min_similarity
        or app_margin
        < cfg.appearance_conservative_margin
    ):
        return (
            "appearance_conservative_reject:"
            f" selected_app={selected_app:.3f}"
            f" second_app={second_app:.3f}"
            f" margin={app_margin:.3f}"
        )

    return None


def same_id_hijack_reject_reason(
    *,
    cfg: TargetMemoryConfig,
    same_id: bool,
    score: CandidateScore,
    memory_state: TargetState,
    challenger: CandidateScore | None,
    appearance_threshold: float,
) -> Optional[str]:
    """Reject a plausible same-ID person handover without identity support."""
    if (
        not cfg.same_id_hijack_protection_enabled
        or not cfg.appearance_enabled
        or not same_id
        or memory_state != TargetState.LOCKED
    ):
        return None

    if challenger is None:
        return None

    identity_supported = bool(
        appearance_threshold > 0.0
        and score.appearance_evaluated
        and score.appearance_raw >= appearance_threshold
        and not score.hard_negative_reject
    )
    if identity_supported:
        return None

    if score.hard_negative_reject:
        evidence = (
            "hard_negative"
            f" neg={score.hard_negative_similarity:.3f}"
            f" margin={score.hard_negative_margin:.3f}"
        )
    elif not score.appearance_evaluated:
        evidence = "no_current_appearance"
    else:
        evidence = (
            "appearance"
            f" {score.appearance_raw:.3f}"
            f"<{appearance_threshold:.3f}"
        )

    return (
        "same_id_hijack_reject:"
        f" challenger={challenger.track_id}"
        f" {evidence}"
    )


def id_switch_appearance_reject_reason(
    *,
    cfg: TargetMemoryConfig,
    candidate: CandidateTrack,
    score: CandidateScore,
    id_switch: bool,
    pending_candidate_id: int | None,
    pending_identity_confirmed: bool,
    appearance_threshold: float,
) -> Optional[str]:
    """Return why appearance cannot authorize a tracker-ID change."""
    if (
        not id_switch
        or not cfg.allow_id_switch_recovery
        or not cfg.appearance_enabled
    ):
        return None

    if candidate.appearance is None:
        same_pending_candidate = bool(
            pending_candidate_id == int(candidate.track_id)
        )
        if (
            same_pending_candidate
            and pending_identity_confirmed
        ):
            return None

        return (
            "id_switch_recovery_reject:"
            "no_candidate_appearance"
        )

    if appearance_threshold <= 0.0:
        return None

    if not score.appearance_evaluated:
        return (
            "id_switch_recovery_reject:"
            "appearance_not_evaluated"
        )

    if float(score.appearance_raw) < appearance_threshold:
        return (
            "id_switch_recovery_reject:"
            "appearance"
            f" {score.appearance_raw:.3f}"
            f"<{appearance_threshold:.3f}"
        )

    return None


def absence_aware_reacquisition_reject_reason(
    *,
    cfg: TargetMemoryConfig,
    score: CandidateScore,
    all_scores: Sequence[CandidateScore],
    absence_confirmation_applies: bool,
) -> Optional[str]:
    """Reject unsafe proposals in the absence-risk window."""
    if not absence_confirmation_applies:
        return None

    if score.geometry_score < cfg.absence_min_total:
        return (
            "absence_recovery_reject:total "
            f"{score.geometry_score:.3f}"
            f"<{cfg.absence_min_total:.3f}"
        )

    if score.distance < cfg.absence_min_distance:
        return (
            "absence_recovery_reject:distance "
            f"{score.distance:.3f}"
            f"<{cfg.absence_min_distance:.3f}"
        )

    if score.scale < cfg.absence_min_scale:
        return (
            "absence_recovery_reject:scale "
            f"{score.scale:.3f}"
            f"<{cfg.absence_min_scale:.3f}"
        )

    if not cfg.absence_new_id_requires_appearance:
        return None

    if (
        not score.geometry_allows_appearance
        or score.appearance_raw <= 0.0
    ):
        return "absence_recovery_reject:no_appearance"

    if score.appearance_raw < cfg.absence_min_similarity:
        return (
            "absence_recovery_reject:appearance"
            f" {score.appearance_raw:.3f}"
            f"<{cfg.absence_min_similarity:.3f}"
        )

    margin = appearance_margin(
        score,
        list(all_scores),
    )
    if margin < cfg.absence_appearance_margin:
        return (
            "absence_recovery_reject:appearance_margin"
            f" {margin:.3f}"
            f"<{cfg.absence_appearance_margin:.3f}"
        )

    return None
