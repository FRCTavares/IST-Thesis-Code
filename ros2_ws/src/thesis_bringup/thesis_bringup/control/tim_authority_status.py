"""Strict parser for controller-facing TIM-MARS authority status."""

from __future__ import annotations

from dataclasses import dataclass
import json


@dataclass(frozen=True)
class TimAuthorityStatus:
    state: str
    control_mode: str
    selection_generation: int
    selection_session_id: str
    frame_id: int | None
    source_stamp_ns: int | None
    target_track_id: int | None
    freshness_is_fresh: bool
    reason: str


@dataclass(frozen=True)
class AuthorityEpochDecision:
    accepted: bool
    reset_authority: bool
    reason: str


def evaluate_authority_epoch(
    *,
    current_session_id: str | None,
    current_generation: int | None,
    retired_session_ids: set[str],
    incoming_session_id: str,
    incoming_generation: int,
) -> AuthorityEpochDecision:
    """Reject delayed generations/sessions while allowing a genuine restart."""
    if current_session_id is None or current_generation is None:
        return AuthorityEpochDecision(
            accepted=True,
            reset_authority=True,
            reason="initial_authority_session",
        )

    if incoming_session_id == current_session_id:
        if incoming_generation < current_generation:
            return AuthorityEpochDecision(
                accepted=False,
                reset_authority=True,
                reason="generation_rollback",
            )
        if incoming_generation > current_generation:
            return AuthorityEpochDecision(
                accepted=True,
                reset_authority=True,
                reason="generation_advance",
            )
        return AuthorityEpochDecision(
            accepted=True,
            reset_authority=False,
            reason="same_generation",
        )

    if incoming_session_id in retired_session_ids:
        return AuthorityEpochDecision(
            accepted=False,
            reset_authority=True,
            reason="retired_session",
        )

    return AuthorityEpochDecision(
        accepted=True,
        reset_authority=True,
        reason="new_authority_session",
    )


def _optional_int(
    payload: dict[str, object],
    key: str,
) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} must be an integer or null")
    if value < 0:
        raise ValueError(f"{key} must be non-negative")
    return int(value)


def parse_tim_authority_status(data: str) -> TimAuthorityStatus:
    try:
        payload = json.loads(data)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid TIM-MARS status JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError("TIM-MARS status must be a JSON object")

    state = payload.get("state")
    control_mode = payload.get("control_mode")
    generation = payload.get("selection_generation")
    session_id = payload.get("selection_session_id")

    if not isinstance(state, str) or not state:
        raise ValueError("state must be a non-empty string")
    if not isinstance(control_mode, str) or not control_mode:
        raise ValueError("control_mode must be a non-empty string")
    if (
        isinstance(generation, bool)
        or not isinstance(generation, int)
        or generation < 0
    ):
        raise ValueError(
            "selection_generation must be a non-negative integer"
        )
    if not isinstance(session_id, str) or not session_id:
        raise ValueError(
            "selection_session_id must be a non-empty string"
        )

    freshness = payload.get("freshness_is_fresh", False)
    if not isinstance(freshness, bool):
        raise ValueError("freshness_is_fresh must be boolean")

    reason = payload.get("reason", "")
    if not isinstance(reason, str):
        raise ValueError("reason must be a string")

    return TimAuthorityStatus(
        state=state,
        control_mode=control_mode,
        selection_generation=int(generation),
        selection_session_id=session_id,
        frame_id=_optional_int(payload, "frame_id"),
        source_stamp_ns=_optional_int(
            payload,
            "track_timestamp_ns",
        ),
        target_track_id=_optional_int(payload, "target_track_id"),
        freshness_is_fresh=freshness,
        reason=reason,
    )
